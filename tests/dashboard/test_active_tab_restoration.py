"""Tests verifying that the active-tab localStorage key is namespaced per project."""

from __future__ import annotations

import os
import re
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient with get_db overridden to the test db_session."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            """Yield the test db_session for FastAPI dependency injection."""
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


def test_namespaced_active_tab_key_shape(client: TestClient) -> None:
    """Verifies that _activeTabKey is namespaced by projectId in chat.js."""
    response = client.get("/static/chat_assistant/chat.js")
    assert response.status_code == 200
    text = response.text

    assert "function _activeTabKey(projectId)" in text
    assert "return 'iw-chat-active-tab:' + projectId;" in text


def test_no_legacy_browser_tab_active_tab_storage_key_usage(client: TestClient) -> None:
    """Verifies that the legacy browser-tab-scoped active-tab storage key is removed."""
    response = client.get("/static/chat_assistant/chat.js")
    assert response.status_code == 200
    text = response.text

    assert "iw-chat-active-tab-' + _browserTabId" not in text
    assert re.search(r"sessionStorage\.setItem\(\s*'iw-chat-active-tab-", text) is None
    assert re.search(r"sessionStorage\.getItem\(\s*'iw-chat-active-tab-", text) is None
