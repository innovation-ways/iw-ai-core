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
