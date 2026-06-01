"""Unit tests for orch/jobs/aggregator.py — four-source union, filtering, sorting, pagination.

Uses the same testcontainer pattern as integration tests (session scope engine,
function-scope transaction rollback).  All four source tables are seeded directly
via SQLAlchemy — no mocking.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    PROJECT_DOCS_FTS_FUNCTION_SQL,
    PROJECT_DOCS_FTS_TRIGGER_SQL,
    Base,
    Batch,
    BatchStatus,
    CodeIndexJob,
    DocGenerationJob,
    DocStatus,
    DocType,
    JobStatus,
    Project,
    ProjectDoc,
)
from orch.db.models import DocTier as DocTier
from orch.db.models import EditorialCategory as DocEditorialCategory
from orch.jobs.aggregator import JobsAggregator, JobType

if TYPE_CHECKING:
    from sqlalchemy import Engine


# ---------------------------------------------------------------------------
# Testcontainer fixtures (duplicated from conftest to keep this file self-contained)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_engine() -> Engine:
    """Start a PostgreSQL container and create all tables."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:15-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        engine = create_engine(url, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            conn.execute(text(FTS_FUNCTION_SQL))
            conn.execute(text(FTS_TRIGGER_SQL))
            conn.execute(text(PROJECT_DOCS_FTS_FUNCTION_SQL))
            conn.execute(text(PROJECT_DOCS_FTS_TRIGGER_SQL))
            conn.commit()
        yield engine


