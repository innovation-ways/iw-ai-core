"""Tests verifying that the chat assistant project selector is decoupled from page context."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from bs4 import BeautifulSoup
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


def test_dropdown_renders(client: TestClient) -> None:
    """Verifies that the project selector dropdown renders with a loading placeholder option."""
    response = client.get("/")
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    select = soup.find("select", {"id": "chat-assistant-project-select"})
    assert select is not None
    option = select.find("option") if select else None
    assert option is not None
    assert option.get("value") == ""
    assert option.get_text(strip=True) == "Loading…"
    classes = select.get("class") or []
    assert "text-xs" in classes


def test_chat_js_has_no_current_project_accessor_reference(client: TestClient) -> None:
    """Verifies that the legacy _currentProjectId accessor has been removed from chat.js."""
    response = client.get("/static/chat_assistant/chat.js")
    assert response.status_code == 200
    assert "_currentProjectId" not in response.text
