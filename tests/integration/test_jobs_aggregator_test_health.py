"""Integration tests for the test-health job type in the Jobs aggregator.

Uses a real PostgreSQL testcontainer via the integration conftest fixtures.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.integration


class TestJobsAggregatorTestHealth:
    """Verify test-health-capture rows appear in the unified Jobs view (AC2)."""

    def test_capture_appears_in_jobs_view(self, db_session, test_project) -> None:
        """Aggregator returns one 'test-health-capture' row per capture minute (AC2)."""
        from orch.db.models import TestHealthSnapshot
        from orch.jobs.aggregator import JobsAggregator, JobType

        # Seed one snapshot per metric (all same ts → same minute → ONE job row)
        ts = datetime(2025, 3, 15, 14, 30, 0, tzinfo=UTC)

        for metric in [
            "mutation_score",
            "coverage_pct",
            "flaky_test_count",
            "assertion_baseline_size",
        ]:
            snap = TestHealthSnapshot(
                project_id=test_project.id,
                metric=metric,
                value=75.0,
                ts=ts,
                meta={},
            )
            db_session.add(snap)
        db_session.commit()

        aggregator = JobsAggregator(db_session)
        result = aggregator.list_jobs(project_id=test_project.id)

        job_types = [row.job_type for row in result.rows]
        assert "test-health-capture" in job_types, f"Expected 'test-health-capture' in {job_types}"

    def test_multiple_captures_one_job_row_per_minute(self, db_session, test_project) -> None:
        """Two captures in the same minute produce ONE job row, not four."""
        from orch.db.models import TestHealthSnapshot
        from orch.jobs.aggregator import JobsAggregator, JobType

        ts = datetime(2025, 3, 15, 14, 30, 0, tzinfo=UTC)

        # First capture: 2 metrics
        for metric in ["mutation_score", "coverage_pct"]:
            snap = TestHealthSnapshot(
                project_id=test_project.id,
                metric=metric,
                value=75.0,
                ts=ts,
                meta={},
            )
            db_session.add(snap)

        # Second capture: same minute, 2 more metrics
        for metric in ["flaky_test_count", "assertion_baseline_size"]:
            snap = TestHealthSnapshot(
                project_id=test_project.id,
                metric=metric,
                value=10.0,
                ts=ts,
                meta={},
            )
            db_session.add(snap)
        db_session.commit()

        aggregator = JobsAggregator(db_session)
        result = aggregator.list_jobs(project_id=test_project.id)

        th_job_rows = [row for row in result.rows if row.job_type == "test-health-capture"]
        assert len(th_job_rows) == 1, (
            f"Expected exactly 1 'test-health-capture' row (same minute), got {len(th_job_rows)}"
        )

    def test_capture_different_minutes_produces_multiple_rows(
        self, db_session, test_project
    ) -> None:
        """Captures in different minutes produce multiple job rows."""
        from orch.db.models import TestHealthSnapshot
        from orch.jobs.aggregator import JobsAggregator

        ts1 = datetime(2025, 3, 15, 14, 30, 0, tzinfo=UTC)
        ts2 = datetime(2025, 3, 15, 15, 30, 0, tzinfo=UTC)

        for metric in ["mutation_score", "coverage_pct"]:
            snap = TestHealthSnapshot(
                project_id=test_project.id,
                metric=metric,
                value=75.0,
                ts=ts1,
                meta={},
            )
            db_session.add(snap)

        snap2 = TestHealthSnapshot(
            project_id=test_project.id,
            metric="mutation_score",
            value=76.0,
            ts=ts2,
            meta={},
        )
        db_session.add(snap2)
        db_session.commit()

        aggregator = JobsAggregator(db_session)
        result = aggregator.list_jobs(project_id=test_project.id)

        th_job_rows = [row for row in result.rows if row.job_type == "test-health-capture"]
        assert len(th_job_rows) == 2, (
            f"Expected 2 'test-health-capture' rows (different minutes), got {len(th_job_rows)}"
        )
