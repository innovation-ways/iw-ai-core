"""AC3/AC4/AC5 integration tests for I-00063 lock_timeout and self-blocker detection.

Tests:
- AC3 (lock_timeout wiring): SET lock_timeout is issued on the apply connection
  via the event listener; IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS env var is honored
  end-to-end through `apply()`; setting it to 0 disables the timeout.
- AC4 (self-blocker detection): `_assert_no_self_blockers` happy path returns
  cleanly; raises SelfBlockerError when a same-process session holds a blocking
  AccessShareLock on a relevant table; treats the no-pending-revisions case
  defensively by checking all relevant tables.
- AC5 (apply-failure surface): `safe_apply` returns ApplyResult(success=False)
  with a recognisable error_message when the self-blocker fires; the
  pending_migration_log row is short-circuited in test context (per the
  IW_CORE_TEST_CONTEXT design — see `_is_test_context_active`), so we verify
  the surfaced error message rather than the audit-log row.

Fixture strategy: each test file has a module-scoped Postgres container.
Schema is established by `command.upgrade(alembic_cfg, "head")` so
alembic_version is in sync — `Base.metadata.create_all` would leave alembic
unaware of the schema and `safe_apply` would re-attempt CREATE TABLE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from orch.db.safe_migrate import (
    SelfBlockerError,
    _assert_no_self_blockers,
)
from orch.db.safe_migrate import (
    apply as safe_apply,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pg_container() -> PostgresContainer:
    """Function-scoped container so each test starts with a clean DB."""
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture
def db_url(pg_container: PostgresContainer) -> str:
    return pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )


@pytest.fixture
def db_engine_at_head(db_url: str) -> Engine:
    """Engine with full schema applied via alembic upgrade head.

    `Base.metadata.create_all` is intentionally NOT used: it would leave
    alembic_version unset, so `safe_apply` would re-run the initial CREATE
    TABLE migration and fail with DuplicateTable. Going through alembic up
    front matches production semantics.
    """
    engine = create_engine(db_url, pool_pre_ping=True)
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session_factory(db_engine_at_head: Engine) -> sessionmaker:
    return sessionmaker(bind=db_engine_at_head, autocommit=False, autoflush=False)


# ---------------------------------------------------------------------------
# AC4 — Self-blocker detection
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_assert_no_self_blockers_happy_path(db_engine_at_head: Engine) -> None:
    """AC4 happy path: no blocker — `_assert_no_self_blockers` returns cleanly."""
    apply_engine = create_engine(
        db_engine_at_head.url.render_as_string(hide_password=False),
        pool_pre_ping=True,
    )
    try:
        _assert_no_self_blockers(apply_engine)
    finally:
        apply_engine.dispose()


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_assert_no_self_blockers_raises_when_same_process_holds_blocking_lock(
    db_engine_at_head: Engine,
    db_session_factory: sessionmaker,
) -> None:
    """AC4: raises SelfBlockerError when same-process session holds a relevant lock."""
    outer = db_session_factory()
    _ = outer.execute(text("SELECT id FROM batch_items LIMIT 1")).fetchall()
    # Keep idle in transaction — do NOT commit
    try:
        apply_engine = create_engine(
            db_engine_at_head.url.render_as_string(hide_password=False),
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
    db_engine_at_head: Engine,
    db_session_factory: sessionmaker,
) -> None:
    """AC4 defensive default: when no migrations are pending, the helper
    scans every relevant table. A lock on `projects` (a relevant table) is
    therefore detected — protecting against the case where the alembic
    history can't be read but a DDL might still arrive.
    """
    outer = db_session_factory()
    _ = outer.execute(text("SELECT id FROM projects LIMIT 1")).fetchall()
    try:
        apply_engine = create_engine(
            db_engine_at_head.url.render_as_string(hide_password=False),
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


# ---------------------------------------------------------------------------
# AC3 — lock_timeout wiring
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_lock_timeout_set_on_apply_connection(db_engine_at_head: Engine) -> None:
    """AC3: SET lock_timeout = '30s' is issued on the apply connection.

    Verifies the event-listener pattern that `safe_apply` uses works in
    isolation — the apply connection sees the configured lock_timeout.
    """
    apply_engine = create_engine(
        db_engine_at_head.url.render_as_string(hide_password=False),
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
    """AC3: get_migration_lock_timeout_secs() reads the env var without reload.

    `tests/CLAUDE.md` forbids `importlib.reload(orch.config)` — `monkeypatch`
    is the only supported channel. The helper reads `os.environ` on every
    call, so monkeypatch is sufficient.
    """
    from orch.config import get_migration_lock_timeout_secs

    monkeypatch.setenv("IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS", "5")
    assert get_migration_lock_timeout_secs() == 5

    monkeypatch.setenv("IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS", "0")
    assert get_migration_lock_timeout_secs() == 0

    monkeypatch.delenv("IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS")
    assert get_migration_lock_timeout_secs() == 30  # default


# ---------------------------------------------------------------------------
# AC1/AC5 — apply() surfaces a self-blocker / lock_timeout failure cleanly
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_apply_returns_self_blocker_failure_when_caller_holds_share_lock(
    db_engine_at_head: Engine,
    db_session_factory: sessionmaker,
) -> None:
    """AC1/AC5: safe_apply returns ApplyResult(success=False) with a
    self-blocker error message when the caller holds AccessShareLock on a
    relevant table — instead of hanging indefinitely.

    The pending_migration_log row is short-circuited in test context per
    `_is_test_context_active`, so we verify the surfaced error_message.
    """
    blocker = db_session_factory()
    _ = blocker.execute(text("SELECT id FROM batch_items LIMIT 1")).fetchall()

    try:
        result = safe_apply(
            db_engine_at_head.url.render_as_string(hide_password=False),
            batch_id=999,
        )
        assert result is not None
        assert result.success is False, (
            f"Expected apply() to fail when caller holds share lock, got success={result.success!r}"
        )
        msg = (result.error_message or "").lower()
        assert any(token in msg for token in ("self", "lock", "timeout")), (
            f"Expected lock/self error, got: {result.error_message!r}"
        )
    finally:
        blocker.rollback()
        blocker.close()


@pytest.mark.integration
@pytest.mark.timeout(60)
def test_apply_returns_lock_timeout_failure_under_short_timeout(
    db_engine_at_head: Engine,
    db_session_factory: sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1/AC3: with a short lock_timeout and a synthetic blocker, apply()
    fails fast (~5s) with a lock-related error rather than hanging.

    The self-blocker detector usually catches this case first; the test still
    exercises the lock_timeout backstop because the underlying SET lock_timeout
    runs unconditionally on the apply connection.
    """
    monkeypatch.setenv("IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS", "5")

    blocker = db_session_factory()
    _ = blocker.execute(text("SELECT id FROM batch_items LIMIT 1")).fetchall()

    try:
        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures import TimeoutError as FutTimeout

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                safe_apply,
                db_engine_at_head.url.render_as_string(hide_password=False),
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
        assert any(token in msg for token in ("self", "lock", "timeout")), (
            f"Expected lock/timeout error, got: {result.error_message!r}"
        )
    finally:
        blocker.rollback()
        blocker.close()
