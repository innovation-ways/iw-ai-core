"""Alembic-version guard — fail-fast when the live DB is behind the script directory head.

Public API:
    GuardStatus         — frozen dataclass with current_rev, head_rev, pending, multiple_heads, ok
    DBBehindHeadError   — raised when alembic_version != head
    MultipleHeadsError — raised when ScriptDirectory has >1 head (re-export)
    check_db_at_head()  — returns GuardStatus; never raises
    assert_db_at_head() — raises DBBehindHeadError or MultipleHeadsError on mismatch
    remediation_message() — human-readable single-line message

Environment overrides (only for testing agent subprocess DB access):
    IW_CORE_SKIP_ALEMBIC_GUARD  — if "true", assert_db_at_head() returns silently
    IW_CORE_AGENT_CONTEXT        — if "true", assert_db_at_head() returns silently
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from alembic.script import ScriptDirectory
from alembic.script.revision import RangeNotAncestorError
from alembic.util.exc import CommandError

from orch.config import get_db_url
from orch.db.safe_migrate import (
    MultipleHeadsError,
    current_revision,
    list_pending_revisions,
)

__all__ = [
    "GuardStatus",
    "DBBehindHeadError",
    "MultipleHeadsError",
    "check_db_at_head",
    "assert_db_at_head",
    "remediation_message",
]

logger = logging.getLogger("orch.db.alembic_guard")

MIGRATIONS_SCRIPT_LOCATION = str(__file__.rsplit("/", 1)[0] + "/migrations")


class DBBehindHeadError(RuntimeError):
    """Raised when alembic_version != ScriptDirectory head."""


@dataclass(frozen=True)
class GuardStatus:
    current_rev: str | None
    head_rev: str | None
    pending: list[str]
    multiple_heads: list[str]
    ok: bool


def _get_head_revisions(db_url: str) -> tuple[str | None, list[str]]:
    """Return (head_rev, multiple_heads_list) from ScriptDirectory.

    head_rev is the single head if exactly one exists, otherwise None.
    multiple_heads is non-empty if >1 head detected.
    """
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig()
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", MIGRATIONS_SCRIPT_LOCATION)
    script_dir = ScriptDirectory.from_config(cfg)
    heads = script_dir.get_heads()
    if len(heads) > 1:
        return None, heads
    return heads[0] if heads else None, []


def check_db_at_head(db_url: str | None = None) -> GuardStatus:
    """Compare DB alembic_version against script-directory head.

    Returns GuardStatus (never raises). ok is True when the DB is at head
    with a single head.
    """
    if db_url is None:
        db_url = get_db_url()

    current_rev = current_revision(db_url)
    head_rev, multiple_heads = _get_head_revisions(db_url)

    try:
        pending_revs = list_pending_revisions(db_url)
        pending = [r.id for r in pending_revs]
    except MultipleHeadsError:
        pending = []
    except RangeNotAncestorError:
        pending = ["<RangeNotAncestorError>"]
    except CommandError:
        pending = ["<CommandError>"]

    ok = len(pending) == 0 and len(multiple_heads) <= 1

    return GuardStatus(
        current_rev=current_rev,
        head_rev=head_rev,
        pending=pending,
        multiple_heads=multiple_heads,
        ok=ok,
    )


def assert_db_at_head(db_url: str | None = None) -> None:
    """Raise DBBehindHeadError or MultipleHeadsError on mismatch.

    Silently returns when the DB is at head with a single head.
    """
    import os

    if os.environ.get("IW_CORE_SKIP_ALEMBIC_GUARD", "").lower() == "true":
        return
    if os.environ.get("IW_CORE_AGENT_CONTEXT", "").lower() == "true":
        return

    status = check_db_at_head(db_url)

    if len(status.multiple_heads) > 1:
        raise MultipleHeadsError(
            f"Multiple alembic heads detected: {status.multiple_heads}. "
            "Create a merge revision before applying migrations."
        )

    if not status.ok:
        current_display = status.current_rev or "EMPTY"
        head_display = status.head_rev or "?"
        raise DBBehindHeadError(
            f"orch DB schema mismatch — "
            f"current_rev={current_display} head_rev={head_display} "
            f"run 'make db-migrate' to fix"
        )


def remediation_message(status: GuardStatus) -> str:
    """Human-readable single-line remediation message.

    Contains current_rev, head_rev, and 'make db-migrate'.
    """
    current_display = status.current_rev or "EMPTY"
    head_display = status.head_rev or "?"
    pending_display = ", ".join(status.pending) if status.pending else "none"
    return (
        f"orch DB schema mismatch — "
        f"current_rev={current_display} head_rev={head_display} "
        f"pending={pending_display} "
        f"run 'make db-migrate' to fix"
    )
