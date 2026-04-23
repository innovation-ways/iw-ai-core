# Shared fixtures for all tests.
# Integration-specific fixtures live in tests/integration/conftest.py.

from __future__ import annotations

import pytest


def pytest_sessionfinish(session: object, exitstatus: int) -> None:  # type: ignore[override]
    """Exit 0 when no tests are collected (empty suite is not an error)."""
    if exitstatus == 5:
        session.exitstatus = 0  # type: ignore[union-attr]


@pytest.fixture(autouse=True)
def _isolate_agent_context_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # The daemon sets IW_CORE_AGENT_CONTEXT=true on every agent subprocess
    # (orch/daemon/batch_manager.py). When the QV gate runs `make test-unit`
    # from inside that agent, the var leaks into pytest and every CLI-runner
    # test would see it as 'true', firing the safe_migrate guard with exit 2
    # instead of the command's own exit codes. Tests that need the var present
    # opt in via `monkeypatch.setenv(...)` which runs after this cleanup.
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
