"""orch.staleness.git_lookup — Git commit history lookups for staleness detection.

Two public functions:
- find_commit_at: find the HEAD commit on main at or before a given timestamp.
- commits_since: list commits on main since a given SHA that touch watched paths.

All git invocations use subprocess.run with a 5s timeout and check=False.
Failures return None / empty list and log — they never raise to callers.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

logger = logging.getLogger(__name__)

_GIT_TIMEOUT = 5  # seconds


# ---------------------------------------------------------------------------
# CommitSummary — lightweight commit record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommitSummary:
    """One-line summary of a git commit.

    Attributes:
        sha: Full 40-character commit hash.
        subject: First line of the commit message.
    """

    sha: str
    subject: str


# ---------------------------------------------------------------------------
# find_commit_at
# ---------------------------------------------------------------------------


def find_commit_at(repo_root: Path, ts: datetime) -> str | None:
    """Return the SHA of the most recent first-parent commit on main at or before ``ts``.

    Uses ``git log --first-parent main --before=@<epoch> -1 --format=%H``.

    Returns None when no such commit exists or git fails.
    """
    epoch = int(ts.timestamp())
    cmd = [
        "git",
        "-C",
        str(repo_root),
        "log",
        "--first-parent",
        "main",
        f"--before=@{epoch}",
        "-1",
        "--format=%H",
    ]

    try:
        result = subprocess.run(  # noqa: S603,S607
            cmd,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("[staleness] git log timed out in %s", repo_root)
        return None
    except OSError as exc:
        logger.warning("[staleness] git log failed in %s: %s", repo_root, exc)
        return None

    if result.returncode != 0:
        logger.debug(
            "[staleness] git log exited %d in %s: %s",
            result.returncode,
            repo_root,
            result.stderr.strip(),
        )
        return None

    sha = result.stdout.strip()
    return sha if sha else None


# ---------------------------------------------------------------------------
# commits_since
# ---------------------------------------------------------------------------


def commits_since(
    repo_root: Path,
    since_sha: str,
    watch_paths: list[str],
    ignore_paths: list[str],
) -> list[CommitSummary]:
    """Return commits on main since ``since_sha`` that touch ``watch_paths``.

    Uses ``git log <since_sha>..main --format=%H%x09%s -- <pathspecs>``.

    Path handling:
    - ``watch_paths`` entries starting with ``!`` are treated as additional
      ``:(exclude)`` pathspecs.
    - ``ignore_paths`` entries are wrapped in ``:(exclude)``.

    Returns an empty list when up-to-date, on git failure, or if the repo
    does not exist.
    """
    pathspecs: list[str] = []

    for wp in watch_paths:
        if wp.startswith("!"):
            # Negated watch path → treat as exclude
            pathspecs.append(f":(exclude){wp[1:]}")
        else:
            pathspecs.append(wp)

    for ip in ignore_paths:
        pathspecs.append(f":(exclude){ip}")

    cmd = [
        "git",
        "-C",
        str(repo_root),
        "log",
        f"{since_sha}..main",
        "--format=%H\t%s",
        "--",
        *pathspecs,
    ]

    try:
        result = subprocess.run(  # noqa: S603,S607
            cmd,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("[staleness] git log (commits_since) timed out in %s", repo_root)
        return []
    except OSError as exc:
        logger.warning("[staleness] git log (commits_since) failed in %s: %s", repo_root, exc)
        return []

    if result.returncode != 0:
        logger.debug(
            "[staleness] git log (commits_since) exited %d in %s: %s",
            result.returncode,
            repo_root,
            result.stderr.strip(),
        )
        return []

    commits: list[CommitSummary] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if "\t" in line:
            sha, subject = line.split("\t", 1)
        else:
            sha = line
            subject = ""
        commits.append(CommitSummary(sha=sha.strip(), subject=subject.strip()))

    return commits
