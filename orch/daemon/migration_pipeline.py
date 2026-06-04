"""Migration pipeline — 3-phase orchestration for daemon-driven migration application.

Phase 1 (dry_run):  Daemon spins a short-lived testcontainer Postgres, applies
                    pending revisions, runs integration tests, then tears down.
Phase 2 (apply):    After squash-merge, daemon applies migrations to live DB.
Phase 3 (rollback): If Phase 2 fails, daemon attempts one alembic downgrade -1.

Integration points:
- merge_queue.py  — calls pipeline before/after squash-merge
- safe_migrate.py — all DB-mutating alembic calls go through here
- batch_manager.py — sets IW_CORE_AGENT_CONTEXT=true on agent subprocess env
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from orch.config import get_db_url
from orch.db.safe_migrate import apply as safe_apply
from orch.db.safe_migrate import dry_run as safe_dry_run
from orch.db.safe_migrate import rollback as safe_rollback
from orch.db.session import safe_create_engine

logger = logging.getLogger(__name__)

MIGRATIONS_SCRIPT_LOCATION = str(__file__.rsplit("/orch/daemon/", 1)[0] + "/orch/db/migrations")
ALEMBIC_MIGRATIONS_DIR = MIGRATIONS_SCRIPT_LOCATION


# ---------------------------------------------------------------------------
# PipelineResult dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineResult:
    """Result returned by each phase of the migration pipeline.

    Attributes:
        phase: Which pipeline phase produced this result.
        success: Whether the phase completed without error.
        final_batch_state: Human-readable label for the resulting BatchItem state.
        frozen: True when a rollback failure has frozen the merge queue.
        message: Human-readable summary for logging and dashboard display.
        revisions_applied: Alembic revision IDs actually applied to the live DB
            during Phase 2. Empty when the phase was a no-op or failed before
            touching the DB; used by the merge queue to decide if Phase 3 rollback
            is safe.
    """

    phase: Literal["dry_run", "apply", "rollback"]
    success: bool
    final_batch_state: str
    frozen: bool
    message: str
    # Revisions actually applied to the live DB during a Phase 2 apply.
    # Empty when the apply was a no-op (DB already at head) or failed a
    # pre-flight check (e.g. SelfBlockerError, lock timeout) before touching
    # the DB. The merge queue uses this to decide whether a Phase 3 rollback
    # (`alembic downgrade -1`) is warranted: rolling back when nothing was
    # applied would clobber a previously-applied migration — the post-merge
    # rollback regression observed after the BATCH-00089 merge on 2026-05-11,
    # which left the orch DB one revision behind head.
    revisions_applied: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 1 — Pre-merge dry-run
# ---------------------------------------------------------------------------


def run_pre_merge_dry_run(
    batch_id: str | int | None,
    worktree_path: str | None = None,
) -> PipelineResult:
    """Phase 1: Spin testcontainer, apply pending revisions, run integration tests.

    When worktree_path is provided, alembic uses that worktree's migrations
    directory — so the batch's new migrations are actually exercised.
    When not provided, falls back to the daemon's main-repo migrations location
    (backward-compat for operator entry points; do NOT use this path in the
    merge queue — merge_queue.py always passes worktree_path).
    """
    from testcontainers.postgres import PostgresContainer

    logger.info("[pipeline] Phase 1 dry-run starting for batch %s", batch_id)

    container: PostgresContainer | None = None
    try:
        container = PostgresContainer("postgres:15-alpine")
        container.start()
        tempdb_url = container.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+psycopg://"
        )

        script_location = f"{worktree_path}/orch/db/migrations" if worktree_path else None
        result = safe_dry_run(tempdb_url, batch_id=batch_id, script_location=script_location)

        if not result.success:
            return PipelineResult(
                phase="dry_run",
                success=False,
                final_batch_state="MIGRATION_INVALID",
                frozen=False,
                message=result.error_message or "Dry-run failed",
            )

        return PipelineResult(
            phase="dry_run",
            success=True,
            final_batch_state="proceed_to_merge",
            frozen=False,
            message=f"Dry-run succeeded ({result.duration_ms}ms)",
        )

    except Exception as exc:
        logger.exception("[pipeline] Phase 1 dry-run error for batch %s", batch_id)
        return PipelineResult(
            phase="dry_run",
            success=False,
            final_batch_state="MIGRATION_INVALID",
            frozen=False,
            message=f"Phase 1 error: {exc}",
        )

    finally:
        if container is not None:
            try:
                container.stop()
            except Exception:
                logger.warning("[pipeline] Failed to stop testcontainer for batch %d", batch_id)


# ---------------------------------------------------------------------------
# Phase 2 — Post-merge apply
# ---------------------------------------------------------------------------


def run_post_merge_apply(batch_id: str | int | None) -> PipelineResult:
    """Phase 2: Apply pending migrations to the live DB after squash-merge.

    On failure *after* one or more revisions were applied → triggers Phase 3
    rollback (``rollback_triggered``).

    On failure *before any revision was applied* — e.g. a SelfBlockerError
    pre-flight trip (I-00063) or a lock timeout — returns
    ``apply_deferred``: there is nothing on the DB to roll back, so a Phase 3
    ``alembic downgrade -1`` would clobber a previously-applied migration
    (this is the post-merge rollback regression seen after the BATCH-00089
    merge on 2026-05-11). The daemon retries Phase 2 on the next merge cycle,
    and the dashboard's alembic guard surfaces any genuinely-pending revision
    until then.

    On success → no state change (item already merged).
    """
    live_url = get_db_url()
    logger.info("[pipeline] Phase 2 apply starting for batch %s", batch_id)

    try:
        result = safe_apply(live_url, batch_id=batch_id)

        if not result.success:
            if result.revisions_applied:
                logger.warning(
                    "[pipeline] Phase 2 apply failed for batch %s after applying "
                    "%s — triggering rollback",
                    batch_id,
                    result.revisions_applied,
                )
                return PipelineResult(
                    phase="apply",
                    success=False,
                    final_batch_state="rollback_triggered",
                    frozen=False,
                    message=result.error_message or "Apply failed",
                    revisions_applied=list(result.revisions_applied),
                )
            logger.warning(
                "[pipeline] Phase 2 apply failed for batch %s before any revision "
                "was applied (%s) — deferring, no rollback",
                batch_id,
                result.error_message or "unknown error",
            )
            return PipelineResult(
                phase="apply",
                success=False,
                final_batch_state="apply_deferred",
                frozen=False,
                message=result.error_message or "Apply deferred (no revision applied)",
                revisions_applied=[],
            )

        return PipelineResult(
            phase="apply",
            success=True,
            final_batch_state="merged",
            frozen=False,
            message=f"Applied successfully ({result.duration_ms}ms)",
            revisions_applied=list(result.revisions_applied),
        )

    except Exception as exc:
        # safe_apply already wrote a pending_migration_log entry and re-raised.
        # Whatever blew up here happened before/around the apply, so nothing was
        # committed to the live DB — do NOT roll back (see revisions_applied note).
        logger.exception("[pipeline] Phase 2 apply error for batch %s", batch_id)
        return PipelineResult(
            phase="apply",
            success=False,
            final_batch_state="apply_deferred",
            frozen=False,
            message=f"Phase 2 error: {exc}",
            revisions_applied=[],
        )


# ---------------------------------------------------------------------------
# Phase 3 — Rollback on apply failure
# ---------------------------------------------------------------------------


def run_rollback(batch_id: str | int | None) -> PipelineResult:
    """Phase 3: Attempt alembic downgrade -1 on the live DB.

    On success → batch marked MIGRATION_ROLLED_BACK.
    On failure → merge_queue_frozen flag set, subsequent merges halted.
    """
    live_url = get_db_url()
    logger.info("[pipeline] Phase 3 rollback starting for batch %s", batch_id)

    try:
        result = safe_rollback(live_url, steps=1, batch_id=batch_id)

        if not result.success:
            set_merge_queue_frozen(
                active=True,
                reason=f"Rollback failed for batch {batch_id}: {result.error_message}",
                acknowledged_by=None,
            )
            return PipelineResult(
                phase="rollback",
                success=False,
                final_batch_state="MIGRATION_ROLLED_BACK",
                frozen=True,
                message=result.error_message or "Rollback failed",
            )

        return PipelineResult(
            phase="rollback",
            success=True,
            final_batch_state="MIGRATION_ROLLED_BACK",
            frozen=False,
            message=f"Rollback succeeded ({result.duration_ms}ms)",
        )

    except Exception as exc:
        logger.exception("[pipeline] Phase 3 rollback error for batch %s", batch_id)
        set_merge_queue_frozen(
            active=True,
            reason=f"Rollback error for batch {batch_id}: {exc}",
            acknowledged_by=None,
        )
        return PipelineResult(
            phase="rollback",
            success=False,
            final_batch_state="MIGRATION_ROLLED_BACK",
            frozen=True,
            message=f"Phase 3 error: {exc}",
        )


# ---------------------------------------------------------------------------
# Merge-queue frozen flag
# ---------------------------------------------------------------------------


def is_merge_queue_frozen(db: Session | None = None) -> bool:
    """Return True if the merge queue is currently frozen.

    Reads the latest daemon_events row with event_type='merge_queue_frozen'
    and returns its metadata.active field (defaults to False).

    Args:
        db: Optional session to use. If not provided, creates its own connection
            to the orch DB (suitable for daemon/CLI context).

    Returns False in test context (IW_CORE_TEST_CONTEXT=true) to avoid
    polluting the test-transaction state with out-of-band connections.
    """
    import os

    if os.environ.get("IW_CORE_TEST_CONTEXT") == "true":
        return False

    _owns_session = False
    try:
        if db is None:
            db_url = get_db_url()
            engine = safe_create_engine(db_url, pool_pre_ping=True)
            session_factory = sessionmaker(bind=engine)
            db = session_factory()
            _owns_session = True
        result = db.execute(
            text(
                "SELECT metadata FROM daemon_events "
                "WHERE event_type = 'merge_queue_frozen' "
                "ORDER BY created_at DESC LIMIT 1"
            )
        )
        row = result.fetchone()
        if row is None:
            return False
        metadata = row[0]
        return bool(metadata.get("active", False)) if metadata else False
    except Exception:
        if not _owns_session and db is not None:
            db.rollback()
        return False
    finally:
        if _owns_session and db is not None:
            db.close()


def set_merge_queue_frozen(
    active: bool,
    reason: str,
    acknowledged_by: str | None = None,
    db: Session | None = None,
) -> None:
    """Write a merge_queue_frozen daemon_events row.

    Used by Phase 3 (on rollback fail) and by the `iw merge-queue unfreeze` CLI.

    Args:
        active: Whether to freeze (True) or unfreeze (False) the queue.
        reason: Human-readable reason for the state change.
        acknowledged_by: Optional operator identifier who acknowledged the freeze.
        db: Optional session to use. If not provided, creates its own connection
            to the orch DB (suitable for daemon/CLI context).
    """
    from orch.db.models import DaemonEvent

    _owns_session = False
    try:
        if db is None:
            db_url = get_db_url()
            engine = safe_create_engine(db_url, pool_pre_ping=True)
            session_factory = sessionmaker(bind=engine)
            db = session_factory()
            _owns_session = True
        metadata: dict[str, Any] = {
            "active": active,
            "reason": reason,
        }
        if acknowledged_by is not None:
            metadata["acknowledged_by"] = acknowledged_by

        event = DaemonEvent(
            project_id=None,
            event_type="merge_queue_frozen",
            entity_id=None,
            entity_type=None,
            message=reason,
            event_metadata=metadata,
        )
        db.add(event)
        db.commit()
    finally:
        if _owns_session and db is not None:
            db.close()
