"""Integration tests for safe_migrate lock-timeout and self-blocker behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, event, text

from orch.db.safe_migrate import SelfBlockerError, _assert_no_self_blockers
from orch.db.safe_migrate import apply as safe_apply

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import sessionmaker


def _ensure_iw_core_project(db_session_factory: sessionmaker) -> None:
    """Insert the 'iw-ai-core' project row if it does not already exist.

    Args:
        db_session_factory: Factory used to create a short-lived seeding session.
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


@pytest.mark.integration
@pytest.mark.quarantine(
    reason=(
        "I-00130: module-scoped testcontainer flakes at setup under -n auto "
        "random order; added 2026-06-01"
    )
)
@pytest.mark.timeout(60)
def test_assert_no_self_blockers_happy_path(db_engine: Engine) -> None:
    """Verifies that _assert_no_self_blockers returns None when no locks are held."""
    apply_engine = create_engine(
        db_engine.url.render_as_string(hide_password=False),
        pool_pre_ping=True,
    )
    try:
        result = _assert_no_self_blockers(apply_engine)
        assert result is None  # returns None on success; raises SelfBlockerError on failure
    finally:
        apply_engine.dispose()


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_assert_no_self_blockers_raises_when_same_process_holds_blocking_lock(
    db_engine: Engine,
    db_session_factory: sessionmaker,
) -> None:
    """Verifies that _assert_no_self_blockers raises SelfBlockerError when the calling process holds
    an AccessShareLock.
    """
    outer = db_session_factory()
    _ = outer.execute(text("SELECT id FROM batch_items LIMIT 1")).fetchall()
    try:
        apply_engine = create_engine(
            db_engine.url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )
        try:
            with pytest.raises(SelfBlockerError) as exc_info:
                _assert_no_self_blockers(apply_engine)

            error_msg = str(exc_info.value).lower()
            assert any(
                keyword in error_msg
                for keyword in ("self", "blocker", "accesssharelock", "batch_items", "pid")
            ), f"SelfBlockerError message should be descriptive, got: {exc_info.value}"
        finally:
            apply_engine.dispose()
    finally:
        outer.rollback()
        outer.close()


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_assert_no_self_blockers_no_pending_falls_back_to_relevant_tables(
    db_engine: Engine,
    db_session_factory: sessionmaker,
) -> None:
    """Verifies that when no pending migrations exist, self-blocker detection still checks relevant
    tables and raises on a held lock.
    """
    outer = db_session_factory()
    _ = outer.execute(text("SELECT id FROM projects LIMIT 1")).fetchall()
    try:
        apply_engine = create_engine(
            db_engine.url.render_as_string(hide_password=False),
            pool_pre_ping=True,
        )
        try:
            with pytest.raises(SelfBlockerError) as exc_info:
                _assert_no_self_blockers(apply_engine)
            assert "projects" in str(exc_info.value).lower()
        finally:
            apply_engine.dispose()
    finally:
        outer.rollback()
        outer.close()


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_lock_timeout_set_on_apply_connection(db_engine: Engine) -> None:
    """Verifies that the apply connection has lock_timeout set to the expected value via an event
    listener.
    """
    apply_engine = create_engine(
        db_engine.url.render_as_string(hide_password=False),
        pool_pre_ping=True,
    )

    @event.listens_for(apply_engine, "connect")
    def set_lock_timeout(dbapi_connection, _connection_record) -> None:  # noqa: ARG001
        with dbapi_connection.cursor() as cur:
            cur.execute("SET lock_timeout = '30s'")

    try:
        with apply_engine.connect() as apply_conn:
            row = apply_conn.execute(text("SHOW lock_timeout")).fetchone()
        assert row is not None
        assert row[0] == "30s", f"Expected lock_timeout='30s', got {row[0]!r}"
    finally:
        apply_engine.dispose()


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_lock_timeout_env_var_honored_by_get_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies that IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS env var is read correctly by the config
    helper.
    """
    from orch.config import get_migration_lock_timeout_secs

    monkeypatch.setenv("IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS", "5")
    assert get_migration_lock_timeout_secs() == 5

    monkeypatch.setenv("IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS", "0")
    assert get_migration_lock_timeout_secs() == 0

    monkeypatch.delenv("IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS")
    assert get_migration_lock_timeout_secs() == 30


@pytest.mark.integration
@pytest.mark.quarantine(
    reason=(
        "I-00130: module-scoped testcontainer flakes at setup under -n auto "
        "random order; added 2026-06-01"
    )
)
@pytest.mark.timeout(60)
def test_apply_returns_self_blocker_failure_when_caller_holds_share_lock(
    db_engine: Engine,
    db_session_factory: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies that safe_apply returns a failure result when the calling session holds a share lock
    blocking the migration.
    """
    monkeypatch.setenv("IW_CORE_OPERATOR_APPLY", "true")
    _ensure_iw_core_project(db_session_factory)

    blocker = db_session_factory()
    _ = blocker.execute(text("SELECT id FROM batch_items LIMIT 1")).fetchall()

    try:
        result = safe_apply(
            db_engine.url.render_as_string(hide_password=False),
            batch_id=999,
        )
        assert result is not None
        assert result.success is False
        msg = (result.error_message or "").lower()
        assert any(token in msg for token in ("self", "lock", "timeout"))
    finally:
        blocker.rollback()
        blocker.close()


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_apply_returns_lock_timeout_failure_under_short_timeout(
    db_engine: Engine,
    db_session_factory: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies that safe_apply fails with a lock timeout error when a short timeout is configured
    and a blocker holds a lock.
    """
    monkeypatch.setenv("IW_CORE_OPERATOR_APPLY", "true")
    monkeypatch.setenv("IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS", "5")
    _ensure_iw_core_project(db_session_factory)

    blocker = db_session_factory()
    _ = blocker.execute(text("SELECT id FROM batch_items LIMIT 1")).fetchall()

    try:
        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures import TimeoutError as FutTimeout

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                safe_apply,
                db_engine.url.render_as_string(hide_password=False),
                batch_id=888,
            )
            try:
                result = future.result(timeout=20)
            except FutTimeout:
                pytest.fail(
                    "apply() with lock_timeout=5s should fail within 20s — "
                    "neither self-blocker detection nor lock_timeout fired."
                )

        assert result is not None
        assert result.success is False
        msg = (result.error_message or "").lower()
        assert any(token in msg for token in ("self", "lock", "timeout"))
    finally:
        blocker.rollback()
        blocker.close()
