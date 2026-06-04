"""System-level pages: status, all-active, config, docs-view."""

from __future__ import annotations

import contextlib
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from markdown import markdown
from markupsafe import Markup
from sqlalchemy import func, select

from dashboard.dependencies import get_db
from dashboard.utils.ttl_cache import TTLCache
from orch.cli.daemon_commands import get_pid_file_path, is_process_alive, read_pid
from orch.db.models import (
    Batch,
    BatchStatus,
    DaemonEvent,
    Project,
    StepStatus,
    WorkflowStep,
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
class DaemonStatus:
    """Daemon liveness and operational statistics.

    Attributes:
        is_running: True when the daemon PID is alive.
        pid: OS process ID of the daemon, or None when not running.
        uptime_secs: Seconds since the last daemon_started event, or None.
        last_poll_at: Timestamp of the most recent daemon_poll event.
        poll_count: Total number of daemon poll events recorded.
        running_steps: Count of steps currently in_progress across all projects.
        active_batches: Count of batches in approved or executing state.
    """

    is_running: bool
    pid: int | None
    uptime_secs: float | None
    last_poll_at: datetime | None
    poll_count: int
    running_steps: int
    active_batches: int


@dataclass
class ProjectSummary:
    """Per-project summary row for the system status page.

    Attributes:
        id: Project identifier.
        display_name: Human-readable project name.
        enabled: Whether the project is enabled in the registry.
        item_count: Total work items in the project.
        active_batch_count: Batches in approved or executing state.
        branch: Currently checked-out branch in the repo.
        unpushed: Commits ahead of the remote tracking branch.
        worktrees: Number of active agent worktrees.
        git_error: Non-None when git commands failed.
    """

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
    """A non-completed work item for the all-active view.

    Attributes:
        project_id: Owning project identifier.
        project_name: Human-readable project display name.
        id: Work item identifier.
        type: Work item type string.
        title: Human-readable work item title.
        status: Current status string.
        phase: Current phase string.
        batch_id: Batch identifier if the item belongs to a batch, or None.
    """

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


def _daemon_status(db: Session) -> DaemonStatus:
    """Read daemon liveness from PID file and operational stats from DB."""
    pid_file = get_pid_file_path()
    pid = read_pid(pid_file)
    is_running = pid is not None and is_process_alive(pid)

    # Uptime: time since most recent daemon_started event
    started_event = db.scalar(
        select(DaemonEvent)
        .where(DaemonEvent.event_type == "daemon_started")
        .order_by(DaemonEvent.created_at.desc())
        .limit(1)
    )
    uptime_secs: float | None = None
    if is_running and started_event:
        uptime_secs = (datetime.now(UTC) - started_event.created_at).total_seconds()

    # Last poll and total poll count
    poll_event = db.scalar(
        select(DaemonEvent)
        .where(DaemonEvent.event_type == "daemon_poll")
        .order_by(DaemonEvent.created_at.desc())
        .limit(1)
    )
    poll_count = (
        db.scalar(select(func.count(DaemonEvent.id)).where(DaemonEvent.event_type == "daemon_poll"))
        or 0
    )

    running_steps = (
        db.scalar(
            select(func.count(WorkflowStep.id)).where(WorkflowStep.status == StepStatus.in_progress)
        )
        or 0
    )
    active_batches = (
        db.scalar(
            select(func.count())
            .select_from(Batch)
            .where(Batch.status.in_([BatchStatus.approved, BatchStatus.executing]))
        )
        or 0
    )

    return DaemonStatus(
        is_running=is_running,
        pid=pid if is_running else None,
        uptime_secs=uptime_secs,
        last_poll_at=poll_event.created_at if poll_event else None,
        poll_count=poll_count,
        running_steps=running_steps,
        active_batches=active_batches,
    )


_GIT_STATS_CACHE_TTL = float(os.environ.get("IW_CORE_GIT_STATS_CACHE_TTL", "15"))
_git_stats_cache = TTLCache[tuple[str, int, int, str | None]](ttl=_GIT_STATS_CACHE_TTL)


def _git_branch_and_stats(repo_root: str) -> tuple[str, int, int, str | None]:
    """Return (branch, unpushed, worktrees, error_or_None)."""
    cached = _git_stats_cache.get(repo_root)
    if cached is not None:
        return cached

    result = _git_branch_and_stats_impl(repo_root)
    _git_stats_cache.set(repo_root, result)
    return result


def _git_branch_and_stats_impl(repo_root: str) -> tuple[str, int, int, str | None]:
    """Uncached implementation of _git_branch_and_stats."""
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
    """Render the system status page with daemon health and per-project summaries.

    Args:
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        Full HTML system status page.
    """
    project_summaries = _project_summaries(db)
    daemon = _daemon_status(db)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/system/status.html",
        {
            "current_project": None,
            "running_count": 0,
            "project_summaries": project_summaries,
            "daemon": daemon,
        },
    )


