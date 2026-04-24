"""Safe migration wrapper — single choke-point for DB-mutating alembic calls.

Every migration operation that ever touches the live DB must go through this module.
The module enforces:

1. **Agent-context guard** — apply() and rollback() raise AgentContextForbidden
   when IW_CORE_AGENT_CONTEXT='true' (daemon sets this when launching agents).
2. **Live-DB sanity check** — dry_run() refuses to operate on the live DB URL
   even if called by an operator.
3. **Multi-head detection** — list_pending_revisions() raises MultipleHeadsError when
   the alembic revision graph has >1 head.
4. **Audit logging** — every dry_run / apply / rollback call writes to pending_migration_log
   via a fresh short-lived session.
"""

from __future__ import annotations

import logging
import os
import re
import time
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Literal

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from orch.config import get_db_url
from orch.db.models import PendingMigrationLog

__all__ = [
    "AgentContextForbiddenError",
    "MultipleHeadsError",
    "MigrationLockHeldError",
    "Revision",
    "DryRunResult",
    "ApplyResult",
    "RollbackResult",
    "list_pending_revisions",
    "dry_run",
    "apply",
    "rollback",
    "current_revision",
    "is_live_db_url",
]

logger = logging.getLogger(__name__)

MIGRATIONS_SCRIPT_LOCATION = str(Path(__file__).parent / "migrations")
MAX_TAIL_BYTES = 16 * 1024

# The orch DB is a single shared store; migration_locks is a per-project mutex
# with a FK to projects.id. We key the lock on the orch project's own row
# ("iw-ai-core") because the orch DB migrations are global and there is only
# one orchestrator. The previous hardcoded 'innoForge' value never existed in
# the projects table, so lock acquisition always raised FK violations.
_ORCH_MIGRATION_LOCK_PROJECT = "iw-ai-core"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AgentContextForbiddenError(RuntimeError):
    """Raised when a caller tries to apply/rollback inside an agent subprocess."""


class MultipleHeadsError(RuntimeError):
    """Raised when the alembic revision graph has >1 head."""


class MigrationLockHeldError(RuntimeError):
    """Raised when the migration lock is held by another item (stale agent)."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Revision:
    id: str
    description: str
    down_revision: str | None


@dataclass(frozen=True)
class DryRunResult:
    revisions_applied: list[str]
    success: bool
    duration_ms: int
    stdout_tail: str
    stderr_tail: str
    error_message: str | None


@dataclass(frozen=True)
class ApplyResult(DryRunResult):
    pass


@dataclass(frozen=True)
class RollbackResult:
    revision_from: str
    revision_to: str
    success: bool
    duration_ms: int
    error_message: str | None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _assert_not_agent_context() -> None:
    """Raise AgentContextForbiddenError if IW_CORE_AGENT_CONTEXT='true'."""
    if os.environ.get("IW_CORE_AGENT_CONTEXT") == "true":
        raise AgentContextForbiddenError(
            "Migration operation refused: IW_CORE_AGENT_CONTEXT='true'. "
            "Only the daemon may apply/rollback migrations against the live DB."
        )


def _is_live_db_url(url: str) -> bool:
    """Return True iff URL matches the live DB connection from orch.config."""
    try:
        return url == get_db_url()
    except Exception:
        return False


def _build_alembic_config(db_url: str) -> AlembicConfig:
    """Build an alembic Config configured to point at db_url with our migrations."""
    cfg = AlembicConfig()
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", MIGRATIONS_SCRIPT_LOCATION)
    return cfg


def _current_revision_from_db(db_url: str) -> str | None:
    """Read the current revision from the DB's alembic_version table."""
    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            return row[0] if row else None
    finally:
        engine.dispose()


def _truncate_tail(s: str) -> str:
    """Truncate string to at most MAX_TAIL_BYTES, keeping the end."""
    if len(s) <= MAX_TAIL_BYTES:
        return s
    return s[-MAX_TAIL_BYTES:]


def _write_migration_log(
    revision: str,
    direction: Literal["upgrade", "downgrade"],
    phase: Literal["dry_run", "apply", "rollback"],
    batch_id: int | None,
    success: bool,
    stdout_tail: str,
    stderr_tail: str,
    error_message: str | None,
) -> None:
    """Write an entry to pending_migration_log via a fresh short-lived session."""
    log_db_url = get_db_url()
    engine = create_engine(log_db_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine)
    session: Session = session_factory()
    try:
        entry = PendingMigrationLog(
            revision=revision,
            direction=direction,
            phase=phase,
            batch_id=batch_id,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            success=success,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            error_message=error_message,
        )
        session.add(entry)
        session.commit()
    except Exception as exc:
        logger.error("Failed to write pending_migration_log entry: %s", exc)
        session.rollback()
    finally:
        session.close()
        engine.dispose()


_ALEMBIC_UPGRADE_LINE = re.compile(r"Running upgrade\s+\S+\s+->\s+([A-Za-z0-9_]+)")


