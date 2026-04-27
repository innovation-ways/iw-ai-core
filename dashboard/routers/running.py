"""Running tasks page — live view of all active, failed, and recently completed steps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from orch.db.models import (
    Project,
    RunStatus,
    StepRun,
    StepStatus,
    WorkflowStep,
    WorkItem,
)

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session


router = APIRouter()


# ---------------------------------------------------------------------------
# Data containers for template rendering
# ---------------------------------------------------------------------------


@dataclass
class RunningRow:
    """A currently-running step with all display info."""

    project_id: str
    project_name: str
    item_id: str
    step_id: str  # e.g. "S01"
    agent_label: str
    opencode_agent: str | None
    pid: int | None
    started_at: datetime | None
    run_id: int
    # CR-00024: heartbeat-age and pid-alive are surfaced so operators can tell
    # whether the daemon recently confirmed the step is alive (vs. been silent
    # for ages and probably stuck).
    last_heartbeat: datetime | None
    last_heartbeat_age_secs: int | None
    pid_alive: bool | None
    warned_50pct_at: datetime | None
    timeout_secs: int | None


@dataclass
class FailedRow:
    """A step that failed or needs attention."""

    project_id: str
    project_name: str
    item_id: str
    step_id: str
    agent_label: str
    status: str  # step status value string
    error_message: str | None


@dataclass
class CompletedRow:
    """A step completed in the last hour."""

    project_id: str
    item_id: str
    step_id: str
    agent_label: str
    duration_secs: float | None
    completed_at: datetime


# ---------------------------------------------------------------------------
# DB query helpers
# ---------------------------------------------------------------------------


def _query_running_now(db: Session) -> list[RunningRow]:
    """Return all step_runs with status=running, joined to step/item/project."""
    stmt = (
        select(StepRun, WorkflowStep, WorkItem, Project)
        .join(WorkflowStep, StepRun.step_id == WorkflowStep.id)
        .join(
            WorkItem,
            (WorkflowStep.project_id == WorkItem.project_id)
            & (WorkflowStep.work_item_id == WorkItem.id),
        )
        .join(Project, WorkItem.project_id == Project.id)
        .where(StepRun.status == RunStatus.running)
        .order_by(StepRun.started_at)
    )
    rows = []
    now = datetime.now(UTC)
    for run, step, item, project in db.execute(stmt).all():
        last_hb = run.last_heartbeat
        age_secs: int | None = None
        if last_hb is not None:
            hb_aware = last_hb if last_hb.tzinfo else last_hb.replace(tzinfo=UTC)
            age_secs = int((now - hb_aware).total_seconds())
        rows.append(
            RunningRow(
                project_id=project.id,
                project_name=project.display_name,
                item_id=item.id,
                step_id=step.step_id,
                agent_label=step.agent_label,
                opencode_agent=step.opencode_agent,
                pid=run.pid,
                started_at=run.started_at,
                run_id=run.id,
                last_heartbeat=last_hb,
                last_heartbeat_age_secs=age_secs,
                pid_alive=run.pid_alive,
                warned_50pct_at=run.warned_50pct_at,
                timeout_secs=run.timeout_secs,
            )
        )
    return rows


def _query_failed_steps(db: Session, project_id: str | None = None) -> list[FailedRow]:
    """Return steps with status in (failed, needs_fix) across all/one project."""
    stmt = (
        select(WorkflowStep, WorkItem, Project)
        .join(
            WorkItem,
            (WorkflowStep.project_id == WorkItem.project_id)
            & (WorkflowStep.work_item_id == WorkItem.id),
        )
        .join(Project, WorkItem.project_id == Project.id)
        .where(WorkflowStep.status.in_([StepStatus.failed, StepStatus.needs_fix]))
        .order_by(WorkflowStep.project_id, WorkItem.id, WorkflowStep.step_number)
    )
    if project_id is not None:
        stmt = stmt.where(WorkflowStep.project_id == project_id)

    step_rows = db.execute(stmt).all()
    if not step_rows:
        return []

    failed_step_ids = [step.id for step, _, _ in step_rows]

    last_error_map: dict[int, str | None] = {}
    if failed_step_ids:
        from sqlalchemy import func

        last_run_sub = (
            select(
                StepRun.step_id.label("step_id"),
                StepRun.error_message.label("error_message"),
                func.row_number()
                .over(partition_by=StepRun.step_id, order_by=StepRun.run_number.desc())
                .label("rn"),
            )
            .where(StepRun.step_id.in_(failed_step_ids))
            .subquery()
        )
        bulk_runs = db.execute(
            select(last_run_sub.c.step_id, last_run_sub.c.error_message).where(
                last_run_sub.c.rn == 1
            )
        ).all()
        for row in bulk_runs:
            last_error_map[row.step_id] = row.error_message

    rows = []
    for step, item, project in step_rows:
        rows.append(
            FailedRow(
                project_id=project.id,
                project_name=project.display_name,
                item_id=item.id,
                step_id=step.step_id,
                agent_label=step.agent_label,
                status=step.status.value,
                error_message=last_error_map.get(step.id),
            )
        )
    return rows


def _query_recent_completions(db: Session, project_id: str | None = None) -> list[CompletedRow]:
    """Return step_runs completed in the last hour."""
    cutoff = datetime.now(UTC) - timedelta(hours=1)
    stmt = (
        select(StepRun, WorkflowStep, WorkItem)
        .join(WorkflowStep, StepRun.step_id == WorkflowStep.id)
        .join(
            WorkItem,
            (WorkflowStep.project_id == WorkItem.project_id)
            & (WorkflowStep.work_item_id == WorkItem.id),
        )
        .where(
            StepRun.status == RunStatus.completed,
            StepRun.completed_at >= cutoff,
        )
        .order_by(StepRun.completed_at.desc())
        .limit(50)
    )
    if project_id is not None:
        stmt = stmt.where(WorkflowStep.project_id == project_id)

    rows = []
    for run, step, item in db.execute(stmt).all():
        rows.append(
            CompletedRow(
                project_id=item.project_id,
                item_id=item.id,
                step_id=step.step_id,
                agent_label=step.agent_label,
                duration_secs=run.duration_secs,
                completed_at=run.completed_at or datetime.now(UTC),
            )
        )
    return rows


def get_running_count(db: Session) -> int:
    """Count active step_runs for the sidebar badge."""
    stmt = select(StepRun).where(StepRun.status == RunStatus.running)
    return len(db.execute(stmt).all())


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/system/running", response_class=HTMLResponse)
def running_tasks(
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    templates: Jinja2Templates = request.app.state.templates
    running_rows = _query_running_now(db)
    failed_rows = _query_failed_steps(db)
    completed_rows = _query_recent_completions(db)
    return templates.TemplateResponse(
        request,
        "pages/system/running.html",
        {
            "current_project": None,
            "running_count": len(running_rows),
            "running_rows": running_rows,
            "failed_rows": failed_rows,
            "completed_rows": completed_rows,
        },
    )


@router.get("/system/running-fragment", response_class=HTMLResponse)
def running_fragment(
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Partial HTML fragment for SSE-triggered running table refresh."""
    templates: Jinja2Templates = request.app.state.templates
    running_rows = _query_running_now(db)
    return templates.TemplateResponse(
        request,
        "fragments/running_table.html",
        {"running_rows": running_rows},
    )


@router.get("/project/{project_id}/running", response_class=HTMLResponse)
def project_running_tasks(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    templates: Jinja2Templates = request.app.state.templates
    project = db.get(Project, project_id)
    running_rows = _query_running_now(db)
    running_rows = [r for r in running_rows if r.project_id == project_id]
    failed_rows = _query_failed_steps(db, project_id=project_id)
    completed_rows = _query_recent_completions(db, project_id=project_id)
    return templates.TemplateResponse(
        request,
        "pages/system/running.html",
        {
            "current_project": project,
            "running_count": len(running_rows),
            "running_rows": running_rows,
            "failed_rows": failed_rows,
            "completed_rows": completed_rows,
        },
    )
