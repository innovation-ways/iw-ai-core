"""Tests for dashboard/routers/coverage.py — htmx fragment and page rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.services.coverage_service import CoverageView, FileRow, PackageRow

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a TestClient that overrides get_db to use the test db_session."""
    import os

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


class TestCoveragePage:
    """Tests for the coverage dashboard page rendering with various data states."""

    def test_coverage_page_renders_with_data(self, client: TestClient) -> None:
        """Monkeypatch load_coverage to return a populated view; page renders OK."""
        populated = CoverageView(
            available=True,
            error=None,
            overall_line_pct=75.0,
            overall_branch_pct=60.0,
            threshold=80,
            gap_pct=-5.0,
            mtime_iso="2026-04-29T12:00:00Z",
            test_count=220,
            packages=[
                PackageRow(
                    name="orch",
                    line_pct=90.0,
                    branch_pct=80.0,
                    missing_lines=20,
                    badge="green",
                ),
                PackageRow(
                    name="dashboard",
                    line_pct=50.0,
                    branch_pct=None,
                    missing_lines=30,
                    badge="amber",
                ),
            ],
            files_by_package={
                "orch": [
                    FileRow(
                        path="orch/foo.py",
                        line_pct=90.0,
                        branch_pct=80.0,
                        missing_lines=20,
                        badge="green",
                    ),
                ],
                "dashboard": [
                    FileRow(
                        path="dashboard/baz.py",
                        line_pct=50.0,
                        branch_pct=None,
                        missing_lines=30,
                        badge="amber",
                    ),
                ],
            },
        )
        with patch("dashboard.routers.coverage.load_coverage", return_value=populated):
            resp = client.get("/system/coverage")
        assert resp.status_code == 200
        html = resp.text
        assert "Test Coverage" in html
        assert "Overall Lines" in html
        assert "GREEN" in html or "green" in html

    def test_coverage_page_renders_empty_state(self, client: TestClient) -> None:
        """Monkeypatch load_coverage to return available=False; empty state shown."""
        empty = CoverageView(
            available=False,
            error=None,
            overall_line_pct=None,
            overall_branch_pct=None,
            threshold=80,
            gap_pct=None,
            mtime_iso=None,
            test_count=None,
            packages=[],
            files_by_package={},
        )
        with patch("dashboard.routers.coverage.load_coverage", return_value=empty):
            resp = client.get("/system/coverage")
        assert resp.status_code == 200
        html = resp.text
        assert "No coverage data yet" in html
        assert "make test-unit" in html or "make test-parallel" in html

    def test_coverage_files_fragment_renders(self, client: TestClient) -> None:
        """GET /system/coverage/files/orch with a populated view returns the fragment."""
        populated = CoverageView(
            available=True,
            error=None,
            overall_line_pct=75.0,
            overall_branch_pct=60.0,
            threshold=80,
            gap_pct=-5.0,
            mtime_iso="2026-04-29T12:00:00Z",
            test_count=220,
            packages=[
                PackageRow(
                    name="orch",
                    line_pct=90.0,
                    branch_pct=80.0,
                    missing_lines=20,
                    badge="green",
                ),
            ],
            files_by_package={
                "orch": [
                    FileRow(
                        path="orch/foo.py",
                        line_pct=90.0,
                        branch_pct=80.0,
                        missing_lines=20,
                        badge="green",
                    ),
                    FileRow(
                        path="orch/bar.py",
                        line_pct=100.0,
                        branch_pct=100.0,
                        missing_lines=0,
                        badge="green",
                    ),
                ],
            },
        )
        with patch("dashboard.routers.coverage.load_coverage", return_value=populated):
            resp = client.get("/system/coverage/files/orch")
        assert resp.status_code == 200
        html = resp.text
        assert "orch/foo.py" in html
        assert "orch/bar.py" in html

    def test_coverage_files_fragment_404_unknown_package(self, client: TestClient) -> None:
        """GET /system/coverage/files/nope with a populated view returns 404."""
        populated = CoverageView(
            available=True,
            error=None,
            overall_line_pct=75.0,
            overall_branch_pct=60.0,
            threshold=80,
            gap_pct=-5.0,
            mtime_iso="2026-04-29T12:00:00Z",
            test_count=220,
            packages=[],
            files_by_package={
                "orch": [
                    FileRow(
                        path="orch/foo.py",
                        line_pct=90.0,
                        branch_pct=80.0,
                        missing_lines=20,
                        badge="green",
                    ),
                ],
            },
        )
        with patch("dashboard.routers.coverage.load_coverage", return_value=populated):
            resp = client.get("/system/coverage/files/nope")
        assert resp.status_code == 404

    def test_coverage_page_in_system_nav(self, client: TestClient) -> None:
        """GET /system/status — response HTML contains /system/coverage link and label."""
        resp = client.get("/system/status")
        assert resp.status_code == 200
        html = resp.text
        assert "/system/coverage" in html
        assert "Test Coverage" in html
