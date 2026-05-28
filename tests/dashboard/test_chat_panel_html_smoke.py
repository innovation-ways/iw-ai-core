from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db_session
        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc
    finally:
        app.dependency_overrides.clear()
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


def test_home_html_and_chat_js_smoke_contract(client: TestClient) -> None:
    home = client.get("/")
    html = home.text
    assert '<select id="chat-assistant-project-select"' in html
    assert '<div id="chat-assistant-context-pct"' in html
    assert "chat-assistant-context-pct__bar" in html

    js = client.get("/static/chat_assistant/chat.js").text
    assert "_currentProjectId" not in js


def test_chat_js_contains_boundary_behavior_guards(client: TestClient) -> None:
    js = client.get("/static/chat_assistant/chat.js").text
    assert js.count("No projects available") == 1
    assert "ignore localStorage failures (private mode/quota)" in js
    assert "localStorage.removeItem('iw-chat-assistant-project')" in js
    assert "_setAssistantProjectId(projects[0].id)" in js
    assert "_loadAssistantProjects()" in js
