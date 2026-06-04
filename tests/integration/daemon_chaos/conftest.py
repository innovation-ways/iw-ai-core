"""Fixtures and guards for the daemon_chaos integration test suite.

Provides the ``chaos_daemon`` fixture that wires a ``ChaosDaemonHarness``
to the testcontainer-backed ``db_session``, and the pre-flight guard that
ensures the fixture is never used without a real DB session.
"""

from __future__ import annotations

import pytest
from _pytest.monkeypatch import MonkeyPatch

from tests.integration.daemon_chaos.harness import ChaosDaemonHarness


def validate_chaos_daemon_request(request) -> None:
    """Raise RuntimeError if db_session is absent from the requesting fixture's scope.

    Args:
        request: The pytest FixtureRequest for the test that requested chaos_daemon.

    Raises:
        RuntimeError: If ``db_session`` is not listed in ``request.fixturenames``,
            indicating the chaos harness would run without a testcontainer DB.
    """
    if "db_session" not in request.fixturenames:
        raise RuntimeError("chaos_daemon requires testcontainer-backed db_session fixture")


@pytest.fixture
def chaos_daemon(request, db_session, test_project):
    """Provide a fully-initialised ChaosDaemonHarness for chaos scenario tests.

    Validates that a testcontainer-backed ``db_session`` is present, constructs
    the harness with monkeypatch isolation, and ensures cleanup (monkeypatch undo
    + harness state reset) runs after each test regardless of outcome.

    Yields:
        ChaosDaemonHarness: A harness instance ready for injection calls and
            ``advance_one_cycle()`` drives.
    """
    validate_chaos_daemon_request(request)

    mp = MonkeyPatch()
    harness = ChaosDaemonHarness(db_session=db_session, monkeypatch=mp)
    try:
        yield harness
    finally:
        harness.cleanup()
