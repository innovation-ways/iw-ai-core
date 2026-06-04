"""Project dashboard route — summary cards, active batches, activity feed, git status."""

from __future__ import annotations

import contextlib
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import Integer, func, select

from dashboard.dependencies import get_db
from dashboard.utils.batch_progress import compute_batch_step_progress
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
    RegressionClassification,
    RunStatus,
    StepRun,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
)

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session


router = APIRouter(prefix="/project/{project_id}")


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class BatchSummary:
    """Summary of a single batch for the dashboard active-batches list.

    Attributes:
        id: Batch identifier.
        status: Current batch status string.
        total_items: Total number of work items in the batch.
        completed_items: Count of items in completed or merged status.
        progress_pct: Overall step progress percentage (0–100).
    """

    id: str
    status: str
    total_items: int
    completed_items: int
    progress_pct: int


@dataclass
class ActivityEntry:
    """A single daemon_events row for the activity feed.

    Attributes:
        timestamp: When the event was created.
        event_type: Event type string (e.g. 'step_completed').
        entity_id: Optional ID of the entity the event relates to.
        entity_type: Optional type of entity ('item', 'batch', etc.).
        message: Optional human-readable event description.
    """

    timestamp: datetime
    event_type: str
    entity_id: str | None
    entity_type: str | None
    message: str | None


@dataclass
class GitStatus:
    """Git state for the project repo.

    Attributes:
        branch: Currently checked-out branch name.
        unpushed: Number of commits ahead of the remote tracking branch.
        worktrees: Number of active agent worktrees (excluding main).
        error: Non-None when git commands failed.
    """

    branch: str
    unpushed: int
    worktrees: int
    error: str | None = None


@dataclass
class WeekRow:
    """Weekly quality KPI row (AC6).

    Attributes:
        iso_week: ISO week label in the form 'YYYY-WNN'.
        merges: Count of work items completed in this week.
        regressions: Count of regressions whose classified_at falls in this week.
        rate: regressions / merges; 0.0 when merges == 0.
    """

    iso_week: str
    merges: int
    regressions: int
    rate: float  # regressions / merges; 0.0 when merges == 0


# ---------------------------------------------------------------------------
# DB helpers — Quality KPIs (AC6)
# ---------------------------------------------------------------------------


def weekly_metrics(project_id: str, db: Session, weeks: int = 12) -> list[WeekRow]:
    """Return weekly (merges, regressions, rate) for the last `weeks` ISO weeks.

    merges = count of WorkItem rows with status='completed' whose completed_at week matches.
    regressions = count of WorkItem rows with regression_classification='regression'
      AND introduced_by_work_item_id IS NOT NULL whose classified_at falls in the week.
    rate_guard: when merges == 0, rate is 0.0 (not NaN, not divide-by-zero).
    """
    import datetime as dt

    now = datetime.now(UTC)
    today = now.date()
    current_year, current_week, _ = today.isocalendar()

    # Build ISO week ranges going back `weeks` weeks from current
    week_ranges: list[tuple[str, datetime, datetime]] = []
    for w in range(weeks - 1, -1, -1):
        target_week = current_week - w
        target_year = current_year
        if target_week < 1:
            target_year -= 1
            last_day = dt.date(target_year, 12, 28)
            target_week = last_day.isocalendar()[1]
        iso_label = f"{target_year}-W{target_week:02d}"
        jan4 = dt.date(target_year, 1, 4)
        iso_monday = jan4 - dt.timedelta(days=jan4.weekday())
        week_start_date = iso_monday + dt.timedelta(weeks=target_week - 1)
        week_start = dt.datetime.combine(week_start_date, dt.datetime.min.time(), tzinfo=UTC)
        week_end = week_start + dt.timedelta(days=7)
        week_ranges.append((iso_label, week_start, week_end))

    # Query merges per week (status == 'completed')
    merge_rows = db.execute(
        select(
            func.date_trunc("week", WorkItem.completed_at).label("week_start"),
            func.count().label("cnt"),
        )
        .where(
            WorkItem.project_id == project_id,
            WorkItem.status == WorkItemStatus.completed,
            WorkItem.completed_at.isnot(None),
        )
        .group_by("week_start")
    ).all()

    # Query regressions per week
    regression_rows = db.execute(
        select(
            func.date_trunc("week", WorkItem.classified_at).label("week_start"),
            func.count().label("cnt"),
        )
        .where(
            WorkItem.project_id == project_id,
            WorkItem.regression_classification == RegressionClassification.regression,
            WorkItem.introduced_by_work_item_id.isnot(None),
            WorkItem.classified_at.isnot(None),
        )
        .group_by("week_start")
    ).all()

    merge_map: dict[datetime, int] = {}
    for row in merge_rows:
        ws = row.week_start
        if ws is not None:
            merge_map[ws.replace(tzinfo=UTC)] = row.cnt

    regression_map: dict[datetime, int] = {}
    for row in regression_rows:
        ws = row.week_start
        if ws is not None:
            regression_map[ws.replace(tzinfo=UTC)] = row.cnt

    results: list[WeekRow] = []
    for iso_label, week_start, week_end in week_ranges:
        merges = 0
        regressions = 0
        for ws, cnt in merge_map.items():
            if week_start <= ws < week_end:
                merges = cnt
                break
        for ws, cnt in regression_map.items():
            if week_start <= ws < week_end:
                regressions = cnt
                break
        rate = round(regressions / merges, 3) if merges > 0 else 0.0
        results.append(
            WeekRow(iso_week=iso_label, merges=merges, regressions=regressions, rate=rate)
        )
    return results


