"""Diff resolver and parser for the Files view.

Provides:
- resolve_diff(): canonical diff source resolver following the resolution order
  (step_run → DB snapshot → merge SHA → live worktree).
- parse_diff_summary(): parse unified diff text into a JSON-serialisable summary.
- is_generated_path(): match a path against the canonical generated-file glob list.
- _capture_step_diff(): git diff HEAD^..HEAD in a worktree (for step-done capture).

Single source of truth for the generated-file glob list (consumed by both backend
and frontend).
"""

from __future__ import annotations

import fnmatch
import logging
import subprocess
from typing import TYPE_CHECKING, Any

import unidiff

if TYPE_CHECKING:
    from pathlib import Path

    from orch.db.models import Project, StepRun, WorkItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical glob list for generated files
# ---------------------------------------------------------------------------

GENERATED_FILE_GLOBS: tuple[str, ...] = (
    "uv.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "*.min.js",
    "*.snap",
)


# ---------------------------------------------------------------------------
# Generated-path helper
# ---------------------------------------------------------------------------


def is_generated_path(path: str) -> bool:
    """Return True if path matches any GENERATED_FILE_GLOBS pattern."""
    return any(fnmatch.fnmatch(path, pat) for pat in GENERATED_FILE_GLOBS)


# ---------------------------------------------------------------------------
# Diff parsing
# ---------------------------------------------------------------------------


def _strip_diff_prefix(path: str) -> str:
    """Strip the 'a/' or 'b/' prefix that git diff prepends to file paths."""
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def parse_diff_summary(diff_text: str) -> list[dict[str, Any]]:
    """Parse a unified diff into a JSON-serialisable summary list.

    Each entry: {
        "path": str,
        "status": "A" | "M" | "D" | "R",
        "added": int,
        "removed": int,
        "is_generated": bool,
        "is_binary": bool,
        "old_path": str | None,
    }

    For renamed files a single entry with status="R" is returned;
    old_path is set to the source path from the rename directive.
    """
    patch_set = unidiff.PatchSet(diff_text)
    result: list[dict[str, Any]] = []

    for patched_file in patch_set:
        source = _strip_diff_prefix(patched_file.source_file)
        target = _strip_diff_prefix(patched_file.target_file)

        if patched_file.is_binary_file:
            result.append(
                {
                    "path": target,
                    "status": "M",
                    "added": 0,
                    "removed": 0,
                    "is_generated": is_generated_path(target),
                    "is_binary": True,
                    "old_path": None,
                }
            )
            continue

        if patched_file.is_rename:
            result.append(
                {
                    "path": target,
                    "status": "R",
                    "added": sum(hunk.added for hunk in patched_file),
                    "removed": sum(hunk.removed for hunk in patched_file),
                    "is_generated": is_generated_path(target),
                    "is_binary": False,
                    "old_path": source,
                }
            )
            continue

        # Added / Modified / Deleted
        if patched_file.is_added_file:
            status = "A"
            path = target
        elif patched_file.is_removed_file:
            status = "D"
            path = source
        else:
            status = "M"
            path = target

        added = sum(hunk.added for hunk in patched_file)
        removed = sum(hunk.removed for hunk in patched_file)
        result.append(
            {
                "path": path,
                "status": status,
                "added": added,
                "removed": removed,
                "is_generated": is_generated_path(path),
                "is_binary": False,
                "old_path": None,
            }
        )

    return result


# ---------------------------------------------------------------------------
# Git shell helpers
# ---------------------------------------------------------------------------


