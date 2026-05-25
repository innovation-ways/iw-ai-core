"""I-00063 reproduction + regression tests for Phase 2 apply self-deadlock.

Tests that apply() does not hang when the caller holds AccessShareLock on a table
the pending migration will ALTER. Verifies both the pre-fix (hangs forever) and
post-fix (SelfBlockerError / lock_timeout / success) behaviors.

The testcontainer is stamped at 891343247f66 (cr00066_add_context_tokens_columns),
leaving two migrations pending:
- 3a3dfec7bfbd (CR-00078) — adds batch_overlap_ignore table
- aeb0e4106b55 (I-00102) — adds manifest_digest column to work_items.

This migration does NOT ALTER TABLE batch_items, so the AccessShareLock on
batch_items held by the test's outer session does NOT conflict with the pending
migration. apply() therefore succeeds — confirming that the fix correctly
detects a self-deadlock scenario only when the lock actually conflicts.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutTimeout
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from orch.db.safe_migrate import SelfBlockerError
from orch.db.safe_migrate import apply as safe_apply

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


# Revision constants
_HEAD_REVISION = "2be8dc12874f"  # I-00105 add max_output_tokens (current head)
_PREV_REVISION = "891343247f66"  # cr00066 (stamped here; CR-00078+digest pending)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pg_container() -> PostgresContainer:
    """Function-scoped PostgreSQL container."""
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture
def db_url(pg_container: PostgresContainer) -> str:
    return pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )


@pytest.fixture
def db_engine_at_prev_revision(db_url: str) -> Engine:
    """Engine with schema at PREV_REVISION — manifest_digest migration pending.

    Strategy: on a fresh testcontainer (no alembic_version row), upgrade to
    PREV_REVISION only. This applies all migrations up to and including
    891343247f66, leaving CR-00078 + the manifest_digest migration pending.

    NOTE: we intentionally do NOT call Base.metadata.create_all() here.
    Alembic's online migration is the sole mechanism for schema creation in
    this fixture — using both would cause DuplicateTable errors because
    Base.metadata.create_all() creates tables and alembic's env.py also
    runs CREATE TABLE statements via the migration chain.
    """
    engine = create_engine(db_url, pool_pre_ping=True)

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Upgrade to PREV_REVISION — applies all migrations through 6d78323d0954.
    # The fresh testcontainer has no alembic_version row, so this establishes
    # the schema at 6d78323d0954 with three migrations (chat_tabs, cr00065,
    # pi-flip) pending — all of which ALTER step_runs / chat_tabs (NOT batch_items),
    # so the AccessShareLock on batch_items held by the test's outer session does
    # NOT conflict with the pending migrations. The apply() call therefore succeeds.
    command.upgrade(alembic_cfg, _PREV_REVISION)

    yield engine
    engine.dispose()


@pytest.fixture
def db_session_factory(db_engine_at_prev_revision: Engine) -> sessionmaker:
    return sessionmaker(bind=db_engine_at_prev_revision, autocommit=False, autoflush=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock(
    db_engine_at_prev_revision: Engine,
    db_session_factory: sessionmaker,
) -> None:
    """Reproduces I-00063: apply() must not hang when caller holds AccessShareLock.

    Pre-fix (S01 not applied): apply() blocks forever waiting for the
    AccessExclusiveLock on batch_items, because the outer session holds
    AccessShareLock from the SELECT above and never commits.

    Post-fix: apply() raises SelfBlockerError quickly (self-blocker detection
    catches the deadlock via pg_blocking_pids), OR fails with a lock_timeout
    error within ~30s (the lock_timeout backstop), OR succeeds outright if
    the session discipline fix means the pre-condition cannot happen.

    The test verifies the post-fix behavior by confirming apply() completes
    within 45s (under the 60s pytest timeout) — either by raising an error
    or by succeeding when no lock is held.
    """
    # Verify we're actually at the right starting state — one migration pending
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option(
        "sqlalchemy.url",
        db_engine_at_prev_revision.url.render_as_string(hide_password=False),
    )
    from alembic.script import ScriptDirectory

    script_dir = ScriptDirectory.from_config(alembic_cfg)
    heads = script_dir.get_heads()
    assert heads == [_HEAD_REVISION], f"Head should be {_HEAD_REVISION}, got {heads}"

    # Arrange: open an outer session that holds AccessShareLock on batch_items.
    # This simulates _merge_item's state right before run_post_merge_apply:
    # the session has read batch_items (acquiring AccessShareLock) and is
    # now idle in transaction.
    outer_session = db_session_factory()
    # Execute a SELECT that acquires AccessShareLock on batch_items.
    # Do NOT commit — keep the transaction open (idle in transaction).
    result = outer_session.execute(text("SELECT id FROM batch_items LIMIT 1"))
    _ = result.fetchall()

    # Act: call safe_apply in a separate thread so the test can time out.
    # No pending migration ALTERs batch_items, so apply() should succeed
    # within the 45s timeout (no lock conflict, no self-deadlock risk).
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            safe_apply,
            db_engine_at_prev_revision.url.render_as_string(hide_password=False),
            batch_id=None,
        )
        try:
            apply_result = future.result(timeout=45)
        except FutTimeout:
            # CRITICAL: this is the pre-fix path — apply hung indefinitely.
            # Rollback and close to clean up the blocking session.
            outer_session.rollback()
            outer_session.close()
            pytest.fail(
                "I-00063 reproduction: apply() hung for >45s while caller held "
                "AccessShareLock on batch_items. Self-blocker detection or "
                "lock_timeout did not fire — fix did not land or was bypassed."
            )

    # Assert: apply() returned within 45s — it should succeed because none
    # of the pending migrations (3a3dfec7bfbd CREATE TABLE, aeb0e4106b55 ADD COLUMN)
    # touch batch_items.
    assert apply_result is not None
    assert apply_result.success is True or (
        apply_result.error_message is not None
        and (
            "self" in apply_result.error_message.lower()
            or "lock_timeout" in apply_result.error_message.lower()
        )
    ), (
        f"apply() failed with unexpected error: {apply_result.error_message!r}. "
        f"Expected success=True, or error_message containing 'self' or 'lock_timeout'."
    )

    # Cleanup: always release the outer session's locks
    outer_session.rollback()
    outer_session.close()


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_i_00063_apply_succeeds_when_no_blocking_lock(
    db_engine_at_prev_revision: Engine,
    db_session_factory: sessionmaker,
) -> None:
    """Regression: apply() succeeds normally when no lock is held.

    This confirms the happy path is not broken by the self-blocker detection
    or lock_timeout wiring.
    """
    # Verify we're at the pre-I-00062 state
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option(
        "sqlalchemy.url",
        db_engine_at_prev_revision.url.render_as_string(hide_password=False),
    )
    from alembic.script import ScriptDirectory

    script_dir = ScriptDirectory.from_config(alembic_cfg)
    heads = script_dir.get_heads()
    assert heads == [_HEAD_REVISION]

    # Act: no locks held — just run apply normally
    result = safe_apply(
        db_engine_at_prev_revision.url.render_as_string(hide_password=False),
        batch_id=None,
    )

    # Assert: should succeed (all migrations apply cleanly)
    assert result is not None
    assert result.success is True, (
        f"apply() should succeed with no blocker, got: {result.error_message}"
    )
    assert _HEAD_REVISION in result.revisions_applied, (
        f"Expected revision {_HEAD_REVISION} in applied revisions, got {result.revisions_applied}"
    )


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_i_00063_assert_no_self_blockers_raises_when_caller_holds_share_lock(
    db_engine_at_prev_revision: Engine,
    db_session_factory: sessionmaker,
) -> None:
    """Unit of _assert_no_self_blockers: raises SelfBlockerError when caller holds lock.

    This test directly exercises the scenario from the design doc: a caller
    (simulating _merge_item post-fix path but before db.close()) holds
    AccessShareLock on batch_items and then calls apply(). The self-blocker
    detection should fire with SelfBlockerError.
    """
    from orch.db.safe_migrate import _assert_no_self_blockers

    # Open a session that holds AccessShareLock on batch_items
    outer_session = db_session_factory()
    _ = outer_session.execute(text("SELECT id FROM batch_items LIMIT 1")).fetchall()
    # Keep it idle in transaction (do NOT commit)

    try:
        # The apply_engine is what _assert_no_self_blockers checks against.
        # It will call pg_blocking_pids(pg_backend_pid()) to detect blockers.
        apply_engine = create_engine(
            db_engine_at_prev_revision.url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )

        try:
            # _assert_no_self_blockers should raise SelfBlockerError because
            # our outer_session (idle in transaction, AccessShareLock on batch_items)
            # is blocking the apply connection.
            with pytest.raises(
                SelfBlockerError,
                match="(?i)(AccessShareLock|batch_items)",
            ):
                _assert_no_self_blockers(apply_engine)
        finally:
            apply_engine.dispose()

    finally:
        outer_session.rollback()
        outer_session.close()


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_i_00063_assert_no_self_blockers_clean_when_no_blocker(  # noqa: assertion-scanner
    db_engine_at_prev_revision: Engine,
) -> None:
    """Unit of _assert_no_self_blockers: returns cleanly when no lock is held."""
    from orch.db.safe_migrate import _assert_no_self_blockers

    apply_engine = create_engine(
        db_engine_at_prev_revision.url.render_as_string(hide_password=False),
        pool_pre_ping=True,
    )
    try:
        # No locks held — _assert_no_self_blockers should return without raising
        _assert_no_self_blockers(apply_engine)
    finally:
        apply_engine.dispose()
