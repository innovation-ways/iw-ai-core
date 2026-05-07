"""Lightweight smoke tests for the F-00080 help system.

Using FastAPI TestClient (no real browser needed):
  A. /project/{id}/queue → 200 + data-help-slug="queue"
  B. /_help/queue → 200 + all 4 mandatory headings + data-tour-start button
  C. /static/help/help.js → 200 (asset served)
  D. /static/help/tours.js → 200 (asset served)
  E. /static/vendor/driver/driver.js.iife.js → 200 (vendor asset served)

Note: FastAPI TestClient never makes outbound network calls — httpx mocks
must NOT be added in this file, as doing so would hide a regression where
the help system accidentally gains a network dependency.
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


MANDATORY_HEADINGS = [
    "What is this page?",
    "What can I do here?",
    "Vocabulary",
    "Take the 30-second tour",
]


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a TestClient that overrides get_db to use the test db_session."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


class TestHelpSmoke:
    """Smoke tests for F-00080 help system (AC1, AC5)."""

    def test_page_shows_help_button_with_correct_slug(
        self, client: TestClient, test_project
    ) -> None:
        """GET /project/{id}/queue returns 200 and HTML contains data-help-slug="queue"."""
        resp = client.get(f"/project/{test_project.id}/queue")
        assert resp.status_code == 200
        assert 'data-help-slug="queue"' in resp.text, (
            'Queue page HTML should contain data-help-slug="queue" attribute '
            "on the help button (wired by page_help_slug block)"
        )

    def test_help_fragment_returns_correct_content(self, client: TestClient) -> None:
        """GET /_help/queue returns 200, all 4 mandatory headings, and data-tour-start."""
        resp = client.get("/_help/queue")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

        for heading in MANDATORY_HEADINGS:
            assert heading in resp.text, (
                f"Help fragment for queue should contain heading: {heading!r}"
            )

        assert "data-tour-start" in resp.text, "Help fragment should contain data-tour-start button"

    def test_help_js_static_asset_served(self, client: TestClient) -> None:
        """GET /static/help/help.js returns 200 (asset is served by StaticFiles)."""
        resp = client.get("/static/help/help.js")
        assert resp.status_code == 200

    def test_tours_js_static_asset_served(self, client: TestClient) -> None:
        """GET /static/help/tours.js returns 200 (asset is served by StaticFiles)."""
        resp = client.get("/static/help/tours.js")
        assert resp.status_code == 200

    def test_driver_iiife_static_asset_served(self, client: TestClient) -> None:
        """GET /static/vendor/driver/driver.js.iife.js returns 200 (vendor asset reachable)."""
        resp = client.get("/static/vendor/driver/driver.js.iife.js")
        assert resp.status_code == 200
