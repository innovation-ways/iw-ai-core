# Shared fixtures for all tests.
# Integration-specific fixtures live in tests/integration/conftest.py.

from __future__ import annotations

import os

import pytest

# Pull in the testcontainer fixtures (pg_engine, db_session, test_project, etc.)
# for tests that need them. Property-based tests in tests/unit/properties/ use
# the db_session from tests/integration/conftest.py to drive DB-backed state
# machine property tests (TestWorkItemLifecycle, TestFixCycleCap).
pytest_plugins = ["tests.integration.conftest"]


def pytest_configure(config: pytest.Config) -> None:  # type: ignore[override]
    """Unset IW_CORE_AGENT_CONTEXT before test collection begins.

    This hook runs before pytest imports any test modules. Without this,
    the live_db_guard triggers during collection because IW_CORE_AGENT_CONTEXT
    is inherited from the agent context and the fixture (which unsets it)
    only runs after collection completes.
    """
    os.environ.pop("IW_CORE_AGENT_CONTEXT", None)


def pytest_sessionfinish(session: object, exitstatus: int) -> None:  # type: ignore[override]
    """Exit 0 when no tests are collected (empty suite is not an error)."""
    if exitstatus == 5:
        session.exitstatus = 0  # type: ignore[union-attr]


@pytest.fixture(autouse=True, scope="session")
def _arm_live_db_guard() -> None:
    """Arm the live-DB write guard for the entire pytest session.

    Sets IW_CORE_TEST_CONTEXT=true and clears any operator/daemon opt-in
    flags that might have leaked from the parent shell. Uses os.environ
    directly (NOT monkeypatch) so the flag persists across tests, into
    pytest-xdist workers, into subprocesses, and into testcontainers.

    Additionally HIJACKS IW_CORE_DB_HOST/PORT/USER/PASSWORD/NAME (R0e) to
    point at a non-existent local port. Defense-in-depth: even if a code
    path bypasses every short-circuit added in R0a/R0b/R0d, a `get_db_url()`
    resolution returns an unreachable URL and the connection fails with
    ConnectionRefusedError. Tests that use fixture-supplied URLs (the
    testcontainer's `db_engine.url`) are unaffected — they never read
    these env vars. Tests that explicitly monkeypatch IW_CORE_DB_* (e.g.
    test_db_identity_integration.py) keep working because their per-test
    monkeypatch overrides this session default within their test scope.

    See CR-00022 S17 R0 (and incident I-00041) for context. The previous
    opt-out fixture was the proximate cause of a multi-hour dashboard outage.
    """
    import os

    os.environ["IW_CORE_TEST_CONTEXT"] = "true"
    os.environ.pop("IW_CORE_OPERATOR_APPLY", None)
    os.environ.pop("IW_CORE_DAEMON_CONTEXT", None)
    os.environ.pop("IW_CORE_AGENT_CONTEXT", None)

    # R0e — env hijack: redirect any get_db_url() call to an unreachable
    # address. Port 1 is reserved (RFC 1700) and never has a listener; a
    # connection attempt fails immediately.
    os.environ["IW_CORE_DB_HOST"] = "127.0.0.1"
    os.environ["IW_CORE_DB_PORT"] = "1"
    os.environ["IW_CORE_DB_NAME"] = "iw_orch_test_blocked"
    os.environ["IW_CORE_DB_USER"] = "blocked"
    os.environ["IW_CORE_DB_PASSWORD"] = "blocked"  # noqa: S105

    # R0f — reset lazy engine singletons that may have been created during
    # pytest collection from a per-worktree .env (e.g. IW_CORE_DB_PORT=51396
    # pointing at a stopped per-worktree DB container). Without this, any
    # module that captured `SessionLocal` at import time retains the stale
    # engine and tries to connect to a non-running port, causing Connection
    # Refused in tests that call those modules (e.g. _compute_dirty_count()
    # in dashboard/routers/worktrees.py). Resetting here forces a fresh
    # engine creation with the hijacked port-1 URL on the next call.
    try:
        import orch.db.session as _s

        _s._engine = None
        _s._orch_engine = None
        _s._session_local = None
        _s._orch_session_local = None
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _clear_chat_router_caches() -> None:
    """Reset module-level caches in dashboard.routers.chat between tests.

    The chat router keeps three module-level dicts (``_config_cache``,
    ``_skills_cache`` and ``_providers_cache``) with 30 s TTLs. Under
    pytest-randomly, tests that hit ``/api/chat/config`` against different
    mock OpenCode clients (e.g. ``fake_opencode_server`` returning
    ``fake/model-a`` vs unit mocks returning ``prov-a/model-a``) pollute
    the cache for whichever test runs next on the same ``project_id`` —
    F-00086 expanded the cache-read surface via
    ``_resolve_default_model_for_project`` in the bootstrap path, so the
    leak now surfaces as flaky assertions on the seeded Default tab's
    model. CR-00071 added ``_providers_cache`` (read by ``get_tab`` via
    ``_get_providers_cached`` for ``context_pct`` model-limit lookups);
    a stale providers payload from a prior test makes
    ``lookup_context_window`` miss and ``context_pct`` silently absent.
    Clearing all three caches per-test eliminates the cross-test
    contamination without changing production behaviour.
    """
    try:
        from dashboard.routers import chat as _chat_router
    except Exception:
        # dashboard not importable in this test context (e.g. live-DB
        # guard armed pre-collection); nothing to clear.
        return
    _chat_router._config_cache.clear()
    _chat_router._skills_cache.clear()
    _chat_router._providers_cache.clear()


