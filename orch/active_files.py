"""Validation and auto-commit of ai-dev/active/<item_id>/ before approval."""

from __future__ import annotations

import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Chore-commit allow-list (I-00083)
#
# When `iw approve` runs, only the following paths under
# ai-dev/active/<item_id>/ are staged for the chore commit that lands on
# main *before* the squash merge:
#
#   - <item_id>_*_Design.md   — technical design documents
#   - <item_id>_Functional.md — human-facing summary
#   - workflow-manifest.json  — step definitions (design-time snapshot)
#   - prompts/                — step prompt files
#
# EXCLUDED (intentionally — do NOT add these back):
#   - Test fixtures, scripts, helper files written under ai-dev/active/ by
#     agents or operators pre-approval. These would reach main via the chore
#     commit while their matching implementation has not yet merged, causing
#     the branch-base drift bug documented in I-00083. Items branched between
#     the chore commit and the squash merge would inherit broken half-state.
#   - Evidences, ad-hoc notes, and anything else not in the list above.
#
# All excluded files travel with the squash merge commit instead — which lands
# implementation + tests + fixtures atomically, avoiding the drift.
#
# If you're tempted to "fix" this by re-adding everything: don't. See I-00083.
# ---------------------------------------------------------------------------

_CHORE_COMMIT_PATHSPECS = [
    # Design documents: <ID>_*_Design.md (technical), <ID>_Functional.md
    "{active_dir}/{item_id}_*_Design.md",
    "{active_dir}/{item_id}_Functional.md",
    # Workflow manifest
    "{active_dir}/workflow-manifest.json",
    # All prompt files under the prompts/ subdirectory
    "{active_dir}/prompts/",
]


def _build_allowed_pathspecs(item_id: str, active_dir: str) -> list[str]:
    """Return the list of git pathspecs to stage for the chore commit."""
    return [spec.format(item_id=item_id, active_dir=active_dir) for spec in _CHORE_COMMIT_PATHSPECS]


def ensure_active_files_committed(repo_root: str | Path, item_id: str, title: str) -> None:
    """Validate that the item's active directory exists and is committed.

    Raises ValueError if the directory is missing.
    Auto-commits untracked or modified files in the allow-listed paths only
    (see _CHORE_COMMIT_PATHSPECS / I-00083). Non-design files (test fixtures,
    scripts, evidences) are intentionally left untracked so they travel with
    the squash merge rather than arriving on main before the matching impl.
    """
    root = Path(repo_root)
    active_dir = root / "ai-dev" / "active" / item_id
    active_dir_rel = f"ai-dev/active/{item_id}"

    if not active_dir.exists():
        raise ValueError(
            f"Active directory not found: ai-dev/active/{item_id}/. "
            "Create the design doc and prompts before approving."
        )

    # Check only the allow-listed paths for dirtiness.
    # We check the full active dir for presence but only commit the narrow set.
    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain",
            "--",
            f"ai-dev/active/{item_id}/",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    if not result.stdout.strip():
        return

    # Build the narrowed pathspec list (I-00083 allow-list)
    allowed_pathspecs = _build_allowed_pathspecs(item_id, active_dir_rel)

    # Check whether any allow-listed paths are actually dirty
    dirty_check = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain",
            "--",
            *allowed_pathspecs,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    if not dirty_check.stdout.strip():
        # Only non-design files are dirty; nothing to commit via the chore path.
        return

    # Stage only the allow-listed paths (never the full directory)
    subprocess.run(  # noqa: S603
        [  # noqa: S607
            "git",
            "-C",
            str(root),
            "add",
            "--",
            *allowed_pathspecs,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    commit_msg = f"chore: commit {item_id} active files before approval\n\n{title}"
    proc = subprocess.run(  # noqa: S603
        ["git", "-C", str(root), "commit", "-m", commit_msg],  # noqa: S607
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise ValueError(f"Failed to auto-commit active files for {item_id}: {proc.stderr.strip()}")