def regression_count_for_merge(
    project_id: str, merge_item_ids: list[str], db: Session
) -> dict[str, int]:
    """Batched regression count per merge item. Avoids N+1 on batch/history row rendering.

    Returns {merge_item_id: count} of Incidents with
    regression_classification='regression' AND introduced_by_work_item_id == merge_item_id.
    """
    if not merge_item_ids:
        return {}

    rows = db.execute(
        select(
            WorkItem.introduced_by_work_item_id,
            func.count().label("cnt"),
        )
        .where(
            WorkItem.project_id == project_id,
            WorkItem.introduced_by_work_item_id.in_(merge_item_ids),
            WorkItem.regression_classification == RegressionClassification.regression,
        )
        .group_by(WorkItem.introduced_by_work_item_id)
    ).all()
    return {row.introduced_by_work_item_id: row.cnt for row in rows}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _get_project_or_404(project_id: str, db: Session) -> Project:
    """Fetch a project by ID or raise HTTP 404.

    Args:
        project_id: The project identifier to look up.
        db: Active database session.

    Returns:
        The matching Project ORM row.

    Raises:
        HTTPException: With status 404 if the project does not exist.
    """
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


def _active_batches(project_id: str, db: Session) -> list[BatchSummary]:
    """Return active batches with total/done counts in a single query (C2 fix)."""
    active_statuses = [
        BatchStatus.executing,
        BatchStatus.approved,
        BatchStatus.paused,
        BatchStatus.publishing,
    ]
    batches = list(
        db.scalars(
            select(Batch)
            .where(Batch.project_id == project_id, Batch.status.in_(active_statuses))
            .order_by(Batch.created_at.desc())
        ).all()
    )

    if not batches:
        return []

    batch_ids = [b.id for b in batches]

    # Single query: total + done counts grouped by batch_id
    rows = db.execute(
        select(
            BatchItem.batch_id,
            func.count(BatchItem.id).label("total"),
            func.sum(
                func.cast(
                    func.cast(
                        BatchItem.status.in_([BatchItemStatus.completed, BatchItemStatus.merged]),
                        Integer,
                    ),
                    Integer,
                )
            ).label("done"),
        )
        .where(
            BatchItem.project_id == project_id,
            BatchItem.batch_id.in_(batch_ids),
        )
        .group_by(BatchItem.batch_id)
    ).all()

    counts: dict[str, tuple[int, int]] = {}
    for row in rows:
        counts[row.batch_id] = (row.total, int(row.done or 0))

    step_progress = compute_batch_step_progress(project_id, batch_ids, db)

    result = []
    for batch in batches:
        total, done = counts.get(batch.id, (0, 0))
        pct = step_progress.get(batch.id, 0)
        result.append(
            BatchSummary(
                id=batch.id,
                status=batch.status.value,
                total_items=total,
                completed_items=done,
                progress_pct=pct,
            )
        )
    return result