class _AlembicRevisionCapture(logging.Handler):
    """Parses alembic's 'Running upgrade X -> Y' log records into a revision list.

    `command.upgrade` emits one such record per revision it applies via the
    `alembic.runtime.migration` logger. Capturing them here is the only
    in-process way to know which revisions actually ran without re-querying
    the DB and reconstructing the graph (which is fragile across merge
    revisions).
    """

    def __init__(self) -> None:
        super().__init__()
        self.revisions: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        match = _ALEMBIC_UPGRADE_LINE.search(record.getMessage())
        if match is not None:
            self.revisions.append(match.group(1))


def _run_alembic_upgrade(
    cfg: AlembicConfig,
) -> tuple[list[str], str, str, str | None]:
    """Run alembic upgrade head, capturing stdout/stderr and applied revisions.

    Returns (revisions_applied, stdout_tail, stderr_tail, error_message).
    `revisions_applied` is chronological (first → last applied).
    """
    stdout_buf = StringIO()
    stderr_buf = StringIO()
    error_message: str | None = None

    capture = _AlembicRevisionCapture()
    capture.setLevel(logging.INFO)
    alembic_logger = logging.getLogger("alembic.runtime.migration")
    previous_level = alembic_logger.level
    alembic_logger.addHandler(capture)
    if previous_level == logging.NOTSET or previous_level > logging.INFO:
        alembic_logger.setLevel(logging.INFO)

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            command.upgrade(cfg, "head")
    except Exception as exc:
        error_message = str(exc)
    finally:
        alembic_logger.removeHandler(capture)
        alembic_logger.setLevel(previous_level)

    stdout_tail = _truncate_tail(stdout_buf.getvalue())
    stderr_tail = _truncate_tail(stderr_buf.getvalue())

    return capture.revisions, stdout_tail, stderr_tail, error_message


def _run_alembic_downgrade(cfg: AlembicConfig, steps: int) -> tuple[str, str, str | None]:
    """Run alembic downgrade -N, capturing stdout/stderr.

    Returns (revision_from, stderr_tail, error_message).
    revision_from is the revision we were at before downgrade.
    """
    revision_from = _current_revision_from_db(cfg.get_main_option("sqlalchemy.url") or "")
    stderr_buf = StringIO()
    error_message: str | None = None

    try:
        with redirect_stderr(stderr_buf):
            command.downgrade(cfg, f"-{steps}")
    except Exception as exc:
        error_message = str(exc)

    stderr_tail = _truncate_tail(stderr_buf.getvalue())

    return revision_from or "", stderr_tail, error_message


def _acquire_migration_lock(item: str = "daemon") -> None:
    """Acquire the iw migration-lock for the daemon.

    Raises MigrationLockHeldError if the lock is held by another item.
    """
    lock_db_url = get_db_url()
    engine = create_engine(lock_db_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine)
    session: Session = session_factory()
    try:
        result = session.execute(
            text("SELECT current_holder FROM migration_locks WHERE project_id = :pid FOR UPDATE"),
            {"pid": _ORCH_MIGRATION_LOCK_PROJECT},
        )
        row = result.fetchone()
        current_holder = row[0] if row else None
        if current_holder is not None and current_holder != item:
            raise MigrationLockHeldError(
                f"Migration lock is held by '{current_holder}'. "
                f"Cannot acquire for '{item}'. "
                "Check for stale agent processes."
            )
        session.execute(
            text(
                "INSERT INTO migration_locks (project_id, current_holder, locked_at) "
                "VALUES (:pid, :item, now()) "
                "ON CONFLICT (project_id) DO UPDATE "
                "SET current_holder = :item, locked_at = now()"
            ),
            {"pid": _ORCH_MIGRATION_LOCK_PROJECT, "item": item},
        )
        session.commit()
    finally:
        session.close()
        engine.dispose()


def _release_migration_lock(item: str = "daemon") -> None:
    """Release the iw migration-lock for the daemon."""
    lock_db_url = get_db_url()
    engine = create_engine(lock_db_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine)
    session: Session = session_factory()
    try:
        session.execute(
            text(
                "UPDATE migration_locks SET current_holder = NULL "
                "WHERE project_id = :pid AND current_holder = :item"
            ),
            {"pid": _ORCH_MIGRATION_LOCK_PROJECT, "item": item},
        )
        session.commit()
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_pending_revisions(db_url: str | None = None) -> list[Revision]:
    """Compare alembic ScriptDirectory heads to the DB's current revision.

    Returns a list of Revision objects representing pending (not-yet-applied) revisions.
    Raises MultipleHeadsError if multiple heads are detected in ScriptDirectory.
    """
    if db_url is None:
        db_url = get_db_url()

    script_dir = ScriptDirectory.from_config(_build_alembic_config(db_url))

    heads = script_dir.get_heads()
    if len(heads) > 1:
        raise MultipleHeadsError(
            f"Multiple alembic heads detected: {heads}. "
            "Create a merge revision with "
            f"`alembic merge -m 'merge branches' {' '.join(heads)}` "
            "before applying migrations."
        )

    current_rev = _current_revision_from_db(db_url)
    pending: list[Revision] = []

    for rev in script_dir.walk_revisions("head", current_rev or "base"):
        if rev.revision == current_rev:
            break
        if rev.revision not in (r.id for r in pending):
            _down = rev.down_revision
            if isinstance(_down, (list, tuple)):
                _down = ",".join(_down)
            pending.append(
                Revision(
                    id=rev.revision,
                    description=rev.doc or "",
                    down_revision=_down,
                )
            )

    return list(reversed(pending))


