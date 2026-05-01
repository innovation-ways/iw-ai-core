"""I-00058: DocGenerationJob public_id — reproduction + regression tests.

These tests prove:
1. RED:  The bug existed (would fail on pre-fix code)
2. GREEN: The fix works (pass after public_id column + before_insert listener)

Semantic correctness rules (I-00058 lessons from I-002):
  - BAD:  assert job.public_id is not None        (shape only — checks non-null)
  - GOOD: assert job.public_id == "DOC-00001"     (exact value)
  - GOOD: assert re.match(r"^DOC-\\d{5}$", ...)    (format check)
  - GOOD: assert not job.public_id.startswith("{")  (NOT a UUID)

See: ai-dev/active/I-00058/I-00058_Issue_Design.md
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from orch.db.models import (
    DocGenerationJob,
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    JobStatus,
    Project,
)
from orch.doc_service import DocService
from orch.jobs.aggregator import JobsAggregator, JobType

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
DOC_PUBLIC_ID_PATTERN = re.compile(r"^DOC-\d{5}$")


def _make_project(session: Session, project_id: str = "test-proj") -> Project:
    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    session.add(project)
    session.flush()
    return project


# ---------------------------------------------------------------------------
# RED PHASE — Reproduction tests (fail before fix, pass after)
# ---------------------------------------------------------------------------


def test_i00058_public_id_exactly_doc_00001_on_first_insert(
    db_session: Session,
) -> None:
    """First DocGenerationJob in a clean DB gets public_id = DOC-00001.

    RED: FAILS before fix (AttributeError: 'DocGenerationJob' has no 'public_id')
    GREEN: PASSES after fix adds the column + before_insert listener.
    """
    _make_project(db_session)

    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="test-proj",
        status=JobStatus.queued,
    )
    db_session.add(job)
    db_session.flush()  # triggers before_insert listener

    # MUST be exactly DOC-00001, not None, not a UUID, not any other value
    assert job.public_id == "DOC-00001", f"Expected exactly 'DOC-00001', got {job.public_id!r}"


def test_i00058_public_id_format_is_doc_nnnnn_not_uuid(
    db_session: Session,
) -> None:
    """public_id must match r'^DOC-\\d{5}$' — it is NOT a UUID.

    RED: FAILS before fix (AttributeError or public_id is None)
    GREEN: PASSES after fix.
    """
    _make_project(db_session)

    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="test-proj",
        status=JobStatus.queued,
    )
    db_session.add(job)
    db_session.flush()

    assert job.public_id is not None, "public_id must be allocated on insert"
    assert DOC_PUBLIC_ID_PATTERN.match(job.public_id), (
        f"public_id {job.public_id!r} does not match ^DOC-\\d{5}$"
    )
    # Extra guarantee: it must NOT look like a UUID
    assert not _UUID_PATTERN.match(job.public_id), (
        f"public_id {job.public_id!r} looks like a UUID — bug not fixed"
    )


# ---------------------------------------------------------------------------
# GREEN PHASE — Regression tests (pass after fix, prove correctness)
# ---------------------------------------------------------------------------


def test_i00058_public_id_not_overwritten_when_explicitly_set(
    db_session: Session,
) -> None:
    """Pre-set public_id must NOT be overwritten by the before_insert listener."""
    _make_project(db_session)

    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="test-proj",
        status=JobStatus.queued,
        public_id="DOC-99999",  # explicitly set — listener must respect this
    )
    db_session.add(job)
    db_session.flush()

    assert job.public_id == "DOC-99999", (
        f"Listener overwrote explicit public_id; got {job.public_id!r}"
    )


def test_i00058_sequential_increment_two_jobs(
    db_session: Session,
) -> None:
    """Two inserts in the same session receive DOC-00001 and DOC-00002."""
    _make_project(db_session)

    job1 = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="test-proj",
        status=JobStatus.queued,
    )
    job2 = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="test-proj",
        status=JobStatus.queued,
    )
    db_session.add_all([job1, job2])
    db_session.flush()

    assert job1.public_id == "DOC-00001", f"Expected DOC-00001, got {job1.public_id!r}"
    assert job2.public_id == "DOC-00002", f"Expected DOC-00002, got {job2.public_id!r}"


def test_i00058_sequential_increment_three_jobs(
    db_session: Session,
) -> None:
    """Three inserts receive strictly incrementing public_ids."""
    _make_project(db_session)

    job1 = DocGenerationJob(id=str(uuid.uuid4()), project_id="test-proj", status=JobStatus.queued)
    job2 = DocGenerationJob(id=str(uuid.uuid4()), project_id="test-proj", status=JobStatus.queued)
    job3 = DocGenerationJob(id=str(uuid.uuid4()), project_id="test-proj", status=JobStatus.queued)
    db_session.add_all([job1, job2, job3])
    db_session.flush()

    # Exact values prove increment; the split+int is a secondary check
    assert job1.public_id == "DOC-00001"
    assert job2.public_id == "DOC-00002"
    assert job3.public_id == "DOC-00003"


# ---------------------------------------------------------------------------
# Aggregator — _fetch_doc_generation returns public_id as job_id
# ---------------------------------------------------------------------------


def test_i00058_aggregator_list_jobs_returns_public_id_as_job_id(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """list_jobs(doc_generation) must surface public_id as job_id, not UUID."""
    project = _make_project(db_session, "test-proj-agg")

    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id=project.id,
        status=JobStatus.queued,
    )
    db_session.add(job)
    db_session.flush()
    db_session.commit()

    aggregator = JobsAggregator(db_session)
    result = aggregator.list_jobs(project_id=project.id, types=[JobType.doc_generation])

    assert result.total >= 1, f"Expected at least 1 doc_generation job, got {result.total}"
    doc_rows = [r for r in result.rows if r.job_type == JobType.doc_generation]
    assert len(doc_rows) == 1, f"Expected exactly 1 doc_generation row, got {len(doc_rows)}"

    row = doc_rows[0]
    # job_id must be the DOC-NNNNN, not the UUID
    assert row.job_id == "DOC-00001", (
        f"Expected job_id='DOC-00001', got {row.job_id!r}; "
        "aggregator is still surfacing UUID instead of public_id"
    )
    # Verify it is NOT a UUID
    assert not _UUID_PATTERN.match(row.job_id), (
        f"job_id {row.job_id!r} looks like a UUID — bug not fixed"
    )


def test_i00058_aggregator_get_job_returns_public_id(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """get_job(doc_generation, job_id=DOC-NNNNN) must return the correct row."""
    project = _make_project(db_session, "test-proj-agg-get")

    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id=project.id,
        status=JobStatus.running,
    )
    db_session.add(job)
    db_session.flush()
    db_session.commit()

    aggregator = JobsAggregator(db_session)
    # Lookup by public_id (new path)
    row = aggregator.get_job(
        project_id=project.id,
        job_type=JobType.doc_generation,
        job_id="DOC-00001",
    )

    assert row is not None, "get_job by public_id must find the row"
    assert row.job_id == "DOC-00001", f"Expected job_id='DOC-00001', got {row.job_id!r}"
    assert row.job_type == JobType.doc_generation


def test_i00058_aggregator_raw_includes_public_id(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """JobRow.raw must include the public_id field."""
    project = _make_project(db_session, "test-proj-agg-raw")

    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id=project.id,
        status=JobStatus.queued,
    )
    db_session.add(job)
    db_session.flush()
    db_session.commit()

    aggregator = JobsAggregator(db_session)
    result = aggregator.list_jobs(project_id=project.id, types=[JobType.doc_generation])

    doc_rows = [r for r in result.rows if r.job_type == JobType.doc_generation]
    assert len(doc_rows) == 1

    raw = doc_rows[0].raw
    assert "public_id" in raw, f"raw must contain 'public_id' key; got keys: {list(raw.keys())}"
    assert raw["public_id"] == "DOC-00001", (
        f"Expected raw[public_id]='DOC-00001', got {raw['public_id']!r}"
    )


# ---------------------------------------------------------------------------
# DocService.create_doc_job integration test
# ---------------------------------------------------------------------------


def test_i00058_doc_service_create_doc_job_returns_doc_nnnnn_public_id(
    db_session: Session,
) -> None:
    """DocService.create_doc_job() must return a job with public_id = DOC-NNNNN."""
    _make_project(db_session)

    svc = DocService(db_session)
    # Create the doc first (required by create_doc_job)
    svc.create_doc(
        project_id="test-proj",
        doc_id="test-module",
        title="Test Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.draft,
        content="# Test\n\nContent.",
        generated_by="test",
    )

    job = svc.create_doc_job(
        project_id="test-proj",
        doc_id="test-module",
        trigger_reason="test",
    )

    # Must have a public_id
    assert job.public_id is not None, "create_doc_job must allocate public_id on insert"
    # Must match DOC-NNNNN format
    assert DOC_PUBLIC_ID_PATTERN.match(job.public_id), (
        f"public_id {job.public_id!r} does not match ^DOC-\\d{5}$"
    )
    # Must NOT be a UUID
    assert not _UUID_PATTERN.match(job.public_id), (
        f"public_id {job.public_id!r} looks like a UUID — bug not fixed"
    )
    # Verify the UUID id column is still set (it's the PK)
    assert job.id is not None
    assert _UUID_PATTERN.match(job.id), "id column should still be a UUID (PK)"


def test_i00058_doc_service_create_doc_job_multiple_have_incrementing_ids(
    db_session: Session,
) -> None:
    """Multiple create_doc_job calls must produce incrementing public_ids."""
    _make_project(db_session)

    svc = DocService(db_session)
    # Create the doc first (required by create_doc_job)
    svc.create_doc(
        project_id="test-proj",
        doc_id="test-module-2",
        title="Test Module 2",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.draft,
        content="# Test\n\nContent.",
        generated_by="test",
    )

    job1 = svc.create_doc_job(project_id="test-proj", doc_id="test-module-2", trigger_reason="t1")
    job2 = svc.create_doc_job(project_id="test-proj", doc_id="test-module-2", trigger_reason="t2")

    assert job1.public_id is not None
    assert job2.public_id is not None
    assert job1.public_id == "DOC-00001", f"Expected DOC-00001, got {job1.public_id!r}"
    assert job2.public_id == "DOC-00002", f"Expected DOC-00002, got {job2.public_id!r}"
