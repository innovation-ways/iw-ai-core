"""orch.staleness.alembic_check — Alembic migration head checker.

Compares the database's current revision (``alembic current``) against
the code's head revision (``alembic heads``) and returns a structured
result indicating whether migrations are up-to-date or stale.

All subprocess calls use a 10s timeout and check=False.
Failures return an ``unreachable`` status and log — they never raise to callers.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_ALEMBIC_TIMEOUT = 10  # seconds

# Docstring metadata prefixes that appear inside the migration script
# docstring (after Path:) and must be skipped when extracting the message.
_DOCSTRING_METADATA_PREFIXES = (
    "Revision ID:",
    "Revises:",
    "Create Date:",
    "Branch labels:",
    "Branches:",
    "Depends on:",
)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RevisionSummary:
    """Summary of a single pending Alembic revision.

    Attributes:
        rev_id: The revision identifier (hex string).
        message: Human-readable description of the revision.
    """

    rev_id: str
    message: str


@dataclass
class AlembicStatus:
    """Result of an Alembic migration head check.

    Attributes:
        status: One of "up_to_date", "stale", "unreachable", "no_config".
        current: The revision ID currently applied to the database, or None
            if no migrations have been applied yet.
        head: The code's target head revision ID, or None if unavailable.
        pending: Revisions between current and head (may be empty even when
            stale if we couldn't parse them individually).
        error: Error message when status is "unreachable" or "no_config".
    """

    status: str
    current: str | None
    head: str | None
    pending: list[RevisionSummary] = field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_revision_from_verbose(output: str) -> str | None:
    """Extract the first revision ID from verbose alembic output.

    Real ``alembic current --verbose`` stdout starts with a header line
    (``Current revision(s) for postgresql+...:``) followed by per-revision
    blocks beginning with ``Rev: <rev_id>``. ``alembic heads --verbose``
    starts directly with ``Rev: <rev_id>``. We scan for the first line
    whose stripped form starts with ``Rev: `` and return the token after it.

    Args:
        output: Full stdout from an ``alembic current --verbose`` or
            ``alembic heads --verbose`` invocation.

    Returns:
        The first revision ID found, or None when no Rev: line is present
        (e.g. an empty database with no migrations applied yet).
    """
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Rev:"):
            parts = stripped.split(maxsplit=2)
            if len(parts) >= 2:
                return parts[1]
    return None


def _parse_message_from_verbose(output: str) -> str:
    """Extract the human-readable description from verbose alembic output.

    Alembic embeds the migration script's docstring after the ``Path:``
    metadata line. The first line of the docstring is the human-readable
    message; subsequent lines are docstring metadata
    (``Revision ID:``/``Revises:``/``Create Date:``) and the long-form body.

    We return the first non-empty line after ``Path:`` that isn't a
    docstring-metadata line. Falls back to an empty string.

    Args:
        output: Full stdout from an ``alembic heads --verbose`` invocation.

    Returns:
        The first non-metadata line from the migration docstring, or empty string.
    """
    seen_path = False
    for line in output.splitlines():
        stripped = line.strip()
        if not seen_path:
            if stripped.startswith("Path:"):
                seen_path = True
            continue
        if not stripped:
            continue
        if stripped.startswith(_DOCSTRING_METADATA_PREFIXES):
            continue
        return stripped
    return ""


# ---------------------------------------------------------------------------
# Environment builder
# ---------------------------------------------------------------------------


def _build_env(db_url_env: str | None) -> dict[str, str] | None:
    """Build the subprocess environment dict.

    - When db_url_env is None: return None (inherit parent env unchanged).
    - When set: look up os.environ[db_url_env]; if missing, raise KeyError.
      Otherwise return a copy of os.environ with IW_ALEMBIC_DB_URL injected.

    Raises:
        KeyError: When db_url_env is set but the named variable is absent.
    """
    if db_url_env is None:
        return None

    db_url = os.environ.get(db_url_env)
    if db_url is None:
        raise KeyError(db_url_env)

    env = dict(os.environ)
    env["IW_ALEMBIC_DB_URL"] = db_url
    return env


# ---------------------------------------------------------------------------
# check_alembic — public entry point
# ---------------------------------------------------------------------------


def check_alembic(
    repo_root: Path,
    alembic_cfg_path: str,
    db_url_env: str | None,
) -> AlembicStatus:
    """Check whether the database's Alembic revision is at the code's head.

    Args:
        repo_root: Absolute path to the project root (where alembic.ini lives).
        alembic_cfg_path: Path to alembic.ini relative to repo_root.
        db_url_env: Name of an environment variable whose value is the DB URL.
            When None, the alembic subprocess inherits the parent environment
            unchanged. When set, the named env var's value is injected as
            IW_ALEMBIC_DB_URL in the subprocess environment.

    Returns:
        AlembicStatus with status ∈ {"up_to_date", "stale", "unreachable", "no_config"}.
    """
    cfg_path = repo_root / alembic_cfg_path
    if not cfg_path.exists():
        return AlembicStatus(
            status="no_config",
            current=None,
            head=None,
            pending=[],
            error=f"Alembic config not found: {cfg_path}",
        )

    # Build subprocess environment
    try:
        env = _build_env(db_url_env)
    except KeyError:
        return AlembicStatus(
            status="unreachable",
            current=None,
            head=None,
            pending=[],
            error=(
                f"Environment variable {db_url_env!r} is not set. "
                "Cannot determine database URL for Alembic check."
            ),
        )

    cfg_str = str(cfg_path)

    # -----------------------------------------------------------------------
    # Step 1: run `alembic current --verbose`
    # -----------------------------------------------------------------------
    try:
        current_result = subprocess.run(  # noqa: S603,S607  system-installed CLI; args are a list, no shell injection risk
            ["alembic", "-c", cfg_str, "current", "--verbose"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=_ALEMBIC_TIMEOUT,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        logger.warning("[staleness] alembic current timed out for %s", cfg_path)
        return AlembicStatus(
            status="unreachable",
            current=None,
            head=None,
            pending=[],
            error=f"alembic current timed out after {_ALEMBIC_TIMEOUT}s",
        )
    except OSError as exc:
        logger.warning("[staleness] alembic current failed for %s: %s", cfg_path, exc)
        return AlembicStatus(
            status="unreachable",
            current=None,
            head=None,
            pending=[],
            error=str(exc),
        )

    if current_result.returncode != 0:
        stderr = current_result.stderr.strip()
        logger.debug(
            "[staleness] alembic current exited %d for %s: %s",
            current_result.returncode,
            cfg_path,
            stderr,
        )
        return AlembicStatus(
            status="unreachable",
            current=None,
            head=None,
            pending=[],
            error=stderr or f"alembic current exited {current_result.returncode}",
        )

    current_rev = _parse_revision_from_verbose(current_result.stdout)

    # -----------------------------------------------------------------------
    # Step 2: run `alembic heads --verbose`
    # -----------------------------------------------------------------------
    try:
        heads_result = subprocess.run(  # noqa: S603,S607  system-installed CLI; args are a list, no shell injection risk
            ["alembic", "-c", cfg_str, "heads", "--verbose"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=_ALEMBIC_TIMEOUT,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        logger.warning("[staleness] alembic heads timed out for %s", cfg_path)
        return AlembicStatus(
            status="unreachable",
            current=current_rev,
            head=None,
            pending=[],
            error=f"alembic heads timed out after {_ALEMBIC_TIMEOUT}s",
        )
    except OSError as exc:
        logger.warning("[staleness] alembic heads failed for %s: %s", cfg_path, exc)
        return AlembicStatus(
            status="unreachable",
            current=current_rev,
            head=None,
            pending=[],
            error=str(exc),
        )

    if heads_result.returncode != 0:
        stderr = heads_result.stderr.strip()
        logger.debug(
            "[staleness] alembic heads exited %d for %s: %s",
            heads_result.returncode,
            cfg_path,
            stderr,
        )
        return AlembicStatus(
            status="unreachable",
            current=current_rev,
            head=None,
            pending=[],
            error=stderr or f"alembic heads exited {heads_result.returncode}",
        )

    head_rev = _parse_revision_from_verbose(heads_result.stdout)

    # -----------------------------------------------------------------------
    # Step 3: compare
    # -----------------------------------------------------------------------
    if head_rev is None:
        # No heads — nothing to migrate (empty project?)
        return AlembicStatus(
            status="up_to_date",
            current=current_rev,
            head=None,
            pending=[],
        )

    if current_rev == head_rev:
        return AlembicStatus(
            status="up_to_date",
            current=current_rev,
            head=head_rev,
            pending=[],
        )

    # Stale: build pending list from the heads output
    head_message = _parse_message_from_verbose(heads_result.stdout)
    pending: list[RevisionSummary] = []
    if head_rev:
        pending.append(RevisionSummary(rev_id=head_rev, message=head_message))

    return AlembicStatus(
        status="stale",
        current=current_rev,
        head=head_rev,
        pending=pending,
    )
