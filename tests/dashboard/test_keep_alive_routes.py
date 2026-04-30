"""Dashboard route tests for Keep-Alive Scheduler API.

Uses FastAPI TestClient with testcontainer DB session override.
"""

from __future__ import annotations

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
    import os

    # Ensure keep_alive_config row exists before any tests run
    from orch.keep_alive_service import get_config

    get_config(db_session)
    db_session.commit()

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


class TestKeepAlivePage:
    def test_get_keep_alive_page_returns_200(self, client: TestClient) -> None:
        """GET /system/keep-alive returns 200."""
        resp = client.get("/system/keep-alive")
        assert resp.status_code == 200
        assert "Keep-Alive Scheduler" in resp.text


class TestConfigApi:
    def test_post_config_valid(self, client: TestClient) -> None:
        """POST /api/keep-alive/config with valid payload returns 200."""
        resp = client.post(
            "/api/keep-alive/config",
            json={"model": "claude-sonnet-4-6", "window_duration_hours": 5},
        )
        assert resp.status_code == 200

    def test_post_config_invalid_model(self, client: TestClient) -> None:
        """POST /api/keep-alive/config with unknown model returns 422."""
        resp = client.post(
            "/api/keep-alive/config",
            json={"model": "gpt-4", "window_duration_hours": 5},
        )
        assert resp.status_code == 422

    def test_post_config_invalid_duration(self, client: TestClient) -> None:
        """POST /api/keep-alive/config with window outside [3,4,5,6] returns 422."""
        resp = client.post(
            "/api/keep-alive/config",
            json={"model": "claude-sonnet-4-6", "window_duration_hours": 99},
        )
        assert resp.status_code == 422


class TestSlotsApi:
    def test_post_slot_valid(self, client: TestClient) -> None:
        """POST /api/keep-alive/slots with valid time returns 200."""
        resp = client.post(
            "/api/keep-alive/slots",
            json={"time_hhmm": "10:02"},
        )
        assert resp.status_code == 200

    def test_post_slot_invalid_format(self, client: TestClient) -> None:
        """POST /api/keep-alive/slots with invalid format returns 422."""
        resp = client.post(
            "/api/keep-alive/slots",
            json={"time_hhmm": "25:00"},
        )
        assert resp.status_code == 422

    def test_post_slot_duplicate(self, client: TestClient) -> None:
        """POST /api/keep-alive/slots with duplicate time returns 409."""
        client.post("/api/keep-alive/slots", json={"time_hhmm": "10:02"})
        resp = client.post("/api/keep-alive/slots", json={"time_hhmm": "10:02"})
        assert resp.status_code == 409

    def test_delete_slot_not_found(self, client: TestClient) -> None:
        """DELETE /api/keep-alive/slots/99999 returns 404."""
        resp = client.delete("/api/keep-alive/slots/99999")
        assert resp.status_code == 404

    def test_patch_toggle_not_found(self, client: TestClient) -> None:
        """PATCH /api/keep-alive/slots/99999/toggle returns 404."""
        resp = client.patch("/api/keep-alive/slots/99999/toggle")
        assert resp.status_code == 404


class TestRunsApi:
    def test_get_runs_returns_200(self, client: TestClient) -> None:
        """GET /api/keep-alive/runs returns 200."""
        resp = client.get("/api/keep-alive/runs")
        assert resp.status_code == 200
