"""Project selector page and project-scoped page stubs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchStatus,
    Project,
    StepStatus,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter()


@dataclass
class ProjectStats:
    active_batches: int
    running_steps: int
    queued_items: int
    total_items: int


@dataclass
class ProjectWithStats:
    id: str
    display_name: str
    enabled: bool
    stats: ProjectStats


@dataclass
class SystemStatus:
    daemon_running: bool
    active_steps: int


_ACTIVE_BATCH_STATUSES = (
    BatchStatus.approved,
    BatchStatus.executing,
    BatchStatus.paused,
    BatchStatus.publishing,
)


def _project_stats(db: Session, project_id: str) -> ProjectStats:
    active_batches = (
        db.scalar(
            select(func.count(Batch.id)).where(
                Batch.project_id == project_id,
                Batch.status.in_(_ACTIVE_BATCH_STATUSES),
            )
        )
        or 0
    )

    running_steps = (
        db.scalar(
            select(func.count(WorkflowStep.id)).where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.status == StepStatus.in_progress,
            )
        )
        or 0
    )

    queued_items = (
        db.scalar(
            select(func.count())
            .select_from(WorkItem)
            .where(
                WorkItem.project_id == project_id,
                WorkItem.status == WorkItemStatus.approved,
            )
        )
        or 0
    )

    total_items = (
        db.scalar(
            select(func.count())
            .select_from(WorkItem)
            .where(
                WorkItem.project_id == project_id,
            )
        )
        or 0
    )

    return ProjectStats(
        active_batches=active_batches,
        running_steps=running_steps,
        queued_items=queued_items,
        total_items=total_items,
    )


@router.get("/api/nav-projects", response_class=HTMLResponse)
def nav_projects(
    request: Request,
    current: str = "",
    path: str = "/",
    db: Session = Depends(get_db),
) -> Any:
    """Sidebar project navigation fragment (htmx)."""
    projects_db = db.scalars(select(Project).order_by(Project.display_name)).all()
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/nav_projects.html",
        {
            "projects": projects_db,
            "current_project_id": current,
            "current_path": path,
        },
    )


@router.get("/", response_class=HTMLResponse)
def project_selector(request: Request, db: Session = Depends(get_db)) -> Any:
    """Root page — show all registered projects with stats."""
    projects_db = db.scalars(select(Project).order_by(Project.display_name)).all()

    projects = [
        ProjectWithStats(
            id=p.id,
            display_name=p.display_name,
            enabled=p.enabled,
            stats=_project_stats(db, p.id),
        )
        for p in projects_db
    ]

    active_steps = (
        db.scalar(
            select(func.count(WorkflowStep.id)).where(WorkflowStep.status == StepStatus.in_progress)
        )
        or 0
    )
    system_status = SystemStatus(daemon_running=active_steps > 0, active_steps=active_steps)

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/project_selector.html",
        {
            "projects": projects,
            "system_status": system_status,
            "current_project": None,
            "running_count": active_steps,
        },
    )
