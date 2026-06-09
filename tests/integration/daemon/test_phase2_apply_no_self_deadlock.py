"""I-00063 regression tests for Phase 2 apply self-deadlock behavior."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutTimeout
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from orch.db.safe_migrate import SelfBlockerError
from orch.db.safe_migrate import apply as safe_apply

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import sessionmaker


def _ensure_iw_core_project(db_session_factory: sessionmaker) -> None:
    """Insert the iw-ai-core project row if it does not already exist.

    Args:
        db_session_factory: A SQLAlchemy sessionmaker bound to the testcontainer engine.
    """
    seed = db_session_factory()
    try:
        seed.execute(
            text(
                """
                INSERT INTO projects (id, display_name, repo_root, config)
                VALUES ('iw-ai-core', 'IW AI Core', '/tmp/iw-ai-core', '{}'::jsonb)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        seed.commit()
    finally:
        seed.close()


_HEAD_REVISION = (
    "65084ea7e4b4"  # MUST update this constant whenever a new migration is added to main —
)
# see CLAUDE.md migration section (CR-00095)
_PREV_REVISION = "76250ecb2593"


@pytest.fixture
def db_engine_at_prev_revision(db_engine: Engine) -> Engine:
    """Downgrade the testcontainer DB to _PREV_REVISION and return the engine.

    Yields:
        The same Engine after Alembic has downgraded the schema to ``_PREV_REVISION``.
    """
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option(
        "sqlalchemy.url", db_engine.url.render_as_string(hide_password=False)
    )
    command.downgrade(alembic_cfg, _PREV_REVISION)
    return db_engine


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock(
    db_engine_at_prev_revision: Engine,
    db_session_factory: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies that safe_apply completes without deadlocking when a caller holds an
    AccessShareLock.
    """
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

    monkeypatch.setenv("IW_CORE_OPERATOR_APPLY", "true")
    _ensure_iw_core_project(db_session_factory)

    outer_session = db_session_factory()
    result = outer_session.execute(text("SELECT id FROM batch_items LIMIT 1"))
    _ = result.fetchall()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            safe_apply,
            db_engine_at_prev_revision.url.render_as_string(hide_password=False),
            batch_id=None,
        )
        try:
            apply_result = future.result(timeout=45)
        except FutTimeout:
            outer_session.rollback()
            outer_session.close()
            pytest.fail(
                "I-00063 reproduction: apply() hung for >45s while caller held "
                "AccessShareLock on batch_items."
            )

    assert apply_result is not None
    assert apply_result.success is True or (
        apply_result.error_message is not None
        and (
            "self" in apply_result.error_message.lower()
            or "lock_timeout" in apply_result.error_message.lower()
        )
    )

    outer_session.rollback()
    outer_session.close()


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_i_00063_apply_succeeds_when_no_blocking_lock(
    db_engine_at_prev_revision: Engine,
    db_session_factory: sessionmaker,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies that safe_apply succeeds and applies the head revision when no competing lock is
    held.
    """
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

    monkeypatch.setenv("IW_CORE_OPERATOR_APPLY", "true")
    _ensure_iw_core_project(db_session_factory)

    result = safe_apply(
        db_engine_at_prev_revision.url.render_as_string(hide_password=False),
        batch_id=None,
    )

    assert result is not None
    assert result.success is True, (
        f"apply() should succeed with no blocker, got: {result.error_message}"
    )
    assert _HEAD_REVISION in result.revisions_applied


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_i_00063_assert_no_self_blockers_raises_when_caller_holds_share_lock(
    db_engine_at_prev_revision: Engine,
    db_session_factory: sessionmaker,
) -> None:
    """Verifies that _assert_no_self_blockers raises SelfBlockerError when the caller holds a share
    lock.
    """
    from orch.db.safe_migrate import _assert_no_self_blockers

    outer_session = db_session_factory()
    _ = outer_session.execute(text("SELECT id FROM batch_items LIMIT 1")).fetchall()

    try:
        apply_engine = create_engine(
            db_engine_at_prev_revision.url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )

        try:
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
@pytest.mark.quarantine(
    reason=(
        "I-00130: module-scoped testcontainer flakes at setup under -n auto "
        "random order; added 2026-06-01"
    )
)
@pytest.mark.timeout(60)
def test_i_00063_assert_no_self_blockers_clean_when_no_blocker(
    db_engine_at_prev_revision: Engine,
) -> None:
    """Verifies that _assert_no_self_blockers returns None when no competing lock exists."""
    from orch.db.safe_migrate import _assert_no_self_blockers

    apply_engine = create_engine(
        db_engine_at_prev_revision.url.render_as_string(hide_password=False),
        pool_pre_ping=True,
    )
    try:
        result = _assert_no_self_blockers(apply_engine)
        assert result is None  # returns None on success; raises SelfBlockerError on failure
    finally:
        apply_engine.dispose()
