from __future__ import annotations

import pytest
from _pytest.monkeypatch import MonkeyPatch

from tests.integration.daemon_chaos.harness import ChaosDaemonHarness


def validate_chaos_daemon_request(request) -> None:
    if "db_session" not in request.fixturenames:
        raise RuntimeError("chaos_daemon requires testcontainer-backed db_session fixture")


@pytest.fixture
def chaos_daemon(request, db_session, test_project):
    validate_chaos_daemon_request(request)

    mp = MonkeyPatch()
    harness = ChaosDaemonHarness(db_session=db_session, monkeypatch=mp)
    try:
        yield harness
    finally:
        harness.cleanup()
