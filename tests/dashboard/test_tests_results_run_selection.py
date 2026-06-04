"""Regression: the Tests > Results tab must honor the ?run=<id> selector.

Bug: the full-page route ``tests_page`` ignored the ``run`` query parameter, so
the run-selector dropdown (which does a full-page navigation to
``?tab=results&run=<id>``) always rendered the *latest* run's Allure summary and
report link regardless of which run was picked.

Uses a real PostgreSQL testcontainer via the dashboard conftest fixtures.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

# Aliased so pytest does not try to collect the ORM classes as test classes.
from orch.db.models import TestRun as TestRunModel
from orch.db.models import TestRunStatus as RunStatus

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient with test-context flags and get_db overridden to db_session."""
    _original_test = os.environ.pop("IW_CORE_TEST_CONTEXT", None)
    _original_operator = os.environ.pop("IW_CORE_OPERATOR_APPLY", None)
    original_expected = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        os.environ["IW_CORE_TEST_CONTEXT"] = "true"
        os.environ["IW_CORE_OPERATOR_APPLY"] = "true"

        from dashboard.app import create_app
        from dashboard.dependencies import get_db

        app = create_app()

        def _override_get_db() -> Generator[Session, None, None]:
            """Yield the test db_session for FastAPI dependency injection."""
            yield db_session

        app.dependency_overrides[get_db] = _override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if _original_test is not None:
            os.environ["IW_CORE_TEST_CONTEXT"] = _original_test
        else:
            os.environ.pop("IW_CORE_TEST_CONTEXT", None)
        if _original_operator is not None:
            os.environ["IW_CORE_OPERATOR_APPLY"] = _original_operator
        else:
            os.environ.pop("IW_CORE_OPERATOR_APPLY", None)
        if original_expected is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original_expected


def _summary(total: int, passed: int, failed: int) -> dict:
    return {
        "statistic": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": 0,
            "broken": 0,
        },
        "time": {"duration": 1000},
    }


def _report_dir(base: Path, name: str) -> str:
    """Create an on-disk Allure report dir with an index.html; return its path."""
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text("<title>Allure Report</title>", encoding="utf-8")
    return str(d)


@pytest.fixture
def runs(test_project, db_session: Session, tmp_path: Path) -> dict[str, int]:
    """Seed four completed runs:

    * ``summarised``  — older unit run WITH parsed summary stats (10/10) and an
      on-disk report.
    * ``no_summary``  — data-layer run with NO parsed summary but its own
      on-disk report (the common real-world case).
    * ``no_report``   — run whose ``allure_report_dir`` does NOT exist on disk
      (report never persisted) — the link must degrade gracefully.
    * ``latest``      — newest e2e run WITH parsed summary stats and a report.

    Returns a ``{name: run_id}`` map.
    """
    test_project.config = {
        "test_config": {
            "categories": {
                "unit": {"label": "Unit Tests", "command": "make test-unit"},
                "data-layer": {"label": "Data Layer", "command": "make test-data"},
                "e2e": {"label": "E2E Tests", "command": "make test-e2e"},
            }
        }
    }

    now = datetime.now(UTC)
    summarised = TestRunModel(
        project_id=test_project.id,
        category="unit",
        status=RunStatus.passed,
        command="make test-unit",
        run_type="test",
        summary=_summary(total=10, passed=10, failed=0),
        allure_report_dir=_report_dir(tmp_path, "unit"),
        started_at=now - timedelta(hours=4),
        created_at=now - timedelta(hours=4),
    )
    no_summary = TestRunModel(
        project_id=test_project.id,
        category="data-layer",
        status=RunStatus.passed,
        command="make test-data",
        run_type="test",
        summary=None,
        allure_report_dir=_report_dir(tmp_path, "data-layer"),
        started_at=now - timedelta(hours=2),
        created_at=now - timedelta(hours=2),
    )
    no_report = TestRunModel(
        project_id=test_project.id,
        category="data-layer",
        status=RunStatus.passed,
        command="make test-data",
        run_type="test",
        summary=None,
        allure_report_dir=str(tmp_path / "never-generated"),
        started_at=now - timedelta(hours=1),
        created_at=now - timedelta(hours=1),
    )
    latest = TestRunModel(
        project_id=test_project.id,
        category="e2e",
        status=RunStatus.failed,
        command="make test-e2e",
        run_type="test",
        summary=_summary(total=5, passed=2, failed=3),
        allure_report_dir=_report_dir(tmp_path, "e2e"),
        started_at=now - timedelta(minutes=5),
        created_at=now - timedelta(minutes=5),
    )
    db_session.add_all([summarised, no_summary, no_report, latest])
    db_session.commit()
    for r in (summarised, no_summary, no_report, latest):
        db_session.refresh(r)
    return {
        "summarised": summarised.id,
        "no_summary": no_summary.id,
        "no_report": no_report.id,
        "latest": latest.id,
    }


