"""System-level pages: status, all-active, config."""

from __future__ import annotations

import contextlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchStatus,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
)

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/system")

_TERMINAL_STATUSES = {WorkItemStatus.completed, WorkItemStatus.failed}
_TERMINAL_PHASES = {WorkItemPhase.done}


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class ProjectSummary:
    id: str
    display_name: str
    enabled: bool
    item_count: int
    active_batch_count: int
    branch: str
    unpushed: int
    worktrees: int
    git_error: str | None


@dataclass
class ActiveWorkItem:
    project_id: str
    project_name: str
    id: str
    type: str
    title: str
    status: str
    phase: str
    batch_id: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_branch_and_stats(repo_root: str) -> tuple[str, int, int, str | None]:
    """Return (branch, unpushed, worktrees, error_or_None)."""
    try:
        branch = subprocess.check_output(  # noqa: S603
            ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown", 0, 0, "git unavailable"

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
        worktrees = max(0, len([ln for ln in out.strip().splitlines() if ln]) - 1)

    return branch, unpushed, worktrees, None


def _project_summaries(db: Session) -> list[ProjectSummary]:
    projects = list(db.scalars(select(Project).order_by(Project.display_name)))
    summaries = []
    for p in projects:
        item_count = (
            db.scalar(select(func.count()).select_from(WorkItem).where(WorkItem.project_id == p.id))
            or 0
        )
        active_batch_count = (
            db.scalar(
                select(func.count())
                .select_from(Batch)
                .where(
                    Batch.project_id == p.id,
                    Batch.status.in_([BatchStatus.approved, BatchStatus.executing]),
                )
            )
            or 0
        )
        branch, unpushed, worktrees, git_error = _git_branch_and_stats(p.repo_root)
        summaries.append(
            ProjectSummary(
                id=p.id,
                display_name=p.display_name,
                enabled=p.enabled,
                item_count=item_count,
                active_batch_count=active_batch_count,
                branch=branch,
                unpushed=unpushed,
                worktrees=worktrees,
                git_error=git_error,
            )
        )
    return summaries


def _all_active_items(db: Session) -> dict[str, list[ActiveWorkItem]]:
    """Return active work items grouped by project_id."""
    from orch.db.models import BatchItem

    stmt = (
        select(WorkItem)
        .where(
            WorkItem.status.notin_([WorkItemStatus.completed, WorkItemStatus.failed]),
            WorkItem.phase.notin_([WorkItemPhase.done]),
        )
        .order_by(WorkItem.project_id, WorkItem.created_at.desc())
    )
    items = list(db.scalars(stmt))

    # Fetch project names
    pids = {i.project_id for i in items}
    project_names: dict[str, str] = {}
    if pids:
        projects = db.scalars(select(Project).where(Project.id.in_(pids))).all()
        project_names = {p.id: p.display_name for p in projects}

    # Fetch batch membership
    batch_map: dict[tuple[str, str], str] = {}
    if items:
        bi_rows = db.execute(
            select(BatchItem.project_id, BatchItem.work_item_id, BatchItem.batch_id).where(
                BatchItem.project_id.in_(pids)
            )
        ).all()
        for row in bi_rows:
            batch_map[(row.project_id, row.work_item_id)] = row.batch_id

    grouped: dict[str, list[ActiveWorkItem]] = {}
    for item in items:
        pid = item.project_id
        if pid not in grouped:
            grouped[pid] = []
        grouped[pid].append(
            ActiveWorkItem(
                project_id=pid,
                project_name=project_names.get(pid, pid),
                id=item.id,
                type=item.type.value,
                title=item.title,
                status=item.status.value,
                phase=item.phase.value,
                batch_id=batch_map.get((pid, item.id)),
            )
        )
    return grouped


def _load_projects_toml() -> str:
    """Load projects.toml content for the config viewer."""
    candidates = [
        Path("projects.toml"),
        Path(__file__).resolve().parents[2] / "projects.toml",
    ]
    for p in candidates:
        if p.exists():
            return p.read_text()
    return ""


def _safe_config_display(config: dict[str, Any]) -> dict[str, Any]:
    """Mask sensitive keys in config dict for display."""
    sensitive = {"password", "secret", "token", "key", "credential"}
    out: dict[str, Any] = {}
    for k, v in config.items():
        if any(s in k.lower() for s in sensitive):
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = _safe_config_display(v)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/status", response_class=HTMLResponse)
def system_status(request: Request, db: Session = Depends(get_db)) -> Any:
    project_summaries = _project_summaries(db)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/system/status.html",
        {
            "current_project": None,
            "running_count": 0,
            "project_summaries": project_summaries,
        },
    )


@router.get("/all-active", response_class=HTMLResponse)
def system_all_active(request: Request, db: Session = Depends(get_db)) -> Any:
    grouped = _all_active_items(db)
    total = sum(len(v) for v in grouped.values())
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/system/all_active.html",
        {
            "current_project": None,
            "running_count": 0,
            "grouped_items": grouped,
            "total": total,
        },
    )


@router.get("/config", response_class=HTMLResponse)
def system_config(request: Request, db: Session = Depends(get_db)) -> Any:
    projects_toml_raw = _load_projects_toml()

    # Parse env summary (non-sensitive)
    import os

    env_summary: dict[str, str] = {}
    for key in sorted(os.environ):
        if key.startswith("IW_CORE_"):
            val = os.environ[key]
            sensitive = any(s in key.lower() for s in ("password", "secret", "token", "key"))
            env_summary[key] = "***" if sensitive else val

    # Per-project configs
    projects = list(db.scalars(select(Project).order_by(Project.display_name)))
    project_configs = [
        {
            "id": p.id,
            "display_name": p.display_name,
            "config": _safe_config_display(p.config or {}),
        }
        for p in projects
    ]

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/system/config.html",
        {
            "current_project": None,
            "running_count": 0,
            "projects_toml": projects_toml_raw,
            "env_summary": env_summary,
            "project_configs": project_configs,
        },
    )
