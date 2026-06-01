from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from sqlalchemy import event, text

from orch.daemon import main as daemon_main
from orch.db import session as db_session


def _build_session_factory_and_engine(monkeypatch, db_engine):
    """Build daemon session factory and resolve the backing engine."""
    monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
    db_url = db_engine.url.render_as_string(hide_password=False)

    monkeypatch.setattr("orch.config.get_db_url", lambda: db_url)
    monkeypatch.setattr(db_session, "_engine", None)
    monkeypatch.setattr(db_session, "_session_local", None)

    session_factory = daemon_main.create_session_factory(db_url)
    engine = db_session._get_engine()
    return session_factory, engine


def test_i00123_daemon_session_factory_physical_connects_bounded_under_hot_concurrency(
    monkeypatch, db_engine
):
    """Regression: daemon hot path must not churn physical connects under concurrent load."""
    monkeypatch.setenv("IW_CORE_DB_POOL_SIZE", "20")
    monkeypatch.setenv("IW_CORE_DB_MAX_OVERFLOW", "20")

    session_factory, engine = _build_session_factory_and_engine(monkeypatch, db_engine)

    try:
        physical_connects = 0
        count_lock = Lock()

        @event.listens_for(engine.pool, "connect")
        def _on_connect(dbapi_conn, conn_record):  # noqa: ARG001
            nonlocal physical_connects
            with count_lock:
                physical_connects += 1

        pool_size = engine.pool.size()
        max_overflow = engine.pool._max_overflow  # noqa: SLF001
        pool_ceiling = pool_size + max_overflow

        concurrent_calls = min(20, pool_size)
        rounds = 25

        def _invoke_hot_path_once() -> None:
            with session_factory() as session:
                session.execute(text("SELECT pg_sleep(0.02)"))

        with ThreadPoolExecutor(max_workers=concurrent_calls) as executor:
            for _ in range(rounds):
                futures = [executor.submit(_invoke_hot_path_once) for _ in range(concurrent_calls)]
                for future in futures:
                    future.result()

        assert physical_connects <= pool_ceiling, (
            "Expected physical connects <= pool ceiling "
            f"({pool_ceiling}), got {physical_connects}. "
            "Expected session factory to reuse pooled connections under repeated load."
        )
    finally:
        engine.dispose()


def test_i00123_daemon_session_factory_reuses_idle_connection_without_new_connect(
    monkeypatch, db_engine
):
    """Second checkout should reuse idle pooled connection (no extra physical connect)."""
    monkeypatch.setenv("IW_CORE_DB_POOL_SIZE", "20")
    monkeypatch.setenv("IW_CORE_DB_MAX_OVERFLOW", "20")

    session_factory, engine = _build_session_factory_and_engine(monkeypatch, db_engine)

    try:
        physical_connects = 0
        count_lock = Lock()

        @event.listens_for(engine.pool, "connect")
        def _on_connect(dbapi_conn, conn_record):  # noqa: ARG001
            nonlocal physical_connects
            with count_lock:
                physical_connects += 1

        with session_factory() as session:
            session.execute(text("SELECT 1"))

        connects_after_first_checkout = physical_connects
        assert connects_after_first_checkout == 1

        with session_factory() as session:
            session.execute(text("SELECT 1"))

        assert physical_connects == connects_after_first_checkout
    finally:
        engine.dispose()
