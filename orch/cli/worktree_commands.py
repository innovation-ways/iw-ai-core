"""Git worktree health monitoring command.

Shows git status of all active agent worktrees and flags orphaned paths.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from typing import Any

import click
from sqlalchemy import select

from orch.db.models import (
    BatchItem,
    BatchItemStatus,
    Project,
)

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git_status(path: str) -> dict[str, Any]:
    """Return git status info for a worktree path.

    Returns a dict with keys: label, modified, untracked, files.
    Label is one of: clean, dirty, untracked, staged, no_path, timeout, error.
    """
    try:
        r = subprocess.run(  # noqa: S603
            ["git", "-C", path, "status", "--porcelain"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            return {"label": "error", "modified": 0, "untracked": 0, "files": []}
        lines = [ln for ln in r.stdout.splitlines() if ln]
        if not lines:
            return {"label": "clean", "modified": 0, "untracked": 0, "files": []}

        untracked = [ln for ln in lines if ln.startswith("??")]
        modified = [ln for ln in lines if not ln.startswith("??")]

        label = "dirty" if modified else "untracked"
        return {
            "label": label,
            "modified": len(modified),
            "untracked": len(untracked),
            "files": lines,
        }
    except FileNotFoundError:
        return {"label": "no_path", "modified": 0, "untracked": 0, "files": []}
    except subprocess.TimeoutExpired:
        return {"label": "timeout", "modified": 0, "untracked": 0, "files": []}
    except Exception:  # noqa: BLE001
        return {"label": "error", "modified": 0, "untracked": 0, "files": []}


def _commits_ahead(path: str, base: str = "main") -> int:
    """Return number of commits HEAD is ahead of *base*. Returns -1 on error."""
    with contextlib.suppress(Exception):
        r = subprocess.run(  # noqa: S603
            ["git", "-C", path, "rev-list", f"{base}..HEAD", "--count"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            return int(r.stdout.strip())
    return -1


def _current_branch(path: str) -> str:
    """Return the checked-out branch name. Returns '—' on error."""
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
    """Return all agent worktrees for *repo_root* via git worktree list --porcelain.

    Skips the first entry (the main worktree itself).
    Each item: {path, branch, head}.
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
                current = {"path": line[9:], "branch": "—", "head": "—"}
            elif line.startswith("HEAD "):
                current["head"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:].removeprefix("refs/heads/")
        if current:
            entries.append(current)

        # entries[0] is always the main worktree — skip it
        return entries[1:]
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# Status display helpers
# ---------------------------------------------------------------------------

_STATUS_ICONS: dict[str, str] = {
    "clean": "[OK]",
    "dirty": "[!!]",
    "untracked": "[??]",
    "staged": "[++]",
    "orphaned": "[XX]",
    "no_path": "[--]",
    "timeout": "[TO]",
    "error": "[ER]",
}


def _fmt_git(label: str, modified: int, untracked: int) -> str:
    detail = label.upper()
    if modified:
        detail += f"({modified}M)"
    if untracked:
        detail += f"({untracked}U)"
    return detail


