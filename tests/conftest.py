# Shared fixtures for all tests.
# Integration-specific fixtures live in tests/integration/conftest.py.


def pytest_sessionfinish(session: object, exitstatus: int) -> None:  # type: ignore[override]
    """Exit 0 when no tests are collected (empty suite is not an error)."""
    if exitstatus == 5:
        session.exitstatus = 0  # type: ignore[union-attr]