@router.get("/all-active", response_class=HTMLResponse)
def system_all_active(request: Request, db: Session = Depends(get_db)) -> Any:
    """Render the all-active work items page grouped by project.

    Args:
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        Full HTML page with all non-completed, non-failed work items.
    """
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
    """Render the system configuration page.

    Displays masked environment variables, projects.toml contents, and per-project configs.

    Args:
        request: The current FastAPI request.
        db: Active database session.

    Returns:
        Full HTML configuration page.
    """
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


# ---------------------------------------------------------------------------
# Docs view  (CR-00042 + CR-00044: subdirectory support)
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOCS_DIR = _REPO_ROOT / "docs"

# Curated CLAUDE.md files surfaced via the docs viewer (URL key = repo-relative path)
_CLAUDE_MD_PATHS: list[str] = [
    "orch/rag/CLAUDE.md",
    "orch/CLAUDE.md",
    "dashboard/CLAUDE.md",
    "executor/CLAUDE.md",
]

# Precompute the URL-key → repo-relative-path map at module load.
# - docs/ files: key = path relative to docs/ with .md suffix stripped
#   (e.g. docs/implementation/00_INDEX.md → "implementation/00_INDEX")
#   This preserves every flat-form URL from CR-00042.
# - curated CLAUDE.md files: key = repo-relative path including .md
#   (e.g. "orch/rag/CLAUDE.md" → "orch/rag/CLAUDE.md")
_DOC_URL_MAP: dict[str, str] = {}

# Allowed base directories for resolved-path defence-in-depth check
_ALLOWED_BASE_DIRS: list[Path] = [_DOCS_DIR]

for _p in _DOCS_DIR.rglob("*.md"):
    _url_key = _p.relative_to(_DOCS_DIR).with_suffix("").as_posix()
    _repo_rel = _p.relative_to(_REPO_ROOT).as_posix()
    _DOC_URL_MAP[_url_key] = _repo_rel

for _claude_rel in _CLAUDE_MD_PATHS:
    _claude_path = _REPO_ROOT / _claude_rel
    if _claude_path.is_file():
        _DOC_URL_MAP[_claude_rel] = _claude_rel
        _ALLOWED_BASE_DIRS.append((_REPO_ROOT / _claude_rel).parent.resolve())


def _extract_h1_title(content: str) -> str:
    """Return the first level-1 ATX heading text from a markdown string, or None."""

    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return ""


@router.get("/docs/{doc_path:path}", response_class=HTMLResponse)
def system_docs_view(doc_path: str, request: Request) -> HTMLResponse:
    """Render a docs/ .md file (or curated CLAUDE.md) as HTML.

    The doc_path is validated against a precomputed allow-list map, then
    defended by resolved-path checks inside allowed base directories.
    The page title is derived from the document's first H1 heading.
    """
    # --- Step 1: structural validation ---
    if not doc_path or doc_path.startswith("/"):
        raise HTTPException(status_code=404, detail="Document not found")
    _pp = PurePosixPath(doc_path)
    if any(p in (".", "..") for p in _pp.parts):
        raise HTTPException(status_code=404, detail="Document not found")

    # --- Step 2: allow-list lookup ---
    mapped = _DOC_URL_MAP.get(doc_path)
    if mapped is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # --- Step 3: resolved-path defence-in-depth ---
    candidate = (_REPO_ROOT / mapped).resolve()
    if not any(candidate.is_relative_to(base) for base in _ALLOWED_BASE_DIRS):
        raise HTTPException(status_code=404, detail="Document not found")

    # --- Step 4: require a .md file ---
    if candidate.suffix != ".md" or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Document not found")

    # --- Step 5: read and render ---
    content = candidate.read_text(encoding="utf-8")
    rendered = markdown(content, extensions=["toc", "tables", "fenced_code"])
    doc_title = _extract_h1_title(content) or PurePosixPath(doc_path).stem.replace("_", " ")

    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/system/docs_view.html",
        {
            "doc_slug": doc_path,
            "doc_title": doc_title,
            "rendered_html": Markup(rendered),  # noqa: S704  # nosec B704 — rendered from an allow-listed repo .md file (see Steps 1-4), not user input
        },
    )
