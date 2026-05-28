"""Integration tests for orch.test_health_service.

Uses a real PostgreSQL testcontainer via the conftest fixtures.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from orch.db.models import TestHealthSnapshot

pytestmark = pytest.mark.integration


class TestCaptureSnapshot:
    """TestHealthSnapshot upsert logic."""

    def test_capture_writes_row(self, db_session, test_project) -> None:
        """capture_snapshot writes one row to the DB."""
        from orch.test_health_service import capture_snapshot

        snapshot = capture_snapshot(
            db_session,
            project_id=test_project.id,
            metric="mutation_score",
            value=85.5,
            meta={"source_shape": "cr-00080"},
        )
        db_session.commit()

        assert snapshot.id is not None
        assert snapshot.project_id == test_project.id
        assert snapshot.metric == "mutation_score"
        assert snapshot.value == 85.5

    def test_idempotent_within_minute(self, db_session, test_project) -> None:
        """Two captures with same (project, metric, ts_minute) produce one row."""
        from orch.test_health_service import capture_snapshot

        snap1 = capture_snapshot(
            db_session,
            project_id=test_project.id,
            metric="coverage_pct",
            value=91.2,
            meta={"threshold": 80},
        )
        db_session.commit()

        # Same call within the same minute — same ts_minute
        snap2 = capture_snapshot(
            db_session,
            project_id=test_project.id,
            metric="coverage_pct",
            value=91.2,
            meta={"threshold": 80},
        )
        db_session.commit()

        assert snap1.id == snap2.id  # Same row returned

        # Only one row exists in the DB
        count = db_session.execute(
            select(func.count())
            .select_from(TestHealthSnapshot)
            .where(
                TestHealthSnapshot.project_id == test_project.id,
                TestHealthSnapshot.metric == "coverage_pct",
            )
        ).scalar_one()
        assert count == 1

    def test_different_metrics_produce_separate_rows(self, db_session, test_project) -> None:
        """Different metric names within the same ts_minute create separate rows."""
        from orch.test_health_service import capture_snapshot

        capture_snapshot(db_session, test_project.id, "mutation_score", 80.0, {})
        capture_snapshot(db_session, test_project.id, "coverage_pct", 88.0, {})
        capture_snapshot(db_session, test_project.id, "flaky_test_count", 3.0, {})
        capture_snapshot(db_session, test_project.id, "assertion_baseline_size", 42.0, {})
        db_session.commit()

        count = db_session.execute(
            select(func.count())
            .select_from(TestHealthSnapshot)
            .where(
                TestHealthSnapshot.project_id == test_project.id,
            )
        ).scalar_one()
        assert count == 4


class TestLatestAndTrend:
    """latest() and trend() query helpers."""

    def test_latest_returns_most_recent_per_metric(self, db_session, test_project) -> None:
        """latest() returns one row per metric, the most recent."""
        from orch.test_health_service import latest

        now = datetime.now(UTC)
        earlier = now - timedelta(hours=2)
        later = now - timedelta(hours=1)

        db_session.add(
            TestHealthSnapshot(
                project_id=test_project.id,
                metric="mutation_score",
                value=70.0,
                meta={},
                ts=earlier,
            )
        )
        db_session.add(
            TestHealthSnapshot(
                project_id=test_project.id,
                metric="mutation_score",
                value=80.0,
                meta={},
                ts=later,
            )
        )
        db_session.add(
            TestHealthSnapshot(
                project_id=test_project.id,
                metric="coverage_pct",
                value=90.0,
                meta={},
                ts=later,
            )
        )
        db_session.commit()

        result = latest(db_session, test_project.id)

        assert "mutation_score" in result
        assert "coverage_pct" in result
        assert result["mutation_score"].value == 80.0
        assert result["coverage_pct"].value == 90.0

    def test_trend_returns_limited_rows_descending(self, db_session, test_project) -> None:
        """trend(limit=30) returns at most 30 rows, newest first."""
        from orch.test_health_service import trend

        now = datetime.now(UTC)
        for i in range(35):
            db_session.add(
                TestHealthSnapshot(
                    project_id=test_project.id,
                    metric="mutation_score",
                    value=float(60 + i),
                    meta={"index": i},
                    ts=now - timedelta(hours=i),
                )
            )
        db_session.commit()

        result = trend(db_session, test_project.id, "mutation_score", limit=30)

        assert len(result) == 30
        # Newest first (ts=now → i=0 → value=60)
        assert result[0].value == 60.0
        # i from 0 to 29 gives values 60 to 89
        assert result[-1].value == 89.0
        # Strictly descending ts
        for i in range(len(result) - 1):
            assert result[i].ts > result[i + 1].ts


class TestCaptureAllFourMetrics:
    """End-to-end: capture all four metrics and verify state."""

    def test_capture_writes_four_snapshots(self, db_session, test_project, tmp_path: Path) -> None:
        """Calling capture_snapshot for all four metrics writes four rows."""
        from orch.test_health_service import capture_snapshot, read_sources

        # Set up artefact files
        (tmp_path / "tests" / "output" / "mutation").mkdir(parents=True)
        (tmp_path / "tests" / "output" / "mutation" / "mutation.json").write_text(
            json.dumps({"score": 82.7, "total": 500, "mutated": 500, "killed": 414})
        )

        (tmp_path / "tests" / "output" / "coverage").mkdir(parents=True)
        (tmp_path / "tests" / "output" / "coverage" / "coverage.json").write_text(
            json.dumps(
                {"totals": {"percent_covered": 91.0, "branch_percent_covered": 80.0}, "files": {}}
            )
        )
        (tmp_path / "pyproject.toml").write_text("[tool.coverage.report]\nfail_under = 80\n")

        flaky_json = tmp_path / "flake_summary.json"
        flaky_json.write_text(
            json.dumps(
                {"flakes": [{"test_id": "tests/a.py::test_1", "outcomes": ["FAILED", "PASSED"]}]}
            )
        )

        (tmp_path / "tests" / "assertion_free_baseline.txt").write_text(
            "tests/b.py::test_b # no-assert\ntests/c.py::test_c # tautology\n"
        )

        sources = read_sources(str(tmp_path), flake_summary_json=flaky_json)

        for metric, data in sources.items():
            if data is None:
                continue
            value, meta = data
            capture_snapshot(db_session, test_project.id, metric, value, meta)
        db_session.commit()

        rows = (
            db_session.execute(
                select(TestHealthSnapshot).where(
                    TestHealthSnapshot.project_id == test_project.id,
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 4

        row_map = {r.metric: r for r in rows}
        assert row_map["mutation_score"].value == 82.7
        assert row_map["coverage_pct"].value == 91.0
        assert row_map["flaky_test_count"].value == 1.0
        assert row_map["assertion_baseline_size"].value == 2.0

    def test_missing_source_skips_that_metric(
        self, db_session, test_project, tmp_path: Path
    ) -> None:
        """When one source is absent, only the available metrics are captured."""
        from orch.test_health_service import capture_snapshot, read_sources

        # Only mutation JSON is present
        (tmp_path / "tests" / "output" / "mutation").mkdir(parents=True)
        (tmp_path / "tests" / "output" / "mutation" / "mutation.json").write_text(
            json.dumps({"score": 75.0, "total": 100, "mutated": 100, "killed": 75})
        )

        sources = read_sources(str(tmp_path))

        captured = []
        skipped = []
        for metric, data in sources.items():
            if data is None:
                skipped.append(metric)
            else:
                value, meta = data
                capture_snapshot(db_session, test_project.id, metric, value, meta)
                captured.append(metric)
        db_session.commit()

        count = db_session.execute(
            select(func.count())
            .select_from(TestHealthSnapshot)
            .where(
                TestHealthSnapshot.project_id == test_project.id,
            )
        ).scalar_one()
        assert count == 1  # Only mutation_score was captured
        assert len(skipped) == 3  # coverage, flaky, baseline absent
        assert len(captured) == 1


class TestJobsAggregatorHook:
    """Verify test-health-capture job rows appear in the unified Jobs view (AC2).

    S05 wires the aggregator to read test_health_snapshots grouped by (project_id, ts_minute),
    showing one job row per capture invocation regardless of how many metrics were written.
    Here we verify the raw rows exist with correct (project_id, ts) for S05 to aggregate.
    """

    def test_capture_writes_four_rows_sharing_same_ts_minute(
        self, db_session, test_project
    ) -> None:
        """All four metric rows share the same ts_minute — aggregator will group by this."""
        from orch.test_health_service import capture_snapshot

        capture_snapshot(db_session, test_project.id, "mutation_score", 85.0, {"shape": "cr-00080"})
        capture_snapshot(db_session, test_project.id, "coverage_pct", 91.0, {"threshold": 80})
        capture_snapshot(
            db_session, test_project.id, "flaky_test_count", 2.0, {"flakes": ["a", "b"]}
        )
        capture_snapshot(
            db_session, test_project.id, "assertion_baseline_size", 30.0, {"total_lines": 50}
        )
        db_session.commit()

        now = datetime.now(UTC)
        ts_minute = now.replace(second=0, microsecond=0)
        rows = (
            db_session.execute(
                select(TestHealthSnapshot).where(
                    TestHealthSnapshot.project_id == test_project.id,
                    TestHealthSnapshot.ts == ts_minute,
                )
            )
            .scalars()
            .all()
        )

        # All four metric rows in the same ts_minute bucket
        metrics_written = {r.metric for r in rows}
        assert metrics_written == {
            "mutation_score",
            "coverage_pct",
            "flaky_test_count",
            "assertion_baseline_size",
        }