@pytest.fixture(autouse=True)
def _bypass_live_db_guard_for_unit_tests(request: pytest.FixtureRequest) -> None:
    """Allow unit tests to import orch.db.session without hitting the live-DB guard.

    Unit tests (``tests/unit/``) that need to verify pool configuration via
    ``orch.db.session`` would hit the guard because ``_arm_live_db_guard``
    hi-jacks ``IW_CORE_DB_*`` to 127.0.0.1:1, causing any call to
    ``safe_create_engine`` to raise ``LiveDbConnectionRefusedError``.

    This fixture patches ``safe_create_engine`` ONLY when the requesting test
    lives strictly under ``tests/unit/`` — not ``tests/integration/`` or
    ``tests/dashboard/`` where the real testcontainer must be exercised.
    The guard's own unit tests (``test_live_db_guard.py``) are also excluded
    so they test the real guard, not a mock.
    """
    from pathlib import Path

    unit_root = Path(__file__).resolve().parent / "unit"
    test_path = str(request.fspath.realpath())

    # Only patch for tests under tests/unit/, excluding test_live_db_guard.
    should_patch = (
        test_path.startswith(f"{unit_root}{os.sep}") and "test_live_db_guard" not in test_path
    )

    if not should_patch:
        yield
        return

    from unittest.mock import MagicMock

    from sqlalchemy.pool import QueuePool

    # Build a mock engine with the pool attributes the unit tests expect.
    mock_pool = MagicMock(spec=QueuePool)
    mock_pool.size.return_value = 20
    mock_pool._max_overflow = 20
    mock_pool._recycle = 1800
    mock_pool._timeout = 10

    mock_engine = MagicMock()
    mock_engine.pool = mock_pool

    import orch.db.live_db_guard as ldg
    import orch.db.session as session_module

    orig_ldg = ldg.safe_create_engine
    orig_sess = session_module.safe_create_engine
    try:
        ldg.safe_create_engine = lambda _, **__: mock_engine  # type: ignore[assignment]
        session_module.safe_create_engine = lambda _, **__: mock_engine  # type: ignore[assignment]
        yield
    finally:
        ldg.safe_create_engine = orig_ldg
        session_module.safe_create_engine = orig_sess
