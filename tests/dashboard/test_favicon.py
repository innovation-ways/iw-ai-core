"""Tests for GET /favicon.ico route (CR-00044 AC5)."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
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


class TestFaviconRoute:
    """Tests for GET /favicon.ico (CR-00044 AC5)."""

    def test_favicon_ico_returns_200(self, client: TestClient) -> None:
        """GET /favicon.ico returns HTTP 200."""
        resp = client.get("/favicon.ico")
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}"

    def test_favicon_ico_content_type_is_svg(self, client: TestClient) -> None:
        """GET /favicon.ico returns content-type image/svg+xml."""
        resp = client.get("/favicon.ico")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/svg+xml"), (
            f"expected image/svg+xml, got {resp.headers['content-type']}"
        )

    def test_favicon_ico_returns_svg_bytes(self, client: TestClient) -> None:
        """GET /favicon.ico returns the bytes of dashboard/static/favicon.svg."""
        resp = client.get("/favicon.ico")
        assert resp.status_code == 200
        expected_bytes = (
            Path(__file__).resolve().parents[2] / "dashboard" / "static" / "favicon.svg"
        )
        assert expected_bytes.exists(), f"favicon.svg not found at {expected_bytes}"
        assert resp.content == expected_bytes.read_bytes(), (
            "/favicon.ico content does not match dashboard/static/favicon.svg"
        )
