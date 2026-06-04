"""I-00057 regression tests: chat panel ships collapsed; no floating toggle tab.

These tests verify:
1. The chat panel renders with data-collapsed='true' (user lands on slim rail)
2. The old floating toggle button (style='left: -48px') is gone
3. Both collapse and expand affordances are labelled for accessibility
"""

from __future__ import annotations

import os
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
    """Create a TestClient that overrides get_db to use the test db_session."""

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


def test_i00057_chat_panel_ships_collapsed(client: TestClient, test_project) -> None:
    """RED until I-00057 lands. Asserts the chat panel renders with
    data-collapsed='true' so the user lands on a slim rail, not a wide
    open panel.
    """
    resp = client.get(f"/project/{test_project.id}/code")
    assert resp.status_code == 200
    html = resp.text
    assert 'id="chat-panel"' in html
    assert 'data-collapsed="true"' in html, (
        "Chat panel must ship with data-collapsed='true' so it renders collapsed"
    )
    assert 'data-collapsed="false"' not in html, (
        "Chat panel must not have data-collapsed='false' on initial render"
    )


def test_i00057_no_floating_left_minus_48_toggle(client: TestClient, test_project) -> None:
    """Guards against the absolute-positioned tab pattern returning.

    Original bug: <button id="chat-toggle-tab" style="left: -48px;">
    This pattern clutters the viewport with an orphaned floating button.
    """
    resp = client.get(f"/project/{test_project.id}/code")
    assert resp.status_code == 200
    html = resp.text
    assert 'style="left: -48px;"' not in html, (
        "Floating toggle button with style='left: -48px;' must not be present. "
        "Collapse/expand affordances should live inside #chat-panel."
    )
    assert 'id="chat-toggle-tab"' not in html, (
        "The #chat-toggle-tab id must not exist — the old floating toggle pattern "
        "is gone; collapse/expand affordances are now inside #chat-panel."
    )


def test_i00057_collapse_and_expand_affordances_present(client: TestClient, test_project) -> None:
    """Both modes must offer a labelled control to toggle state."""
    resp = client.get(f"/project/{test_project.id}/code")
    assert resp.status_code == 200
    html = resp.text
    # Collapse affordance (in the expanded header)
    assert 'aria-label="Collapse chat panel' in html, (
        "Expanded panel must have a labelled collapse control"
    )
    # Expand affordance (in the collapsed rail)
    assert 'aria-label="Expand chat panel' in html, (
        "Collapsed rail must have a labelled expand control"
    )
