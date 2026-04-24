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
    """Summary of a single batch for the dashboard active-batches list."""

    id: str
    status: str
    total_items: int
    completed_items: int
    progress_pct: int


@dataclass
class ActivityEntry:
    """A single daemon_events row for the activity feed."""

    timestamp: datetime
    event_type: str
    entity_id: str | None
    entity_type: str | None
    message: str | None


@dataclass
class GitStatus:
    """Git state for the project repo."""

    branch: str
    unpushed: int
    worktrees: int
    error: str | None = None


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _get_project_or_404(project_id: str, db: Session) -> Project:
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
    project = _get_project_or_404(project_id, db)
    running_count = _running_steps_count(project_id, db)
    active = _active_batches(project_id, db)
    activity = _recent_activity(project_id, db)
    completed_week = _completed_this_week(project_id, db)
    git = _git_status(project.repo_root)

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
        },
    )
