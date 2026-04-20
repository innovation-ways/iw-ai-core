"""Git log parser for resolving files to work-item IDs.

Parses `git log --follow --oneline` output looking for squash-merge commit
first lines that contain patterns like `Merge F-NNNNN:`, `Merge CR-NNNNN:`,
or `Merge I-NNNNN:`.
"""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

MERGE_PATTERN = re.compile(r"Merge\s+(F|CR|I)-\d{5}:")


def resolve_work_items_for_files(
    files: Sequence[str],
    *,
    repo_root: Path,
) -> dict[str, list[str]]:
    """Resolve work-item IDs from git log for the given files.

    For each file, runs `git log --follow --oneline` and parses the first line
    of each commit looking for `Merge {F,CR,I}-NNNNN:` patterns.

    Args:
        files: Sequence of file paths (absolute or relative to repo_root).
        repo_root: Root of the git repository.

    Returns:
        Dict mapping file path -> list of work-item IDs found (deduplicated,
        preserving order of first-seen).

    Note:
        The returned work-item IDs are raw and unfiltered by project. The caller
        (typically ``_fetch_work_items_by_ids`` which filters by ``project_id``)
        is responsible for scoping results to the correct project. Cross-project
        IDs returned by this resolver will be filtered out at the database query layer.
    """
    result: dict[str, list[str]] = {}

    for file in files:
        result[file] = _resolve_file(file, repo_root)

    return result


def _resolve_file(file: str, repo_root: Path) -> list[str]:
    """Resolve a single file to work-item IDs via git log."""
    import shutil

    seen: set[str] = set()
    ids: list[str] = []

    git_path = shutil.which("git")
    if git_path is None:
        return []

    try:
        proc = subprocess.run(  # noqa: S603
            [git_path, "log", "--follow", "--oneline", "--", file],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
    except (subprocess.TimeoutExpired, OSError):  # noqa: S110
        return []

    for line in proc.stdout.splitlines():
        match = MERGE_PATTERN.search(line)
        if match:
            wi_id = match.group(0).replace("Merge ", "").replace(":", "").strip()
            if wi_id not in seen:
                seen.add(wi_id)
                ids.append(wi_id)

    return ids


def parse_work_item_id_from_commit_line(line: str) -> str | None:
    """Extract work-item ID from a git commit first line.

    Returns the ID (e.g. "F-00042") if found, else None.
    """
    match = MERGE_PATTERN.search(line)
    if match:
        return match.group(0).replace("Merge ", "").replace(":", "").strip()
    return None
