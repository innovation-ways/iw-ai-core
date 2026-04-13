"""Worktree health page — git status of all active agent worktrees."""

from __future__ import annotations

import contextlib
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from dashboard.dependencies import get_db
from orch.db.models import (
    BatchItem,
    BatchItemStatus,
    Project,
)

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/system")

_ACTIVE_STATUSES = {
    BatchItemStatus.setting_up,
    BatchItemStatus.executing,
    BatchItemStatus.merging,
}


# ---------------------------------------------------------------------------
# Git helpers (run at request time — acceptable latency for a health page)
# ---------------------------------------------------------------------------


def _git_status(path: str) -> tuple[str, int, int]:
    """Return (label, modified_count, untracked_count) for a worktree path.

    Labels: clean | dirty | untracked | no_path | error | timeout
    """
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
        db.execute(select(Project.repo_root).where(Project.enabled.is_(True))).scalars().all()  # type: ignore[arg-type]
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


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------


def _collect_worktrees(db: Session) -> list[WorktreeRow]:
    """Query active batch items and detect orphaned worktrees on disk.

    Rows are ordered: project main checkouts first, then agent worktrees,
    then orphans.
    """
    now = datetime.now(UTC)
    rows: list[WorktreeRow] = []
    known_paths: set[str] = set()

    # ---- Project main checkouts (always shown — catches developer dirty state) ----
    projects = db.execute(select(Project).where(Project.enabled.is_(True))).scalars().all()  # type: ignore[arg-type]
    for project in projects:
        path = project.repo_root
        known_paths.add(path)
        label, mod, untr = _git_status(path)
        rows.append(
            WorktreeRow(
                project_id=project.id,
                item_id="(main)",
                batch_id="—",
                branch=_current_branch(path),
                batch_status="main",
                path=path,
                git_label=label,
                modified=mod,
                untracked=untr,
                ahead=-1,
                is_orphan=False,
                checked_at=now,
            )
        )

    # Active batch items with worktree_info
    stmt = select(BatchItem).where(BatchItem.status.in_(list(_ACTIVE_STATUSES)))
    for bi in db.execute(stmt).scalars().all():
        wt = bi.worktree_info or {}
        path: str | None = wt.get("path")
        branch: str = wt.get("branch", "—")

        if path:
            known_paths.add(path)

        if path:
            label, mod, untr = _git_status(path)
            ahead = _commits_ahead(path)
        else:
            label, mod, untr, ahead = "no_path", 0, 0, -1

        rows.append(
            WorktreeRow(
                project_id=bi.project_id,
                item_id=bi.work_item_id,
                batch_id=bi.batch_id,
                branch=branch,
                batch_status=bi.status.value,
                path=path or "—",
                git_label=label,
                modified=mod,
                untracked=untr,
                ahead=ahead,
                is_orphan=False,
                checked_at=now,
            )
        )

    # Orphan detection: walk git worktrees per enabled project (projects already loaded above)
    for project in projects:
        for wt in _git_worktrees(project.repo_root):
            if wt["path"] in known_paths:
                continue
            # Only flag daemon-managed branches (agent/*) as orphaned.
            # Human worktrees (e.g. manual-dev) are intentional — skip them.
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

    return rows


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/nav/worktree-badge", response_class=HTMLResponse)
def nav_worktree_badge(request: Request, db: Session = Depends(get_db)) -> Any:
    """Sidebar badge — red dot when any worktree is dirty.

    Lightweight: only runs git status on project roots + active worktrees.
    No orphan scan, no commits-ahead.
    """
    templates: Jinja2Templates = request.app.state.templates
    dirty = 0

    projects = db.execute(select(Project).where(Project.enabled.is_(True))).scalars().all()  # type: ignore[arg-type]
    for project in projects:
        label, _, _ = _git_status(project.repo_root)
        if label == "dirty":
            dirty += 1

    for bi in (
        db.execute(select(BatchItem).where(BatchItem.status.in_(list(_ACTIVE_STATUSES))))
        .scalars()
        .all()
    ):
        wt = bi.worktree_info or {}
        path = wt.get("path")
        if path:
            label, _, _ = _git_status(path)
            if label == "dirty":
                dirty += 1

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