def dry_run(tempdb_url: str, batch_id: int | None = None) -> DryRunResult:
    """Spin up alembic context against tempdb_url, upgrade to head, record log entry.

    tempdb_url is expected to be a testcontainer URL (caller provides).
    Refuses if tempdb_url matches the live DB URL.
    """
    if _is_live_db_url(tempdb_url):
        raise ValueError("dry_run called on live DB — refusing")

    started_at = time.perf_counter()
    cfg = _build_alembic_config(tempdb_url)

    revisions_applied, stdout_tail, stderr_tail, error_message = _run_alembic_upgrade(cfg)
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    success = error_message is None

    revision_str = revisions_applied[-1] if revisions_applied else "head"

    _write_migration_log(
        revision=revision_str,
        direction="upgrade",
        phase="dry_run",
        batch_id=batch_id,
        success=success,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
        error_message=error_message,
    )

    return DryRunResult(
        revisions_applied=revisions_applied,
        success=success,
        duration_ms=duration_ms,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
        error_message=error_message,
    )


def apply(live_db_url: str, batch_id: int | None = None) -> ApplyResult:
    """Acquire migration lock, upgrade to head against live DB, release lock.

    RAISES AgentContextForbiddenError if IW_CORE_AGENT_CONTEXT='true'.
    Records log entry with phase='apply'.
    """
    _assert_not_agent_context()

    _acquire_migration_lock(item="daemon")
    try:
        started_at = time.perf_counter()
        cfg = _build_alembic_config(live_db_url)

        revisions_applied, stdout_tail, stderr_tail, error_message = _run_alembic_upgrade(cfg)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        success = error_message is None

        revision_str = revisions_applied[-1] if revisions_applied else "head"

        _write_migration_log(
            revision=revision_str,
            direction="upgrade",
            phase="apply",
            batch_id=batch_id,
            success=success,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            error_message=error_message,
        )

        return ApplyResult(
            revisions_applied=revisions_applied,
            success=success,
            duration_ms=duration_ms,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            error_message=error_message,
        )
    except Exception as exc:
        success = False
        error_message = str(exc)
        stdout_tail = ""
        stderr_tail = ""
        revision_str = "head"
        duration_ms = 0
        _write_migration_log(
            revision=revision_str,
            direction="upgrade",
            phase="apply",
            batch_id=batch_id,
            success=success,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            error_message=error_message,
        )
        raise
    finally:
        _release_migration_lock(item="daemon")


def rollback(live_db_url: str, steps: int = 1, batch_id: int | None = None) -> RollbackResult:
    """Alembic downgrade -N against live DB.

    RAISES AgentContextForbiddenError if IW_CORE_AGENT_CONTEXT='true'.
    Records log entry with phase='rollback'.
    """
    _assert_not_agent_context()

    _acquire_migration_lock(item="daemon")
    try:
        started_at = time.perf_counter()
        cfg = _build_alembic_config(live_db_url)

        revision_from, stderr_tail, error_message = _run_alembic_downgrade(cfg, steps)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        success = error_message is None

        revision_to = _current_revision_from_db(live_db_url) or "base"

        _write_migration_log(
            revision=revision_from,
            direction="downgrade",
            phase="rollback",
            batch_id=batch_id,
            success=success,
            stdout_tail="",
            stderr_tail=stderr_tail,
            error_message=error_message,
        )

        return RollbackResult(
            revision_from=revision_from,
            revision_to=revision_to,
            success=success,
            duration_ms=duration_ms,
            error_message=error_message,
        )
    except Exception as exc:
        success = False
        error_message = str(exc)
        stderr_tail = ""
        revision_from = "?"
        duration_ms = 0
        _write_migration_log(
            revision=revision_from,
            direction="downgrade",
            phase="rollback",
            batch_id=batch_id,
            success=success,
            stdout_tail="",
            stderr_tail=stderr_tail,
            error_message=error_message,
        )
        raise
    finally:
        _release_migration_lock(item="daemon")


def current_revision(db_url: str) -> str | None:
    """Read the current revision from the DB's alembic_version table."""
    return _current_revision_from_db(db_url)


def is_live_db_url(url: str) -> bool:
    """Return True iff the URL matches the live DB connection from orch.config."""
    return _is_live_db_url(url)