def _recent_activity(project_id: str, db: Session, limit: int = 20) -> list[ActivityEntry]:
    events = list(
        db.scalars(
            select(DaemonEvent)
            .where(DaemonEvent.project_id == project_id)
            .order_by(DaemonEvent.created_at.desc())
            .limit(limit)
        ).all()
    )
    return [
        ActivityEntry(
            timestamp=e.created_at,
            event_type=e.event_type,
            entity_id=e.entity_id,
            entity_type=e.entity_type,
            message=e.message,
        )
        for e in events
    ]


def _running_steps_count(project_id: str, db: Session) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(StepRun)
            .join(WorkflowStep, StepRun.step_id == WorkflowStep.id)
            .where(
                WorkflowStep.project_id == project_id,
                StepRun.status == RunStatus.running,
            )
        )
        or 0
    )


def _completed_this_week(project_id: str, db: Session) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=7)
    return (
        db.scalar(
            select(func.count()).where(
                WorkItem.project_id == project_id,
                WorkItem.status == WorkItemStatus.completed,
                WorkItem.completed_at >= cutoff,
            )
        )
        or 0
    )


def _git_status(repo_root: str) -> GitStatus:
    """Query git state for the project repo. Returns partial data on errors."""
    # repo_root comes from the DB (not user input); "git" is a fixed system binary
    try:
        branch = subprocess.check_output(  # noqa: S603
            ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return GitStatus(branch="unknown", unpushed=0, worktrees=0, error="git unavailable")

    unpushed = 0
    with contextlib.suppress(Exception):
        out = subprocess.check_output(  # noqa: S603
            ["git", "-C", repo_root, "rev-list", "--count", "@{u}..HEAD"],  # noqa: S607
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        ).strip()
        unpushed = int(out)

    worktrees = 0
    with contextlib.suppress(Exception):
        out = subprocess.check_output(  # noqa: S603
            ["git", "-C", repo_root, "worktree", "list"],  # noqa: S607
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
        # Each worktree is one line; subtract 1 for the main worktree itself
        worktrees = max(0, len([ln for ln in out.strip().splitlines() if ln]) - 1)

    return GitStatus(branch=branch, unpushed=unpushed, worktrees=worktrees)


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def project_dashboard(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Render the per-project dashboard home page.

    Args:
        project_id: The project to render the dashboard for.
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        Full HTML dashboard page with activity feed, active batches, KPIs, and git status.
    """
    project = _get_project_or_404(project_id, db)
    running_count = _running_steps_count(project_id, db)
    active = _active_batches(project_id, db)
    activity = _recent_activity(project_id, db)
    completed_week = _completed_this_week(project_id, db)
    git = _git_status(project.repo_root)
    # AC6: compute weekly KPIs for the section
    kpi_weeks = weekly_metrics(project_id, db, weeks=12)
    current_week = kpi_weeks[-1] if kpi_weeks else None

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project/dashboard.html",
        {
            "current_project": project,
            "running_count": running_count,
            "active_batches": active,
            "active_batches_count": len(active),
            "running_steps_count": running_count,
            "completed_this_week": completed_week,
            "recent_activity": activity,
            "git_status": git,
            "kpi_weeks": kpi_weeks,
            "current_week": current_week,
        },
    )


@router.get("/quality-kpis", response_class=HTMLResponse)
def quality_kpis_page(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Dedicated Quality KPIs page — same section as per-project home, full-screen (AC6)."""
    project = _get_project_or_404(project_id, db)
    kpi_weeks = weekly_metrics(project_id, db, weeks=12)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/quality_kpis.html",
        {
            "current_project": project,
            "kpi_weeks": kpi_weeks,
            "current_week": kpi_weeks[-1] if kpi_weeks else None,
        },
    )