def _truncate_path(path: str, max_len: int = 45) -> str:
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3) :]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@click.command("worktree-status")
@click.option("--verbose", "-v", is_flag=True, help="Show list of changed files per worktree")
@click.option("--json", "-j", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def worktree_status(ctx: click.Context, verbose: bool, json_output: bool) -> None:
    """Show git health of all active agent worktrees across all projects.

    Displays DB-tracked active worktrees (setting_up / executing / merging) plus
    any orphaned worktrees found on disk that have no matching active batch item.
    """
    get_session = ctx.obj["get_session"]

    _active = {
        BatchItemStatus.setting_up,
        BatchItemStatus.executing,
        BatchItemStatus.merging,
    }

    rows: list[dict[str, Any]] = []

    with get_session() as session:
        # ---- Project main checkouts (always shown — catches developer dirty state) ----
        projects = (
            session.execute(select(Project).where(Project.enabled.is_(True))).scalars().all()  # type: ignore[arg-type]
        )
        known_paths: set[str] = set()
        for project in projects:
            path = project.repo_root
            known_paths.add(path)
            gs = _git_status(path)
            rows.append(
                {
                    "project_id": project.id,
                    "item_id": "(main)",
                    "batch_id": "—",
                    "branch": _current_branch(path),
                    "batch_status": "main",
                    "path": path,
                    "git_status": gs["label"],
                    "modified": gs["modified"],
                    "untracked": gs["untracked"],
                    "files": gs["files"] if verbose else [],
                    "ahead": -1,
                    "is_orphan": False,
                }
            )

        # ---- Active worktrees from DB ----
        stmt = select(BatchItem).where(BatchItem.status.in_(list(_active)))
        batch_items = session.execute(stmt).scalars().all()

        for bi in batch_items:
            wt = bi.worktree_info or {}
            path = wt.get("path")
            branch = wt.get("branch", "—")

            if path:
                known_paths.add(path)

            gs = (
                _git_status(path)
                if path
                else {"label": "no_path", "modified": 0, "untracked": 0, "files": []}
            )
            ahead = _commits_ahead(path) if path else -1

            rows.append(
                {
                    "project_id": bi.project_id,
                    "item_id": bi.work_item_id,
                    "batch_id": bi.batch_id,
                    "branch": branch,
                    "batch_status": bi.status.value,
                    "path": path or "—",
                    "git_status": gs["label"],
                    "modified": gs["modified"],
                    "untracked": gs["untracked"],
                    "files": gs["files"] if verbose else [],
                    "ahead": ahead,
                    "is_orphan": False,
                }
            )

        # ---- Orphan detection: walk git worktrees per project ----
        # projects already loaded above for main checkout rows
        for project in projects:
            for wt in _git_worktrees(project.repo_root):
                wt_path = wt["path"]
                if wt_path in known_paths:
                    continue
                # Only flag daemon-managed branches (agent/*) as orphaned.
                # Human worktrees (e.g. manual-dev) are intentional — skip them.
                if not wt["branch"].startswith("agent/"):
                    continue
                gs = _git_status(wt_path)
                rows.append(
                    {
                        "project_id": project.id,
                        "item_id": "—",
                        "batch_id": "—",
                        "branch": wt["branch"],
                        "batch_status": "orphaned",
                        "path": wt_path,
                        "git_status": "orphaned",
                        "modified": gs["modified"],
                        "untracked": gs["untracked"],
                        "files": gs["files"] if verbose else [],
                        "ahead": _commits_ahead(wt_path),
                        "is_orphan": True,
                    }
                )

    # ---- Output ----
    if json_output or ctx.obj.get("json"):
        orphan_count = sum(1 for r in rows if r["is_orphan"])
        click.echo(
            json.dumps(
                {"worktrees": rows, "total": len(rows), "orphans": orphan_count},
                indent=2,
            )
        )
        return

    if not rows:
        click.echo("No active worktrees.")
        return

    # Table header
    click.echo(f"{'PROJECT':<16} {'ITEM':<10} {'STAT':<12} {'GIT':<16} {'AHEAD':<6} PATH")
    click.echo("-" * 85)

    dirty_count = 0
    orphan_count = 0

    for r in rows:
        if r["git_status"] == "dirty":
            dirty_count += 1
        if r["is_orphan"]:
            orphan_count += 1

        icon = _STATUS_ICONS.get(r["git_status"], "[??]")
        git_col = f"{icon} {_fmt_git(r['git_status'], r['modified'], r['untracked'])}"
        ahead_col = f"+{r['ahead']}" if r["ahead"] >= 0 else "—"
        path_col = _truncate_path(r["path"])

        line = (
            f"{r['project_id']:<16} {r['item_id']:<10}"
            f" {r['batch_status']:<12} {git_col:<16} {ahead_col:<6} {path_col}"
        )
        click.echo(line)

        if verbose and r["files"]:
            for f in r["files"][:10]:
                click.echo(f"    {f}")
            if len(r["files"]) > 10:
                click.echo(f"    … and {len(r['files']) - 10} more")

    click.echo()
    click.echo(f"Total: {len(rows)}  |  dirty: {dirty_count}  |  orphaned: {orphan_count}")
