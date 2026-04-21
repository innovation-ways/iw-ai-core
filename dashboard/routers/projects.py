"""Project selector page and project-scoped page stubs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from dashboard.dependencies import get_db
from dashboard.utils.project_onboarding import (
    is_valid_project_id,
    safe_resolve_path,
    slugify_project_id,
    validate_repo_root,
)
from orch.db.models import (
    Batch,
    BatchStatus,
    Project,
    StepStatus,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
)
from orch.skills.init_project import init_project

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

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


def _browse_root() -> Path:
    """Return the safe browse root: IW_CORE_BROWSE_ROOT env var or Path.home()."""
    import os

    raw = os.environ.get("IW_CORE_BROWSE_ROOT")
    if raw:
        return Path(raw).expanduser().resolve(strict=False)
    return Path.home()


def _list_directory(path: Path, show_hidden: bool) -> tuple[list[dict[str, Any]], str | None]:
    """List subdirectories of path, skipping broken symlinks. Returns (entries, error)."""
    entries: list[dict[str, Any]] = []
    error: str | None = None
    try:
        for entry in path.iterdir():
            if not show_hidden and entry.name.startswith("."):
                continue
            try:
                resolved = entry.resolve(strict=False)
            except (OSError, RuntimeError):
                continue
            if resolved.is_dir():
                entries.append(
                    {"name": entry.name, "path": str(resolved), "is_symlink": entry.is_symlink()}
                )
    except PermissionError:
        error = f"Permission denied reading '{path}'."
    entries.sort(key=lambda e: e["name"].lower())
    return entries, error


@router.get("/api/projects/new", response_class=HTMLResponse)
def new_project_modal(request: Request) -> Any:
    """Return the new-project modal fragment with empty form values."""
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/new_project_modal.html",
        {
            "form": {"project_id": "", "display_name": "", "repo_root": ""},
            "errors": {},
        },
    )


@router.get("/api/projects/browse", response_class=HTMLResponse)
def browse_directory(request: Request, show_hidden: bool = False) -> Any:
    """Return the directory browser fragment for the given path."""
    safe_root = _browse_root()
    raw_path = request.query_params.get("path")

    templates: Jinja2Templates = request.app.state.templates
    ctx: dict[str, Any] = {
        "current_path": str(safe_root),
        "breadcrumbs": [{"name": "Home", "path": str(safe_root)}],
        "entries": [],
        "show_hidden": show_hidden,
        "safe_root": str(safe_root),
        "error": None,
    }

    try:
        resolved = safe_resolve_path(raw_path, safe_root=safe_root) if raw_path else safe_root
    except ValueError as exc:
        ctx["error"] = str(exc)
        return templates.TemplateResponse(request, "fragments/directory_browser.html", ctx)

    ctx["current_path"] = str(resolved)

    if resolved != safe_root:
        parts: list[dict[str, str]] = []
        try:
            rel = resolved.relative_to(safe_root)
            for i, part in enumerate(rel.parts):
                parts.append({"name": part, "path": str(safe_root / "/".join(rel.parts[: i + 1]))})
        except ValueError:
            pass
        ctx["breadcrumbs"] = [{"name": "Home", "path": str(safe_root)}] + parts

    if not resolved.is_dir():
        ctx["error"] = f"'{resolved}' is not a directory."
        return templates.TemplateResponse(request, "fragments/directory_browser.html", ctx)

    entries, browse_error = _list_directory(resolved, show_hidden)
    if browse_error:
        ctx["error"] = browse_error
    ctx["entries"] = entries

    return templates.TemplateResponse(request, "fragments/directory_browser.html", ctx)


@router.get("/api/projects/slug", response_class=HTMLResponse)
def project_slug(request: Request) -> Response:
    """Return slugified basename of the given path as plain text (or empty body)."""
    safe_root = _browse_root()
    raw_path = request.query_params.get("path", "")

    try:
        resolved = safe_resolve_path(raw_path, safe_root=safe_root)
    except ValueError:
        return Response(status_code=200, content="")

    return Response(status_code=200, content=slugify_project_id(resolved.name))


@router.post("/api/projects/create", response_class=HTMLResponse)
def create_project(
    request: Request,
    project_id: str = Form(""),
    display_name: str = Form(""),
    repo_root: str = Form(""),
    db: Session = Depends(get_db),
) -> Any:
    """Handle form submission to onboard a new project via the UI."""
    templates: Jinja2Templates = request.app.state.templates

    errors: dict[str, str] = {}
    safe_root = _browse_root()

    if not project_id.strip():
        errors["project_id"] = "Project ID is required."
    elif not is_valid_project_id(project_id.strip()):
        errors["project_id"] = (
            "Project ID must be lowercase, start with a letter or digit, "
            "and contain only letters, digits, and hyphens."
        )
    elif (
        db.scalars(select(Project).where(Project.id == project_id.strip()).limit(1)).first()
        is not None
    ):
        errors["project_id"] = f"Project ID '{project_id}' is already in use."

    if not display_name.strip():
        errors["display_name"] = "Display name is required."

    resolved: Path
    try:
        resolved = safe_resolve_path(repo_root, safe_root=safe_root)
    except ValueError as exc:
        errors["repo_root"] = str(exc)
        return templates.TemplateResponse(
            request,
            "fragments/new_project_modal.html",
            {
                "form": {
                    "project_id": project_id,
                    "display_name": display_name,
                    "repo_root": repo_root,
                },
                "errors": errors,
            },
        )

    try:
        validate_repo_root(resolved)
    except ValueError as exc:
        errors["repo_root"] = str(exc)
        return templates.TemplateResponse(
            request,
            "fragments/new_project_modal.html",
            {
                "form": {
                    "project_id": project_id,
                    "display_name": display_name,
                    "repo_root": repo_root,
                },
                "errors": errors,
            },
        )

    try:
        init_project(
            project_id=project_id.strip(),
            repo_path=resolved,
            display_name=display_name.strip(),
            session=db,
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("init_project failed for %s: %s", project_id, exc)
        return templates.TemplateResponse(
            request,
            "fragments/new_project_modal.html",
            {
                "form": {
                    "project_id": project_id,
                    "display_name": display_name,
                    "repo_root": repo_root,
                },
                "errors": {
                    "_global": (
                        f"Project creation failed: {exc}. "
                        "Inspect the repo root and projects.toml "
                        "for leftover artefacts before retrying."
                    )
                },
            },
        )

    return Response(status_code=200, headers={"HX-Redirect": "/"})


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
