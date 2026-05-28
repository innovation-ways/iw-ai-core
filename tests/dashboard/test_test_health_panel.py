"""Dashboard integration tests for the test-health htmx fragment endpoint (CR-00086 S05).

Uses a real PostgreSQL testcontainer via the dashboard conftest fixtures.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from sqlalchemy.orm.sessionmaker import sessionmaker


@pytest.fixture
def client(
    db_session: Session,
    db_session_factory: sessionmaker,
) -> Generator[TestClient, None, None]:
    """FastAPI TestClient wired to the testcontainer db_session.

    IW_CORE_TEST_CONTEXT and IW_CORE_OPERATOR_APPLY must both be set so that
    dashboard.app imports don't trigger the live-DB guard (which blocks
    connection attempts to the production orch DB on port 5433).

    db_session is the shared test session (bound to the same connection as
    db_session_factory). The factory is passed to background SSE threads via
    SessionLocal patching so they share the same connection pool.
    """
    _original_test = os.environ.pop("IW_CORE_TEST_CONTEXT", None)
    _original_operator = os.environ.pop("IW_CORE_OPERATOR_APPLY", None)
    original_expected = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        os.environ["IW_CORE_TEST_CONTEXT"] = "true"
        os.environ["IW_CORE_OPERATOR_APPLY"] = "true"

        from unittest.mock import patch

        from dashboard.app import create_app
        from dashboard.dependencies import get_db

        app = create_app()

        def _override_get_db() -> Generator[Session, None, None]:
            yield db_session

        app.dependency_overrides[get_db] = _override_get_db

        # Patch SessionLocal so SSE background threads share the same
        # connection as db_session (writes done in the test are visible to
        # SSE callbacks without an extra round-trip).
        with (
            patch("dashboard.routers.code_qa.SessionLocal", db_session_factory),
            TestClient(app, raise_server_exceptions=True) as c,
        ):
            yield c

        app.dependency_overrides.clear()
    finally:
        os.environ.pop("IW_CORE_TEST_CONTEXT", None)
        os.environ.pop("IW_CORE_OPERATOR_APPLY", None)
        if original_expected is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original_expected


class TestTestHealthPanel:
    """Test the GET /project/{project_id}/test-health fragment endpoint."""

    def test_panel_combined_empty_state(self, client: TestClient, test_project) -> None:
        """No snapshots — expect ONE combined empty-state message, no per-metric placeholders."""
        response = client.get(f"/project/{test_project.id}/test-health")
        assert response.status_code == 200, response.text
        html = response.text

        assert "Test health data will appear after the first capture runs" in html
        # No per-metric "no data yet" placeholders
        assert "no data yet" not in html.lower()
        # No SVG tags
        assert "<svg" not in html

    def test_panel_renders_with_snapshots(
        self, client: TestClient, test_project, db_session: Session
    ) -> None:
        """Seed 4 metrics with 5 snapshots each; GET returns 200 + 4 metric labels + 4 <svg>."""
        from datetime import UTC, datetime

        from orch.db.models import TestHealthSnapshot

        # Seed 5 snapshots per metric
        base_ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        metrics = [
            ("mutation_score", [72.1, 73.2, 74.0, 74.8, 75.5]),
            ("coverage_pct", [88.0, 88.5, 89.1, 89.3, 90.0]),
            ("flaky_test_count", [3, 3, 2, 2, 1]),
            ("assertion_baseline_size", [142, 145, 148, 151, 155]),
        ]

        for metric, values in metrics:
            for i, value in enumerate(values):
                ts = base_ts.replace(minute=i)
                snap = TestHealthSnapshot(
                    project_id=test_project.id,
                    metric=metric,
                    value=value,
                    ts=ts,
                    meta={},
                )
                db_session.add(snap)
        db_session.flush()
        db_session.commit()

        response = client.get(f"/project/{test_project.id}/test-health")
        assert response.status_code == 200, response.text
        html = response.text

        # All 4 metric labels present (exact label as rendered in template)
        from dashboard.routers._test_health_helpers import METRICS

        for _, expected_label, _ in METRICS:
            assert expected_label in html, f"Missing label {expected_label!r}"

        # Latest values shown (last element in each list)
        assert "75.5" in html  # mutation_score
        assert "90.0" in html  # coverage_pct
        assert "1" in html  # flaky_test_count (lowest)
        assert "155" in html  # assertion_baseline_size

        # 4 sparkline SVGs (fixed viewBox "0 0 80 28" from build_sparkline_svg).
        # Delta arrow SVGs use "0 0 24 24" — filter them out.
        assert html.count('viewBox="0 0 80 28"') == 4, (
            f"Expected 4 sparkline SVGs, got {html.count('viewBox="0 0 80 28"')}"
        )
        # SVG path commands: one per sparkline (M ... L ...)
        assert html.count("M ") >= 4, (
            f"Expected at least 4 SVG path commands, got {html.count('M ')}"
        )
        # No empty-state placeholders
        assert "no data yet" not in html.lower()

    def test_panel_empty_state_per_metric(
        self, client: TestClient, test_project, db_session: Session
    ) -> None:
        """Seed only mutation_score; expect 3 'no data yet' placeholders + 1 SVG for mutation."""
        from datetime import UTC, datetime

        from orch.db.models import TestHealthSnapshot

        base_ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        for i, value in enumerate([70.0, 71.0, 72.0]):
            ts = base_ts.replace(minute=i)
            snap = TestHealthSnapshot(
                project_id=test_project.id,
                metric="mutation_score",
                value=value,
                ts=ts,
                meta={},
            )
            db_session.add(snap)
        db_session.flush()
        db_session.commit()

        response = client.get(f"/project/{test_project.id}/test-health")
        assert response.status_code == 200, response.text
        html = response.text

        # 3 "no data yet" placeholders (for coverage, flaky, baseline — no data)
        assert html.count("no data yet") == 3, (
            f"Expected 3 'no data yet', got {html.count('no data yet')}"
        )
        # 1 sparkline SVG (mutation_score card has data)
        # The panel has delta arrow SVGs too, so we count sparklines by their
        # fixed viewBox dimension that the helper always emits.
        assert html.count('viewBox="0 0 80 28"') == 1, (
            f"Expected 1 sparkline SVG, got {html.count('viewBox="0 0 80 28"')}"
        )
        # No combined empty-state message
        assert "Test health data will appear after the first capture runs" not in html

    def test_tests_page_mounts_panel(
        self, client: TestClient, test_project, db_session: Session
    ) -> None:
        """GET /project/{project_id}/tests — body contains the htmx mount block for test-health."""
        test_project.config = {
            "test_config": {
                "categories": {
                    "unit": {
                        "label": "Unit Tests",
                        "command": "make test-unit",
                        "description": "Unit tests",
                    }
                }
            }
        }
        db_session.commit()

        response = client.get(f"/project/{test_project.id}/tests")
        assert response.status_code == 200, response.text
        html = response.text

        # htmx mount block
        assert f"/project/{test_project.id}/test-health" in html
        assert "hx-get" in html
        assert 'hx-trigger="load"' in html
