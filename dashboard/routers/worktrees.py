"""Worktree health page — git status of all active agent worktrees."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from dashboard.utils.ttl_cache import TTLCache
from orch.daemon import worktree_compose, worktree_reaper
from orch.db.models import (
    BatchItem,
    BatchItemStatus,
    DaemonEvent,
    Project,
    RunStatus,
    StepRun,
    WorkflowStep,
)
from orch.db.session import SessionLocal

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/system")

_ACTIVE_STATUSES = {
    BatchItemStatus.setting_up,
    BatchItemStatus.executing,
    BatchItemStatus.merging,
}

_BADGE_CACHE_TTL = float(os.environ.get("IW_CORE_BADGE_CACHE_TTL", "30"))
_badge_cache = TTLCache[tuple[int, float]](ttl=_BADGE_CACHE_TTL)


def _compute_dirty_count() -> tuple[int, float]:
    """Compute dirty worktree count by enumerating all project roots and active batch items.

    Opens its own DB session so the cache fill is independent of the request-scoped session.
    Returns (dirty_count, timestamp).
    """
    session = SessionLocal()
    try:
        dirty = 0
        projects = session.execute(select(Project).where(Project.enabled.is_(True))).scalars().all()
        for project in projects:
            label, _, _ = _git_status(project.repo_root)
            if label == "dirty":
                dirty += 1

        for bi in (
            session.execute(select(BatchItem).where(BatchItem.status.in_(list(_ACTIVE_STATUSES))))
            .scalars()
            .all()
        ):
            wt = bi.worktree_info or {}
            path = wt.get("path")
            if path:
                label, _, _ = _git_status(path)
                if label == "dirty":
                    dirty += 1

        return dirty, datetime.now(UTC).timestamp()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Git helpers (run at request time — acceptable latency for a health page)
# ---------------------------------------------------------------------------


_WORKTREE_CACHE_TTL = float(os.environ.get("IW_CORE_GIT_STATS_CACHE_TTL", "15"))
_git_status_cache = TTLCache[tuple[str, int, int]](ttl=_WORKTREE_CACHE_TTL)
_commits_ahead_cache = TTLCache[int](ttl=_WORKTREE_CACHE_TTL)
_current_branch_cache = TTLCache[str](ttl=_WORKTREE_CACHE_TTL)


def _git_status(path: str) -> tuple[str, int, int]:
    """Return (label, modified_count, untracked_count) for a worktree path.

    Labels: clean | dirty | untracked | no_path | error | timeout
    """
    cached = _git_status_cache.get(path)
    if cached is not None:
        return cached
    result = _git_status_impl(path)
    _git_status_cache.set(path, result)
    return result


def _git_status_impl(path: str) -> tuple[str, int, int]:
    """Uncached git status implementation."""
    try:
        r = subprocess.run(  # noqa: S603
            ["git", "-C", path, "status", "--porcelain"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            return "error", 0, 0
        lines = [ln for ln in r.stdout.splitlines() if ln]
        if not lines:
            return "clean", 0, 0
        untracked = sum(1 for ln in lines if ln.startswith("??"))
        modified = len(lines) - untracked
        label = "dirty" if modified else "untracked"
        return label, modified, untracked
    except FileNotFoundError:
        return "no_path", 0, 0
    except subprocess.TimeoutExpired:
        return "timeout", 0, 0
    except Exception:  # noqa: BLE001
        return "error", 0, 0


def _commits_ahead(path: str) -> int:
    """Return commits HEAD is ahead of main. -1 on error."""
    cached = _commits_ahead_cache.get(path)
    if cached is not None:
        return cached
    result = _commits_ahead_impl(path)
    _commits_ahead_cache.set(path, result)
    return result


def _commits_ahead_impl(path: str) -> int:
    """Uncached implementation."""
    with contextlib.suppress(Exception):
        r = subprocess.run(  # noqa: S603
            ["git", "-C", path, "rev-list", "main..HEAD", "--count"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            return int(r.stdout.strip())
    return -1


def _current_branch(path: str) -> str:
    """Return the checked-out branch name for *path*. Returns '—' on error."""
    cached = _current_branch_cache.get(path)
    if cached is not None:
        return cached
    result = _current_branch_impl(path)
    _current_branch_cache.set(path, result)
    return result


def _current_branch_impl(path: str) -> str:
    """Uncached implementation."""
    with contextlib.suppress(Exception):
        r = subprocess.run(  # noqa: S603
            ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    return "—"


def _git_worktrees(repo_root: str) -> list[dict[str, str]]:
    """Return agent worktrees for *repo_root* (skips the main worktree).

    Each dict: {path, branch}.
    """
    try:
        r = subprocess.run(  # noqa: S603
            ["git", "-C", repo_root, "worktree", "list", "--porcelain"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            return []
        entries: list[dict[str, str]] = []
        current: dict[str, str] = {}
        for line in r.stdout.splitlines():
            if line.startswith("worktree "):
                if current:
                    entries.append(current)
                current = {"path": line[9:], "branch": "—"}
            elif line.startswith("branch "):
                current["branch"] = line[7:].removeprefix("refs/heads/")
        if current:
            entries.append(current)
        return entries[1:]  # skip main worktree
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# File detail helpers
# ---------------------------------------------------------------------------


@dataclass
class FileEntry:
    filepath: str  # relative path as reported by git
    xy: str  # raw XY status code (e.g. " M", "??", "D ")
    category: str  # "modified" | "untracked"
    display_dir: str  # directory portion with trailing slash, or ""
    display_name: str  # filename only
    badge: str  # single-char label: M, D, A, R, ?


def _parse_git_files(path: str) -> list[FileEntry]:
    """Parse git status --porcelain=v1 into FileEntry list sorted by path."""
    try:
        r = subprocess.run(  # noqa: S603
            ["git", "-C", path, "status", "--porcelain=v1"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return []
    except Exception:  # noqa: BLE001
        return []

    entries: list[FileEntry] = []
    for line in r.stdout.splitlines():
        if len(line) < 4:
            continue
        xy = line[:2]
        filepath = line[3:]
        # Renames: "old -> new" — take the new name
        if " -> " in filepath:
            filepath = filepath.split(" -> ", 1)[1]

        if "/" in filepath:
            display_dir = filepath.rsplit("/", 1)[0] + "/"
            display_name = filepath.rsplit("/", 1)[1]
        else:
            display_dir = ""
            display_name = filepath

        category = "untracked" if xy == "??" else "modified"
        badge = "?" if xy == "??" else xy[0] if xy[0] != " " else xy[1]

        entries.append(
            FileEntry(
                filepath=filepath,
                xy=xy,
                category=category,
                display_dir=display_dir,
                display_name=display_name,
                badge=badge,
            )
        )

    entries.sort(key=lambda e: (e.category, e.filepath))
    return entries


def _validate_path(path: str, db: Session) -> bool:
    """Return True if path is a known project root or active agent worktree."""
    project_roots = set(
        db.execute(select(Project.repo_root).where(Project.enabled.is_(True))).scalars().all()
    )
    if path in project_roots:
        return True
    wt_infos = (
        db.execute(
            select(BatchItem.worktree_info).where(BatchItem.status.in_(list(_ACTIVE_STATUSES)))
        )
        .scalars()
        .all()
    )
    return any(isinstance(w, dict) and w.get("path") == path for w in wt_infos)


# ---------------------------------------------------------------------------
# Data containers (table)
# ---------------------------------------------------------------------------


@dataclass
class WorktreeRow:
    project_id: str
    item_id: str
    batch_id: str
    branch: str
    batch_status: str
    path: str
    git_label: str  # clean | dirty | untracked | no_path | error | timeout | orphaned
    modified: int
    untracked: int
    ahead: int
    is_orphan: bool
    checked_at: datetime
    container_status: Literal["running", "stopped", "missing", "n/a"] = "n/a"
    db_port: int | None = None
    app_port: int | None = None
    classification: Literal["active", "stale", "orphan", "malformed", "n/a"] = "n/a"
    batch_item_pk: int | None = None  # DB PK for teardown
    # CR-00024: per-worktree heartbeat surfacing — populated when there is a
    # running StepRun for the work item; otherwise None and rendered as "—".
    last_heartbeat_age_secs: int | None = None
    pid_alive: bool | None = None
    warned_50pct_at: datetime | None = None


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------


def _container_status_for_batch_item(
    batch_item_pk: int,
    findings: dict[int, worktree_reaper.ReaperFinding],
    db: Session,
) -> tuple[
    Literal["running", "stopped", "missing"],
    Literal["active", "stale", "orphan", "malformed"],
]:
    """Determine container status and classification for a batch item from scan findings.

    Returns (container_status, classification).
    """
    finding = findings.get(batch_item_pk)
    if finding is None:
        return "missing", "malformed"

    classification = worktree_reaper.classify(finding, db)
    if finding.container_id:
        if worktree_compose.is_alive(str(batch_item_pk)):
            return "running", classification
        return "stopped", classification
    return "missing", classification


def _running_step_heartbeats(
    db: Session,
) -> dict[tuple[str, str], tuple[int | None, bool | None, datetime | None]]:
    """CR-00024: bulk-load heartbeat info for all currently-running StepRuns.

    Returns a mapping ``(project_id, work_item_id) -> (age_secs, pid_alive,
    warned_50pct_at)`` so callers can patch heartbeat columns onto worktree
    rows with a single dict lookup. Items without a running step are absent
    from the map.
    """
    now = datetime.now(UTC)
    stmt = (
        select(StepRun, WorkflowStep)
        .join(WorkflowStep, StepRun.step_id == WorkflowStep.id)
        .where(StepRun.status == RunStatus.running)
    )
    out: dict[tuple[str, str], tuple[int | None, bool | None, datetime | None]] = {}
    for run, step in db.execute(stmt).all():
        age_secs: int | None = None
        if run.last_heartbeat is not None:
            hb = (
                run.last_heartbeat
                if run.last_heartbeat.tzinfo
                else run.last_heartbeat.replace(tzinfo=UTC)
            )
            age_secs = int((now - hb).total_seconds())
        out[(step.project_id, step.work_item_id)] = (age_secs, run.pid_alive, run.warned_50pct_at)
    return out


def _collect_worktrees(db: Session) -> list[WorktreeRow]:
    """Query active batch items and detect orphaned worktrees on disk.

    Rows are ordered: project main checkouts first, then agent worktrees,
    then orphans.
    """
    now = datetime.now(UTC)
    rows: list[WorktreeRow] = []
    known_paths: set[str] = set()
    heartbeats = _running_step_heartbeats(db)

    findings = worktree_reaper.scan()
    findings_by_bi: dict[int, worktree_reaper.ReaperFinding] = {}
    for f in findings:
        if f.batch_item_id is not None:
            with contextlib.suppress(ValueError, TypeError):
                findings_by_bi[int(f.batch_item_id)] = f

    projects = db.execute(select(Project).where(Project.enabled.is_(True))).scalars().all()

    for project in projects:
        project_path = project.repo_root
        known_paths.add(project_path)
        label, mod, untr = _git_status(project_path)
        rows.append(
            WorktreeRow(
                project_id=project.id,
                item_id="(main)",
                batch_id="—",
                branch=_current_branch(project_path),
                batch_status="main",
                path=project_path,
                git_label=label,
                modified=mod,
                untracked=untr,
                ahead=-1,
                is_orphan=False,
                checked_at=now,
            )
        )

    stmt = select(BatchItem).where(BatchItem.status.in_(list(_ACTIVE_STATUSES)))
    for bi in db.execute(stmt).scalars().all():
        wt = bi.worktree_info or {}
        wt_path: str | None = wt.get("path")
        branch: str = wt.get("branch", "—")

        if wt_path:
            known_paths.add(wt_path)

        if wt_path:
            label, mod, untr = _git_status(wt_path)
            ahead = _commits_ahead(wt_path)
        else:
            label, mod, untr, ahead = "no_path", 0, 0, -1

        container_status: Literal["running", "stopped", "missing", "n/a"] = "n/a"
        classification: Literal["active", "stale", "orphan", "malformed", "n/a"] = "n/a"
        db_port: int | None = bi.worktree_db_port
        app_port: int | None = bi.worktree_app_port

        finding = findings_by_bi.get(bi.id)
        if finding is not None:
            classification = worktree_reaper.classify(finding, db)
            if worktree_compose.is_alive(str(bi.id)):
                container_status = "running"
            else:
                container_status = "stopped" if finding.container_id else "missing"

        hb = heartbeats.get((bi.project_id, bi.work_item_id))
        last_hb_age, hb_alive, hb_warned = hb if hb else (None, None, None)

        rows.append(
            WorktreeRow(
                project_id=bi.project_id,
                item_id=bi.work_item_id,
                batch_id=bi.batch_id,
                branch=branch,
                batch_status=bi.status.value,
                path=wt_path or "—",
                git_label=label,
                modified=mod,
                untracked=untr,
                ahead=ahead,
                is_orphan=False,
                checked_at=now,
                container_status=container_status,
                db_port=db_port,
                app_port=app_port,
                classification=classification,
                batch_item_pk=bi.id,
                last_heartbeat_age_secs=last_hb_age,
                pid_alive=hb_alive,
                warned_50pct_at=hb_warned,
            )
        )

    for project in projects:
        for wt in _git_worktrees(project.repo_root):
            if wt["path"] in known_paths:
                continue
            if not wt["branch"].startswith("agent/"):
                continue
            label, mod, untr = _git_status(wt["path"])
            rows.append(
                WorktreeRow(
                    project_id=project.id,
                    item_id="—",
                    batch_id="—",
                    branch=wt["branch"],
                    batch_status="orphaned",
                    path=wt["path"],
                    git_label="orphaned",
                    modified=mod,
                    untracked=untr,
                    ahead=_commits_ahead(wt["path"]),
                    is_orphan=True,
                    checked_at=now,
                )
            )

    orphan_findings = [f for f in findings if f.classification == "orphan"]
    for f in orphan_findings:
        rows.append(
            WorktreeRow(
                project_id=f.project_id or "—",
                item_id="—",
                batch_id="—",
                branch="—",
                batch_status="container-orphan",
                path="—",
                git_label="n/a",
                modified=0,
                untracked=0,
                ahead=-1,
                is_orphan=True,
                checked_at=now,
                container_status="stopped",
                classification="orphan",
                batch_item_pk=int(f.batch_item_id) if f.batch_item_id else None,
            )
        )

    return rows


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/nav/worktree-badge", response_class=HTMLResponse)
def nav_worktree_badge(request: Request, _db: Session = Depends(get_db)) -> Any:
    """Sidebar badge — red dot when any worktree is dirty.

    Served from an in-memory TTL cache (30 s default). On cache miss the
    compute fn runs and stores the result; subsequent calls within TTL are
    constant-time (zero subprocess, zero DB queries).
    """
    templates: Jinja2Templates = request.app.state.templates

    cached = _badge_cache.get("")
    if cached is not None:
        dirty, _ = cached
    else:
        dirty, _ = _compute_dirty_count()
        _badge_cache.set("", (dirty, datetime.now(UTC).timestamp()))

    return templates.TemplateResponse(
        request, "fragments/worktree_nav_badge.html", {"dirty": dirty}
    )


@router.get("/worktrees", response_class=HTMLResponse)
def worktrees_page(request: Request, db: Session = Depends(get_db)) -> Any:
    """Full worktree health page."""
    templates: Jinja2Templates = request.app.state.templates
    worktrees = _collect_worktrees(db)
    return templates.TemplateResponse(
        request,
        "pages/system/worktrees.html",
        {
            "current_project": None,
            "worktrees": worktrees,
        },
    )


@router.get("/worktrees/table", response_class=HTMLResponse)
def worktrees_table(request: Request, db: Session = Depends(get_db)) -> Any:
    """htmx fragment — auto-refresh every 30 s."""
    templates: Jinja2Templates = request.app.state.templates
    worktrees = _collect_worktrees(db)
    return templates.TemplateResponse(
        request,
        "fragments/worktree_table.html",
        {"worktrees": worktrees},
    )


@router.get("/worktrees/files", response_class=HTMLResponse)
def worktrees_files(request: Request, path: str, db: Session = Depends(get_db)) -> Any:
    """Return the file-detail panel for a specific worktree path."""
    if not _validate_path(path, db):
        raise HTTPException(status_code=400, detail="Unknown worktree path")
    templates: Jinja2Templates = request.app.state.templates
    entries = _parse_git_files(path)
    modified = [e for e in entries if e.category == "modified"]
    untracked = [e for e in entries if e.category == "untracked"]
    return templates.TemplateResponse(
        request,
        "fragments/worktree_files.html",
        {
            "path": path,
            "branch": _current_branch(path),
            "modified": modified,
            "untracked": untracked,
            "error": None,
        },
    )


@router.post("/worktrees/commit", response_class=HTMLResponse)
async def worktrees_commit(
    request: Request,
    path: str = Form(...),
    message: str = Form(...),
    files: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
) -> Any:
    """Stage selected files and create a git commit."""
    templates: Jinja2Templates = request.app.state.templates

    def _render_files(error: str) -> Any:
        entries = _parse_git_files(path)
        return templates.TemplateResponse(
            request,
            "fragments/worktree_files.html",
            {
                "path": path,
                "branch": _current_branch(path),
                "modified": [e for e in entries if e.category == "modified"],
                "untracked": [e for e in entries if e.category == "untracked"],
                "error": error,
                "prev_message": message,
            },
        )

    if not _validate_path(path, db):
        raise HTTPException(status_code=400, detail="Unknown worktree path")

    if not files:
        return _render_files("No files selected.")

    if not message.strip():
        return _render_files("Commit message is required.")

    # Guard against path traversal in filenames
    for f in files:
        if ".." in f or f.startswith("/"):
            return _render_files(f"Invalid file path: {f}")

    # git add
    add = subprocess.run(  # noqa: S603
        ["git", "-C", path, "add", "--", *files],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=30,
    )
    if add.returncode != 0:
        return _render_files(f"git add failed: {add.stderr.strip()}")

    # git commit (with one automatic retry if pre-commit hooks modify files)
    commit = subprocess.run(  # noqa: S603
        ["git", "-C", path, "commit", "-m", message.strip()],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=60,
    )
    if commit.returncode != 0:
        # Check whether pre-commit hooks modified the files (working tree now
        # differs from the index).  If so, re-stage and retry once.
        hook_modified = subprocess.run(  # noqa: S603
            ["git", "-C", path, "diff", "--name-only", "--", *files],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )
        if hook_modified.returncode == 0 and hook_modified.stdout.strip():
            # Hooks fixed files in the working tree — re-stage and retry
            subprocess.run(  # noqa: S603
                ["git", "-C", path, "add", "--", *files],  # noqa: S607
                capture_output=True,
                timeout=30,
            )
            commit = subprocess.run(  # noqa: S603
                ["git", "-C", path, "commit", "-m", message.strip()],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=60,
            )

    if commit.returncode != 0:
        # Unstage what we added so we don't leave things half-staged
        subprocess.run(  # noqa: S603
            ["git", "-C", path, "reset", "HEAD", "--", *files],  # noqa: S607
            capture_output=True,
            timeout=10,
        )
        return _render_files(f"git commit failed: {commit.stderr.strip()}")

    response = templates.TemplateResponse(
        request,
        "fragments/worktree_files.html",
        {
            "path": path,
            "branch": _current_branch(path),
            "modified": [],
            "untracked": [],
            "error": None,
            "commit_success": {
                "message": message.strip(),
                "file_count": len(files),
                "output": commit.stdout.strip(),
            },
        },
    )
    # Tell the worktree table to refresh immediately
    response.headers["HX-Trigger"] = "worktree-committed"
    return response


@router.post("/worktrees/prune", response_class=HTMLResponse)
def worktrees_prune(request: Request, db: Session = Depends(get_db)) -> Any:
    """Run `git worktree prune` on all enabled projects and refresh the table."""
    projects = db.scalars(select(Project).where(Project.enabled.is_(True))).all()
    errors: list[str] = []
    for project in projects:
        r = subprocess.run(  # noqa: S603
            ["git", "-C", project.repo_root, "worktree", "prune"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            errors.append(f"{project.id}: {r.stderr.strip()}")

    templates: Jinja2Templates = request.app.state.templates
    worktrees = _collect_worktrees(db)
    return templates.TemplateResponse(
        request,
        "fragments/worktree_table.html",
        {"worktrees": worktrees, "prune_errors": errors},
    )


@router.get("/worktrees/{batch_item_id}/logs/stream")
async def worktree_logs_stream(
    batch_item_id: str,
    request: Request,
) -> StreamingResponse:
    """Stream docker logs for the compose stack of a batch item via SSE."""

    async def _log_generator() -> AsyncGenerator[str, None]:
        try:
            compose_project_name = f"iwcore-{batch_item_id.lower().replace('_', '-')}"
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "logs",
                "-f",
                "--tail",
                "100",
                "--details",
                "-t",
                "--filter",
                f"label=com.docker.compose.project={compose_project_name}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            stdout = proc.stdout
            if stdout is None:
                return
            while True:
                if request.is_disconnected():
                    return
                try:
                    line = await asyncio.wait_for(
                        stdout.readline(),
                        timeout=1.0,
                    )
                except TimeoutError:
                    yield ": ping\n\n"
                else:
                    if not line:
                        break

                    data = line.decode("utf-8", errors="replace")
                    yield f"data: {json.dumps({'line': data})}\n\n"

        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"

    return StreamingResponse(
        _log_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/worktrees/{batch_item_id}/teardown", response_class=HTMLResponse)
def worktree_teardown(
    batch_item_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Force teardown of a worktree's compose stack and return refreshed table."""
    bi = db.get(BatchItem, int(batch_item_id))
    if bi is None:
        raise HTTPException(status_code=404, detail="Batch item not found")

    compose_path: Path | None = None
    wt_info = bi.worktree_info or {}
    wt_path = wt_info.get("path")
    if wt_path:
        iw_dir = Path(wt_path) / ".iw"
        rendered_compose = iw_dir / f"docker-compose-{batch_item_id}.yml"
        if rendered_compose.is_file():
            compose_path = rendered_compose

    worktree_compose.down(batch_item_id, compose_path)

    event = DaemonEvent(
        project_id=bi.project_id,
        event_type="worktree_compose",
        entity_id=batch_item_id,
        entity_type="batch_item",
        message="Force teardown triggered by operator",
        event_metadata={
            "phase": "down",
            "trigger": "operator_force",
            "batch_item_id": batch_item_id,
        },
    )
    db.add(event)
    db.commit()

    templates: Jinja2Templates = request.app.state.templates
    worktrees = _collect_worktrees(db)
    return templates.TemplateResponse(
        request,
        "fragments/worktree_table.html",
        {"worktrees": worktrees, "prune_errors": []},
    )