def _run_git(
    *args: str,
    cwd: str | Path,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Run a git command and return CompletedProcess."""
    cmd = ["git", *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)  # noqa: S603


def _git_rev_parse_head(cwd: str | Path) -> str | None:
    """Return the SHA of HEAD in cwd, or None on failure."""
    result = _run_git("rev-parse", "HEAD", cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else None


def _git_diff_step_head(worktree_path: str) -> str | None:
    """Run git diff HEAD^..HEAD in worktree_path and return output or None.

    Returns None if:
    - The worktree has only one commit (HEAD^ is invalid).
    - git fails for any reason (logged as a warning).
    """
    try:
        result = _run_git("diff", "HEAD^..HEAD", cwd=worktree_path)
        if result.returncode != 0:
            logger.warning(
                "git diff HEAD^..HEAD failed in %s: %s",
                worktree_path,
                result.stderr.strip(),
            )
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        logger.warning("git diff HEAD^..HEAD timed out in %s", worktree_path)
        return None
    except Exception:
        logger.warning("git diff HEAD^..HEAD failed in %s", worktree_path, exc_info=True)
        return None


def _git_diff_worktree_head(worktree_path: str) -> str | None:
    """Run git diff <base>...HEAD in the worktree and return output or None.

    <base> is the parent of the first worktree commit. Falls back to HEAD^
    if the worktree has only one commit.
    Returns None if git fails.
    """
    try:
        result = _run_git("log", "--oneline", "-2", cwd=worktree_path)
        if result.returncode != 0:
            return None
        lines = result.stdout.strip().split("\n")
        if len(lines) < 2:
            result2 = _run_git("diff", "HEAD^..HEAD", cwd=worktree_path)
            if result2.returncode != 0:
                return None
            return result2.stdout
        result3 = _run_git("diff", f"{lines[-1].split()[0]}^...HEAD", cwd=worktree_path)
        if result3.returncode != 0:
            return None
        return result3.stdout
    except subprocess.TimeoutExpired:
        logger.warning("git diff timed out in worktree %s", worktree_path)
        return None
    except Exception:
        logger.warning("git diff failed in worktree %s", worktree_path, exc_info=True)
        return None


def _git_diff_merge_commit(repo_root: str, sha: str) -> str | None:
    """Run git diff <sha>^..<sha> in repo_root and return output or None."""
    try:
        result = _run_git("diff", f"{sha}^..{sha}", cwd=repo_root)
        if result.returncode != 0:
            logger.warning(
                "git diff %s^..%s failed in %s: %s",
                sha,
                sha,
                repo_root,
                result.stderr.strip(),
            )
            return None
        return result.stdout
    except subprocess.TimeoutExpired:
        logger.warning("git diff %s^..%s timed out in %s", sha, sha, repo_root)
        return None
    except Exception:
        logger.warning("git diff %s^..%s failed in %s", sha, sha, repo_root, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Diff resolver
# ---------------------------------------------------------------------------


def resolve_diff(
    *,
    item: WorkItem,
    step_run: StepRun | None,
    project: Project,
    worktree_path: str | None,
) -> str | None:
    """Return the raw unified diff for the given (item, optional step) or None.

    Resolution order:
      step_run provided → step_run.diff_text if present, else live `git diff`
        in worktree against step's commit SHA, else None.
      step_run is None and item.archived_at: → item.diff_text (DB snapshot).
      step_run is None and item.merge_commit_sha: → live
        `git diff <sha>^..<sha>` in project.repo_root.
      step_run is None and worktree alive: → live `git diff <base>...HEAD`
        in worktree.
      Otherwise → None.
    """
    # 1. Step-run path: prefer stored diff, fall back to live capture
    if step_run is not None:
        if step_run.diff_text:
            return step_run.diff_text
        if step_run.worktree_path:
            live = _git_diff_step_head(step_run.worktree_path)
            if live:
                return live
        return None

    # 2. Archived item: DB snapshot
    if item.archived_at is not None:
        return item.diff_text

    # 3. Merged-not-archived: diff against merge commit parent in repo_root
    if item.merge_commit_sha:
        return _git_diff_merge_commit(project.repo_root, item.merge_commit_sha)

    # 4. In-progress with live worktree
    if worktree_path:
        return _git_diff_worktree_head(worktree_path)

    # Nothing available
    return None


# ---------------------------------------------------------------------------
# Step-diff capture helper (used by iw step-done)
# ---------------------------------------------------------------------------


def _capture_step_diff(worktree_path: str) -> str | None:
    """Capture git diff HEAD^..HEAD in the worktree.

    Multi-commit step semantics: under the daemon's one-commit-per-step convention
    (executor/worktree_commit.sh produces a single commit per step), HEAD^..HEAD
    captures the full step delta. If a step produces multiple commits (rare, but
    possible if a fix cycle re-runs the same step), this capture returns ONLY the
    most recent commit's diff — earlier commits in the same step are not included.
    Switching to `git diff <prev_step_sha>..HEAD` is out of scope for v1; revisit
    if multi-commit steps become common.

    Returns None if the worktree has only one commit or git fails.
    """
    return _git_diff_step_head(worktree_path)
