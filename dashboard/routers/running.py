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
    for run, step, item, project in db.execute(stmt).all():
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

    rows = []
    for step, item, project in db.execute(stmt).all():
        # Get error from the most recent run
        last_run = db.scalar(
            select(StepRun)
            .where(StepRun.step_id == step.id)
            .order_by(StepRun.run_number.desc())
            .limit(1)
        )
        rows.append(
            FailedRow(
                project_id=project.id,
                project_name=project.display_name,
                item_id=item.id,
                step_id=step.step_id,
                agent_label=step.agent_label,
                status=step.status.value,
                error_message=last_run.error_message if last_run else None,
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