@router.post("/worktrees/orphan/{container_id}/teardown", response_class=HTMLResponse)
def worktree_orphan_teardown(
    container_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Any:
    """Tear down an orphan container (no matching BatchItem) by container_id."""
    import json as json_mod

    try:
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "docker",
                "inspect",
                container_id,
                "--format",
                "{{json .Config.Labels}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        labels_raw = result.stdout.strip()
        if not labels_raw:
            raise HTTPException(status_code=404, detail="Container has no labels")
        labels = json_mod.loads(labels_raw)
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=404, detail="Container not found") from exc
    except json_mod.JSONDecodeError as exc:
        raise HTTPException(status_code=404, detail="Could not parse container labels") from exc

    batch_item_label = labels.get("iwcore.batch_item")
    if not batch_item_label:
        raise HTTPException(status_code=404, detail="Container has no iwcore.batch_item label")

    try:
        batch_item_pk = int(batch_item_label)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Invalid batch_item label: {batch_item_label}",
        ) from exc

    worktree_compose.down(str(batch_item_pk), None)

    event = DaemonEvent(
        project_id=labels.get("iwcore.project"),
        event_type="worktree_compose",
        entity_id=str(batch_item_pk),
        entity_type="batch_item",
        message="Orphan container teardown triggered by operator",
        event_metadata={
            "phase": "down",
            "trigger": "operator_force_orphan",
            "container_id": container_id,
            "batch_item_id": batch_item_label,
        },
    )
    db.add(event)
    db.commit()

    templates: Jinja2Templates = request.app.state.templates
    worktrees = _collect_worktrees(db)
    return templates.TemplateResponse(
        request,
        "fragments/worktree_table.html",
        {"worktrees": worktrees, "prune_errors": []},
    )