class TestResultsRunSelection:
    """Tests that the Results tab honors the ?run= query parameter for run selection."""

    def test_results_default_shows_latest_run(
        self, client: TestClient, test_project, runs: dict[str, int]
    ) -> None:
        """No ?run= → latest run drives the report link."""
        resp = client.get(f"/project/{test_project.id}/tests?tab=results")
        assert resp.status_code == 200, resp.text
        html = resp.text
        assert f"/tests/report/{runs['latest']}/index.html" in html
        assert f"/tests/report/{runs['summarised']}/index.html" not in html

    def test_results_honors_summarised_run(
        self, client: TestClient, test_project, runs: dict[str, int]
    ) -> None:
        """?run=<summarised> → that run's summary + report link are rendered."""
        target = runs["summarised"]
        resp = client.get(f"/project/{test_project.id}/tests?tab=results&run={target}")
        assert resp.status_code == 200, resp.text
        html = resp.text

        assert f"/tests/report/{target}/index.html" in html, (
            "Open Full Allure Report link does not point at the selected run"
        )
        assert f"/tests/report/{runs['latest']}/index.html" not in html, (
            "Report link still points at the latest run — ?run= was ignored"
        )
        # The selected run's total (10) is rendered in the summary cards.
        assert ">10<" in html, "Selected run's total (10) not rendered"
        assert f'value="{target}"' in html

    def test_results_honors_run_without_summary(
        self, client: TestClient, test_project, runs: dict[str, int]
    ) -> None:
        """The core bug: a selected run with NO parsed summary but its own
        report dir must link to ITS OWN report, not the latest summarised run.
        """
        target = runs["no_summary"]
        resp = client.get(f"/project/{test_project.id}/tests?tab=results&run={target}")
        assert resp.status_code == 200, resp.text
        html = resp.text

        # Report link points at the selected (summary-less) run.
        assert f"/tests/report/{target}/index.html" in html, (
            "Summary-less run does not link to its own Allure report"
        )
        # NOT pinned to the latest run that happens to carry parsed stats.
        assert f"/tests/report/{runs['latest']}/index.html" not in html, (
            "Report link leaked to the latest summarised run"
        )
        assert f"/tests/report/{runs['summarised']}/index.html" not in html
        # Graceful note instead of borrowed summary cards.
        assert "Detailed pass/fail statistics aren't available" in html

    def test_results_run_without_report_on_disk_degrades(
        self, client: TestClient, test_project, runs: dict[str, int]
    ) -> None:
        """A run whose report dir is absent shows 'Report unavailable', not a
        link that would 404 (and never borrows another run's report)."""
        target = runs["no_report"]
        resp = client.get(f"/project/{test_project.id}/tests?tab=results&run={target}")
        assert resp.status_code == 200, resp.text
        html = resp.text

        assert "Report unavailable" in html
        # No report link is emitted at all for this run.
        assert f"/tests/report/{target}/index.html" not in html
        assert f"/tests/report/{runs['latest']}/index.html" not in html
        # The selected run is still identified in the label.
        assert f"Run #{target}" in html
