"""Integration test for I-00059: doc_generation get_job() raw fields.

The detail page at /project/{p}/jobs/doc_generation/{id} reads fields from
job.raw (error, skill_used, duration_seconds, doc_id, ...).
_get_doc_generation was building a stub raw dict with only 3 keys, so all
those fields were None.

This test verifies that get_job(JobType.doc_generation) returns a JobRow
whose raw dict contains the full set of diagnostic fields.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session

from orch.db.models import DocGenerationJob, JobStatus, Project
from orch.jobs.aggregator import JobsAggregator, JobType


class TestI00059DocGenerationGetJobRawFields:
    def test_get_doc_generation_raw_contains_diagnostic_fields(
        self,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """get_job(doc_generation) raw must include error, skill_used,
        duration_seconds, doc_id, trigger_reason, etc."""
        project = Project(
            id="test-proj-i00059",
            display_name="Test Project I-00059",
            repo_root="/repos/test",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project.id,
            doc_id=None,  # intentionally null — FK constraint requires existing project_docs.id
            status=JobStatus.failed,
            error="generation timeout after 15 minutes",
            skill_used="iw-doc-generator",
            duration_seconds=900,
            trigger_reason="manual",
            requested_at=now,
            started_at=now,
            completed_at=now,
            agent_output="Model response truncated",
            lint_warnings=[
                {"rule": "max-line-length", "message": "line too long", "section": "Description"}
            ],
            agent_pid=12345,
        )
        db_session.add(job)
        db_session.flush()
        db_session.commit()

        aggregator = JobsAggregator(db_session)
        row = aggregator.get_job(
            project_id=project.id,
            job_type=JobType.doc_generation,
            job_id=job.id,
        )

        assert row is not None, "get_job returned None for a valid doc_generation job"
        assert row.job_type == JobType.doc_generation
        assert row.job_id == job.id

        # The key assertion: error, skill_used, duration_seconds, doc_id, trigger_reason
        # must be present and non-None in row.raw
        assert row.raw.get("error") == "generation timeout after 15 minutes", (
            f"expected error field in raw, got: {row.raw}"
        )
        assert row.raw.get("skill_used") == "iw-doc-generator", (
            f"expected skill_used in raw, got: {row.raw}"
        )
        assert row.raw.get("duration_seconds") == 900, (
            f"expected duration_seconds in raw, got: {row.raw}"
        )
        assert row.raw.get("doc_id") is None, (
            f"expected doc_id=None in raw (no FK target), got: {row.raw}"
        )
        assert row.raw.get("trigger_reason") == "manual", (
            f"expected trigger_reason in raw, got: {row.raw}"
        )
        assert row.raw.get("status") == "failed"
        assert row.raw.get("agent_output") == "Model response truncated"
        assert row.raw.get("agent_pid") == 12345
        assert row.raw.get("lint_warnings") == [
            {"rule": "max-line-length", "message": "line too long", "section": "Description"}
        ]

    def test_get_doc_generation_raw_triggered_by_field(
        self,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """triggered_by on JobRow should use skill_used when both are set."""
        project = Project(
            id="test-proj-i00059-trigger",
            display_name="Test Project I-00059 Trigger",
            repo_root="/repos/test",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project.id,
            doc_id=None,
            status=JobStatus.completed,
            skill_used="iw-doc-system",
            trigger_reason="batch-merge:B-00042:F-00013",
            duration_seconds=60,
        )
        db_session.add(job)
        db_session.flush()
        db_session.commit()

        aggregator = JobsAggregator(db_session)
        row = aggregator.get_job(
            project_id=project.id,
            job_type=JobType.doc_generation,
            job_id=job.id,
        )

        assert row is not None
        # skill_used takes priority over trigger_reason
        assert row.triggered_by == "iw-doc-system", (
            f"triggered_by should prefer skill_used, got: {row.triggered_by}"
        )
        # Verify raw also contains both
        assert row.raw.get("skill_used") == "iw-doc-system"
        assert row.raw.get("trigger_reason") == "batch-merge:B-00042:F-00013"

    def test_i00059_get_doc_generation_raw_lint_warnings(
        self,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """lint_warnings (a list/JSON field) must survive the get_job raw dict round-trip."""
        project = Project(
            id="test-proj-i00059-lint",
            display_name="Test Project I-00059 Lint",
            repo_root="/repos/test",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project.id,
            doc_id=None,
            status=JobStatus.completed,
            skill_used="iw-doc-generator",
            trigger_reason="manual",
            duration_seconds=120,
            lint_warnings=[
                {
                    "rule": "max-line-length",
                    "message": "line 42 exceeds 120 chars",
                    "section": "Description",
                },
                {
                    "rule": "required-front-matter",
                    "message": "missing front matter in Overview",
                    "section": "Overview",
                },
                {
                    "rule": "broken-link",
                    "message": "href target not found: #nonexistent-anchor",
                    "section": "Prerequisites",
                },
            ],
            agent_output="Generated successfully with 3 lint warnings",
        )
        db_session.add(job)
        db_session.flush()
        db_session.commit()

        aggregator = JobsAggregator(db_session)
        row = aggregator.get_job(
            project_id=project.id,
            job_type=JobType.doc_generation,
            job_id=job.id,
        )

        assert row is not None
        # Verify the entire list is preserved exactly
        expected_warnings = [
            {
                "rule": "max-line-length",
                "message": "line 42 exceeds 120 chars",
                "section": "Description",
            },
            {
                "rule": "required-front-matter",
                "message": "missing front matter in Overview",
                "section": "Overview",
            },
            {
                "rule": "broken-link",
                "message": "href target not found: #nonexistent-anchor",
                "section": "Prerequisites",
            },
        ]
        assert row.raw.get("lint_warnings") == expected_warnings, (
            f"lint_warnings round-trip failed; got: {row.raw.get('lint_warnings')}"
        )
        # Also verify agent_output is intact
        assert row.raw.get("agent_output") == "Generated successfully with 3 lint warnings"

    def test_i00059_get_job_raw_parity_with_list_jobs(
        self,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """get_job and list_jobs must produce identical raw dicts for the same job.

        This is the key regression guard: if someone adds a field to _fetch_doc_generation
        (list path) but forgets _get_doc_generation (detail path), this test catches it
        immediately.
        """
        project = Project(
            id="test-proj-i00059-parity",
            display_name="Test Project I-00059 Parity",
            repo_root="/repos/test",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=project.id,
            doc_id=None,
            status=JobStatus.failed,
            error="index too large: 8192 chunks exceeds 6000 limit",
            skill_used="iw-doc-generator",
            duration_seconds=300,
            trigger_reason="scheduled",
            requested_at=now,
            started_at=now,
            completed_at=now,
            agent_output="Ran out of context window",
            agent_pid=67890,
            lint_warnings=[
                {
                    "rule": "section-order",
                    "message": "Description precedes Overview",
                    "section": "Overview",
                },
            ],
        )
        db_session.add(job)
        db_session.flush()
        db_session.commit()

        aggregator = JobsAggregator(db_session)

        # Fetch via get_job (detail path)
        row_detail = aggregator.get_job(
            project_id=project.id,
            job_type=JobType.doc_generation,
            job_id=job.id,
        )

        # Fetch via list_jobs (list path) and find the same job
        result = aggregator.list_jobs(project_id=project.id, types=[JobType.doc_generation])
        row_list = next((r for r in result.rows if r.job_id == job.id), None)

        assert row_detail is not None, "get_job returned None"
        assert row_list is not None, "list_jobs did not return the job"

        # Parity check: same keys and same values
        assert row_detail.raw.keys() == row_list.raw.keys(), (
            f"raw key sets differ between get_job and list_jobs.\n"
            f"get_job keys:  {sorted(row_detail.raw.keys())}\n"
            f"list_jobs keys: {sorted(row_list.raw.keys())}"
        )

        for key in row_detail.raw:
            assert row_detail.raw.get(key) == row_list.raw.get(key), (
                f"raw['{key}'] differs: get_job={row_detail.raw.get(key)!r} "
                f"vs list_jobs={row_list.raw.get(key)!r}"
            )
