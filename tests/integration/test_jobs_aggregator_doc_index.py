"""Integration tests for doc_indexing job type in JobsAggregator.

Inserts a doc_index_jobs row and verifies list_jobs() returns it with
JobType.doc_indexing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session

from orch.db.models import DocIndexJob, Project
from orch.jobs.aggregator import JobsAggregator, JobType


class TestJobsAggregatorDocIndexing:
    def test_list_jobs_includes_doc_indexing(
        self,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """Insert a doc_index_jobs row → list_jobs() returns it with JobType.doc_indexing."""
        project = Project(
            id="test-proj-agg-doc",
            display_name="Test Project Agg Doc",
            repo_root="/repos/test",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        job = DocIndexJob(
            project_id=project.id,
            status="completed",
            provider="local",
            embed_model="qwen3-embedding:8b",
            index_tier="balanced",
            items_discovered=10,
            items_indexed=8,
            chunks_created=24,
            triggered_at=now,
            started_at=now,
            completed_at=now,
        )
        db_session.add(job)
        db_session.flush()
        db_session.commit()

        aggregator = JobsAggregator(db_session)
        result = aggregator.list_jobs(project_id=project.id, types=[JobType.doc_indexing])

        assert result.total >= 1, f"Expected at least 1 doc_indexing job, got {result.total}"
        doc_rows = [r for r in result.rows if r.job_type == JobType.doc_indexing]
        assert len(doc_rows) == 1, f"Expected exactly 1 doc_indexing row, got {len(doc_rows)}"

        doc_row = doc_rows[0]
        assert doc_row.job_id == job.id
        assert doc_row.status == "completed"
        assert doc_row.started_at is not None
        assert doc_row.finished_at is not None

    def test_list_jobs_no_doc_indexing_type(
        self,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """When types=[code_mapping] only, doc_indexing rows are not returned."""
        project = Project(
            id="test-proj-agg-doc-excl",
            display_name="Test Project Agg Doc Excl",
            repo_root="/repos/test",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        job = DocIndexJob(
            project_id=project.id,
            status="queued",
            triggered_at=now,
        )
        db_session.add(job)
        db_session.flush()
        db_session.commit()

        aggregator = JobsAggregator(db_session)
        result = aggregator.list_jobs(
            project_id=project.id,
            types=[JobType.code_mapping],
        )

        doc_rows = [r for r in result.rows if r.job_type == JobType.doc_indexing]
        assert len(doc_rows) == 0

    def test_list_jobs_sorts_queued_jobs_without_crashing(
        self,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """A queued DocIndexJob has started_at=None. Mixing it with a running
        job (started_at=datetime) must not raise TypeError during sort —
        Python refuses to compare None to datetime. Regression guard for the
        F-00060 S14 browser-verification 500 on /project/{id}/jobs."""
        project = Project(
            id="test-proj-agg-sort-none",
            display_name="Test Project Agg Sort None",
            repo_root="/repos/test",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        queued = DocIndexJob(
            project_id=project.id,
            status="queued",
            triggered_at=now,
            # started_at intentionally omitted — server default is NULL
        )
        running = DocIndexJob(
            project_id=project.id,
            status="running",
            triggered_at=now,
            started_at=now,
        )
        db_session.add_all([queued, running])
        db_session.flush()
        db_session.commit()

        aggregator = JobsAggregator(db_session)

        # Default sort (started_at desc) — this is what the /jobs page hits.
        result = aggregator.list_jobs(
            project_id=project.id,
            types=[JobType.doc_indexing],
        )
        assert result.total == 2
        # Running job (has a timestamp) should come before queued (None) in desc order.
        assert result.rows[0].job_id == running.id
        assert result.rows[1].job_id == queued.id
        assert result.rows[1].started_at is None

        # Ascending direction with None present: None must still bucket to the end.
        result_asc = aggregator.list_jobs(
            project_id=project.id,
            types=[JobType.doc_indexing],
            sort_dir="asc",
        )
        assert result_asc.total == 2
        assert result_asc.rows[0].job_id == running.id
        assert result_asc.rows[1].job_id == queued.id

    def test_get_job_doc_indexing(
        self,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """get_job(type=doc_indexing) returns the correct row."""
        project = Project(
            id="test-proj-agg-doc-get",
            display_name="Test Project Agg Doc Get",
            repo_root="/repos/test",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        job = DocIndexJob(
            project_id=project.id,
            status="running",
            embed_model="test-embed",
            triggered_at=now,
            started_at=now,
        )
        db_session.add(job)
        db_session.flush()
        db_session.commit()

        aggregator = JobsAggregator(db_session)
        row = aggregator.get_job(
            project_id=project.id,
            job_type=JobType.doc_indexing,
            job_id=job.id,
        )

        assert row is not None
        assert row.job_type == JobType.doc_indexing
        assert row.job_id == job.id
        assert row.status == "running"
        assert row.raw.get("embed_model") == "test-embed"

    def test_doc_indexing_title_uses_embed_model_or_tier(
        self,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """Title format: 'Doc index — {embed_model or index_tier or default}'."""
        project = Project(
            id="test-proj-agg-doc-title",
            display_name="Test Project Agg Doc Title",
            repo_root="/repos/test",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)

        job_with_embed = DocIndexJob(
            project_id=project.id,
            status="completed",
            embed_model="nomic-embed-code",
            triggered_at=now,
            completed_at=now,
        )
        job_with_tier = DocIndexJob(
            project_id=project.id,
            status="completed",
            index_tier="quality",
            triggered_at=now,
            completed_at=now,
        )
        job_no_model = DocIndexJob(
            project_id=project.id,
            status="completed",
            triggered_at=now,
            completed_at=now,
        )
        db_session.add(job_with_embed)
        db_session.add(job_with_tier)
        db_session.add(job_no_model)
        db_session.flush()
        db_session.commit()

        aggregator = JobsAggregator(db_session)
        result = aggregator.list_jobs(project_id=project.id, types=[JobType.doc_indexing])

        titles = {r.job_id: r.title for r in result.rows}
        assert any("nomic-embed-code" in t for t in titles.values()), (
            f"Expected embed_model in title, got {titles}"
        )
        assert any("quality" in t for t in titles.values()), (
            f"Expected index_tier in title, got {titles}"
        )
        assert any("default" in t for t in titles.values()), (
            f"Expected 'default' fallback in title, got {titles}"
        )
