"""Shared fixtures for tests/dashboard/routers/.

Provides the `app` fixture with `get_db` overridden to the test transaction's
db_session, so router-level tests hit the testcontainer DB instead of the
guarded live orch DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

# Import so orch.db.session is initialised before IW_CORE_TEST_CONTEXT takes effect
from dashboard.app import create_app

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi import FastAPI
    from sqlalchemy.orm import Session


@pytest.fixture
def app(
    db_session: Session,
    db_session_factory,
) -> Generator[FastAPI, None, None]:
    """FastAPI app with get_db and code_qa.SessionLocal overridden.

    Both the request-scoped session (via FastAPI dependency_overrides) and the
    SSE background thread session (via patching SessionLocal in code_qa) share
    the same _db_test_connection so writes are visible across both paths and
    rolled back on test teardown.
    """
    from dashboard.dependencies import get_db

    app_ = create_app()

    def _override_get_db():
        yield db_session

    app_.dependency_overrides[get_db] = _override_get_db

    with patch("dashboard.routers.code_qa.SessionLocal", db_session_factory):
        yield app_