@pytest.fixture
def db_session(pg_engine: Engine):
    """Each test gets a transactional rollback session."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = session_factory()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def project(db_session) -> Project:
    """Insert a minimal Project row."""
    p = Project(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(p)
    db_session.flush()
    return p


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_code_index(
    db_session, project_id: str, job_id: str, status: str, started_offset_h: int = 0
) -> CodeIndexJob:
    job = CodeIndexJob(
        id=job_id,
        project_id=project_id,
        status=status,
        provider="local",
        llm_model="gemma4:31b",
        embed_model="manutic/nomic-embed-code",
        index_tier="balanced",
        files_discovered=10,
        files_indexed=9,
        chunks_created=120,
        languages_detected=["Python", "TypeScript"],
        errors=[],
        triggered_at=datetime.now(UTC) - timedelta(hours=started_offset_h),
        completed_at=datetime.now(UTC) - timedelta(hours=started_offset_h - 1)
        if status == "completed"
        else None,
    )
    db_session.add(job)
    return job


def _seed_doc_gen(
    db_session,
    project_id: str,
    job_id: str,
    doc_id: str | None,
    job_status: JobStatus,
    started_offset_h: int = 0,
) -> DocGenerationJob:
    job = DocGenerationJob(
        id=job_id,
        project_id=project_id,
        doc_id=doc_id,
        status=job_status,
        requested_at=datetime.now(UTC) - timedelta(hours=started_offset_h + 1),
        started_at=datetime.now(UTC) - timedelta(hours=started_offset_h)
        if job_status != JobStatus.queued
        else None,
        completed_at=datetime.now(UTC) - timedelta(hours=started_offset_h - 1)
        if job_status == JobStatus.completed
        else None,
        skill_used="skill:iw-doc-generator",
        trigger_reason="manual",
        duration_seconds=3600 if job_status == JobStatus.completed else None,
        created_at=datetime.now(UTC) - timedelta(hours=started_offset_h + 1),
    )
    db_session.add(job)
    return job


def _seed_batch(
    db_session, project_id: str, batch_id: str, status: BatchStatus, created_offset_h: int = 0
) -> Batch:
    batch = Batch(
        id=batch_id,
        project_id=project_id,
        status=status,
        max_parallel=4,
        cli_tool="opencode",
        auto_publish=False,
        created_at=datetime.now(UTC) - timedelta(hours=created_offset_h),
        completed_at=datetime.now(UTC) - timedelta(hours=created_offset_h - 1)
        if status in (BatchStatus.completed, BatchStatus.published)
        else None,
    )
    db_session.add(batch)
    return batch


def _seed_research_doc(
    db_session, project_id: str, doc_id: str, status: DocStatus, created_offset_h: int = 0
) -> ProjectDoc:
    doc = ProjectDoc(
        id=doc_id,
        project_id=project_id,
        doc_id=f"research-{doc_id}",
        title=f"Research: {doc_id}",
        slug=f"research-{doc_id}",
        doc_type=DocType.research,
        tier=DocTier.semi_automated,
        editorial_category=DocEditorialCategory.technical,
        status=status,
        audience=[],
        source_paths=[],
        content="# Research Content",
        version=1,
        generated_at=datetime.now(UTC) - timedelta(hours=created_offset_h - 1)
        if status == DocStatus.published
        else None,
        generated_by="skill:iw-research" if status == DocStatus.published else None,
        created_at=datetime.now(UTC) - timedelta(hours=created_offset_h),
        updated_at=datetime.now(UTC) - timedelta(hours=created_offset_h),
    )
    db_session.add(doc)
    return doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_state_returns_empty_list(db_session, project: Project) -> None:
    """Aggregator returns empty result for a project with no jobs."""
    agg = JobsAggregator(db_session)
    result = agg.list_jobs(project_id=project.id)
    assert result.rows == []
    assert result.total == 0
    assert result.page == 1
    assert result.page_size == 25


def test_four_source_union(db_session, project: Project) -> None:
    """One row in each of the four tables yields four JobRows with distinct job_types."""
    _seed_code_index(db_session, project.id, "cij-1", "completed")
    _seed_doc_gen(db_session, project.id, "dgj-1", None, JobStatus.completed)
    _seed_batch(db_session, project.id, "B-001", BatchStatus.completed)
    _seed_research_doc(db_session, project.id, "res-1", DocStatus.published)
    db_session.flush()

    agg = JobsAggregator(db_session)
    result = agg.list_jobs(project_id=project.id)

    assert len(result.rows) == 4
    job_types = {row.job_type for row in result.rows}
    assert job_types == {
        JobType.code_mapping,
        JobType.doc_generation,
        JobType.batch_execution,
        JobType.research,
    }


def test_type_filter_narrows_to_one(db_session, project: Project) -> None:
    """types=[JobType.code_mapping] returns only code_mapping rows."""
    _seed_code_index(db_session, project.id, "cij-1", "completed")
    _seed_doc_gen(db_session, project.id, "dgj-1", None, JobStatus.completed)
    _seed_batch(db_session, project.id, "B-001", BatchStatus.completed)
    _seed_research_doc(db_session, project.id, "res-1", DocStatus.published)
    db_session.flush()

    agg = JobsAggregator(db_session)
    result = agg.list_jobs(project_id=project.id, types=[JobType.code_mapping])

    assert len(result.rows) == 1
    assert result.rows[0].job_type == JobType.code_mapping


def test_status_filter_narrows_results(db_session, project: Project) -> None:
    """statuses=['completed'] returns only completed rows (failed row is excluded)."""
    completed_job = _seed_code_index(db_session, project.id, "cij-1", "completed")
    _seed_code_index(db_session, project.id, "cij-2", "failed")
    db_session.flush()

    agg = JobsAggregator(db_session)
    result = agg.list_jobs(project_id=project.id, statuses=["completed"])

    assert len(result.rows) == 1
    assert result.rows[0].status == "completed"
    assert result.rows[0].job_id == completed_job.public_id


def test_date_range_filter(db_session, project: Project) -> None:
    """date_from / date_to narrow results to the seeded time window."""
    now = datetime.now(UTC)
    _seed_code_index(db_session, project.id, "cij-old", "completed", started_offset_h=48)
    recent_job = _seed_code_index(
        db_session, project.id, "cij-recent", "completed", started_offset_h=1
    )
    db_session.flush()

    agg = JobsAggregator(db_session)
    result = agg.list_jobs(
        project_id=project.id,
        date_from=now - timedelta(hours=24),
        date_to=now,
    )

    assert len(result.rows) == 1
    assert result.rows[0].job_id == recent_job.public_id


def test_pagination_returns_correct_page(db_session, project: Project) -> None:
    """30 seeded rows: page=1,size=10 returns 10 rows, total=30; page=4 returns [."""
    for i in range(30):
        _seed_code_index(db_session, project.id, f"cij-{i:02d}", "completed", started_offset_h=i)
    db_session.flush()

    agg = JobsAggregator(db_session)

    result_p1 = agg.list_jobs(project_id=project.id, page=1, page_size=10)
    assert len(result_p1.rows) == 10
    assert result_p1.total == 30
    assert result_p1.page == 1
    assert result_p1.page_size == 10

    result_p4 = agg.list_jobs(project_id=project.id, page=4, page_size=10)
    assert result_p4.rows == []
    assert result_p4.total == 30


def test_sort_descending(db_session, project: Project) -> None:
    """sort_dir='desc' orders rows by started_at descending (most recent first)."""
    jobs = {}
    for i in [1, 5, 3]:
        jobs[i] = _seed_code_index(
            db_session, project.id, f"cij-{i}", "completed", started_offset_h=i
        )
    db_session.flush()

    agg = JobsAggregator(db_session)
    result = agg.list_jobs(project_id=project.id, sort_by="started_at", sort_dir="desc")

    ids = [row.job_id for row in result.rows]
    # most recent first: offset 1h < offset 3h < offset 5h
    assert ids == [jobs[1].public_id, jobs[3].public_id, jobs[5].public_id]


def test_sort_ascending(db_session, project: Project) -> None:
    """sort_dir='asc' orders rows by started_at ascending (oldest first)."""
    jobs = {}
    for i in [1, 5, 3]:
        jobs[i] = _seed_code_index(
            db_session, project.id, f"cij-{i}", "completed", started_offset_h=i
        )
    db_session.flush()

    agg = JobsAggregator(db_session)
    result = agg.list_jobs(project_id=project.id, sort_by="started_at", sort_dir="asc")

    ids = [row.job_id for row in result.rows]
    # oldest first: offset 5h > offset 3h > offset 1h
    assert ids == [jobs[5].public_id, jobs[3].public_id, jobs[1].public_id]


def test_get_job_returns_correct_row_per_type(db_session, project: Project) -> None:
    """get_job returns the exact seeded row for each of the four types; None for bad id."""
    cm_job = _seed_code_index(db_session, project.id, "cij-1", "completed")
    _seed_doc_gen(db_session, project.id, "dgj-1", None, JobStatus.completed)
    _seed_batch(db_session, project.id, "B-001", BatchStatus.completed)
    res_doc = _seed_research_doc(db_session, project.id, "res-1", DocStatus.published)
    db_session.flush()

    agg = JobsAggregator(db_session)

    assert (
        agg.get_job(project_id=project.id, job_type=JobType.code_mapping, job_id=cm_job.public_id)
        is not None
    )
    assert (
        agg.get_job(project_id=project.id, job_type=JobType.doc_generation, job_id="dgj-1")
        is not None
    )
    assert (
        agg.get_job(project_id=project.id, job_type=JobType.batch_execution, job_id="B-001")
        is not None
    )
    assert (
        agg.get_job(project_id=project.id, job_type=JobType.research, job_id=res_doc.doc_id)
        is not None
    )

    assert agg.get_job(project_id=project.id, job_type=JobType.code_mapping, job_id="bogus") is None
    assert (
        agg.get_job(project_id="bogus", job_type=JobType.code_mapping, job_id=cm_job.public_id)
        is None
    )


def test_batch_executing_normalises_to_running(db_session, project: Project) -> None:
    """BatchStatus.executing normalises to 'running' string."""
    _seed_batch(db_session, project.id, "B-001", BatchStatus.executing)
    db_session.flush()

    agg = JobsAggregator(db_session)
    result = agg.list_jobs(project_id=project.id)

    assert len(result.rows) == 1
    assert result.rows[0].status == "running"
    assert result.rows[0].job_type == JobType.batch_execution


def test_research_published_normalises_to_completed(db_session, project: Project) -> None:
    """DocStatus.published on a research doc normalises to 'completed' string."""
    _seed_research_doc(db_session, project.id, "res-1", DocStatus.published)
    db_session.flush()

    agg = JobsAggregator(db_session)
    result = agg.list_jobs(project_id=project.id)

    assert len(result.rows) == 1
    assert result.rows[0].status == "completed"
    assert result.rows[0].job_type == JobType.research
