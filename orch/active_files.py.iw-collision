"""Validation and auto-commit of ai-dev/active/<item_id>/ before approval."""

from __future__ import annotations

import subprocess
from pathlib import Path


def ensure_active_files_committed(repo_root: str | Path, item_id: str, title: str) -> None:
    """Validate that the item's active directory exists and is committed.

    Raises ValueError if the directory is missing.
    Auto-commits untracked or modified files if the directory exists but is dirty.
    """
    root = Path(repo_root)
    active_dir = root / "ai-dev" / "active" / item_id

    if not active_dir.exists():
        raise ValueError(
            f"Active directory not found: ai-dev/active/{item_id}/. "
            "Create the design doc and prompts before approving."
        )

    result = subprocess.run(  # noqa: S603
        ["git", "-C", str(root), "status", "--porcelain", "--", f"ai-dev/active/{item_id}/"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )

    if not result.stdout.strip():
        return

    subprocess.run(  # noqa: S603
        ["git", "-C", str(root), "add", f"ai-dev/active/{item_id}/"],  # noqa: S607
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
