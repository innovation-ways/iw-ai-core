"""I-00058: DocGenerationJob public_id auto-allocation (before_insert listener).

RED PHASE: Test that DocGenerationJob.public_id is auto-allocated as DOC-NNNNN.
This test FAILS before the fix and PASSES after.

See: ai-dev/active/I-00058/I-00058_Issue_Design.md
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from orch.db.models import DocGenerationJob, JobStatus, Project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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


def test_i00058_doc_generation_job_gets_sequential_public_id(
    db_session: Session,
) -> None:
    """public_id must be auto-allocated as DOC-NNNNN on insert.

    RED: FAILS before the before_insert listener is added to DocGenerationJob.
    GREEN: PASSES after the listener is wired up.
    """
    _make_project(db_session)

    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="test-proj",
        status=JobStatus.queued,
    )
    db_session.add(job)
    db_session.flush()  # triggers before_insert listener

    assert job.public_id is not None, "public_id must be allocated on insert"
    assert job.public_id.startswith("DOC-"), (
        f"public_id must start with 'DOC-', got: {job.public_id!r}"
    )
    assert len(job.public_id) == 9, (
        f"public_id must be exactly 9 chars (DOC-NNNNN), got: {job.public_id!r}"
    )


def test_i00058_doc_generation_job_public_id_increments(
    db_session: Session,
) -> None:
    """Sequential inserts must receive strictly incrementing public_ids."""
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
    job3 = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="test-proj",
        status=JobStatus.queued,
    )
    db_session.add_all([job1, job2, job3])
    db_session.flush()

    assert job1.public_id is not None
    assert job2.public_id is not None
    assert job3.public_id is not None

    # Extract numeric suffixes and verify increment
    n1 = int(job1.public_id.split("-")[1])
    n2 = int(job2.public_id.split("-")[1])
    n3 = int(job3.public_id.split("-")[1])

    assert n2 == n1 + 1, f"Expected {n1 + 1}, got {n2} for job2"
    assert n3 == n2 + 1, f"Expected {n2 + 1}, got {n3} for job3"


def test_i00058_doc_generation_job_public_id_not_overwritten(
    db_session: Session,
) -> None:
    """Pre-existing public_id must not be overwritten by the listener."""
    _make_project(db_session)

    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="test-proj",
        status=JobStatus.queued,
        public_id="DOC-99999",  # explicitly set
    )
    db_session.add(job)
    db_session.flush()

    assert job.public_id == "DOC-99999"
