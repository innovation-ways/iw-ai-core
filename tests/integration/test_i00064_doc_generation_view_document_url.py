"""Integration tests for I-00064: doc_generation job raw["doc_id"] must be the inner
ProjectDoc.doc_id (not the composite FK), so the job detail page's "View document"
link resolves with HTTP 200 instead of 404.

These tests FAIL on main (pre-fix) and PASS on the current branch (post-fix).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    DocGenerationJob,
    DocTier,
    DocType,
    EditorialCategory,
    JobStatus,
    Project,
    ProjectDoc,
)
from orch.jobs.aggregator import JobsAggregator, JobType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _make_project(session: Session, project_id: str = "iw-ai-core") -> Project:
    """Insert a minimal Project row."""
    project = Project(
        id=project_id,
        display_name=f"Test Project {project_id}",
        repo_root="/repos/test",
        config={},
    )
    session.add(project)
    session.flush()
    return project


def _make_doc(session: Session, project_id: str, doc_id: str) -> ProjectDoc:
    """Insert a ProjectDoc row whose inner identifier is doc_id."""
    doc = ProjectDoc(
        id=f"{project_id}:{doc_id}",  # composite PK
        project_id=project_id,
        doc_id=doc_id,  # inner identifier
        title=f"Doc Title: {doc_id}",
        slug=doc_id,
        doc_type=DocType.module,
        tier=DocTier.fully_automated,
        editorial_category=EditorialCategory.technical,
        status="published",
        audience=[],
        source_paths=[],
    )
    session.add(doc)
    session.flush()
    return doc


def _make_doc_generation_job(
    session: Session,
    project_id: str,
    doc_id: str | None,
    public_id: str = "DOC-00001",
) -> DocGenerationJob:
    """Insert a DocGenerationJob whose FK is the composite project_docs.id."""
    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id=project_id,
        doc_id=doc_id,  # composite FK value (or None for orphan)
        public_id=public_id,
        status=JobStatus.completed,
        skill_used="iw-doc-generator",
        trigger_reason="manual",
        requested_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(job)
    session.flush()
    return job


# ---------------------------------------------------------------------------
# TestClient fixture (reuses testcontainers db_session)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Build a FastAPI TestClient backed by the testcontainer db_session."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Generator[Session, None, None]:
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_i00064_reproduces_bug(db_session: Session) -> None:
    """FAILS before fix, PASSES after.

    Pre-fix:  raw["doc_id"] == "iw-ai-core:code-index" (composite FK).
    Post-fix: raw["doc_id"] == "code-index" (inner identifier).

    The pre-fix assertion `row.raw["doc_id"] == "iw-ai-core:code-index"`
    would make this test pass on main but fail after the fix is applied,
    proving the test is falsifiable in the wrong direction. We assert the
    post-fix correct value so the test fails on main and passes after S01.
    """
    project = _make_project(db_session, project_id="iw-ai-core")
    doc = _make_doc(db_session, project_id="iw-ai-core", doc_id="code-index")
    _make_doc_generation_job(
        db_session,
        project_id=project.id,
        doc_id=doc.id,  # composite FK value "iw-ai-core:code-index"
        public_id="DOC-00001",
    )
    db_session.flush()

    aggregator = JobsAggregator(db_session)
    row = aggregator.get_job(
        project_id="iw-ai-core",
        job_type=JobType.doc_generation,
        job_id="DOC-00001",
    )

    assert row is not None
    # Semantic assertions — verify the specific expected value, not just shape
    assert row.raw["doc_id"] == "code-index", (
        f"expected inner doc_id 'code-index', got {row.raw['doc_id']!r}; "
        "pre-fix code returns the composite FK here"
    )
    assert ":" not in (row.raw["doc_id"] or ""), (
        f"raw['doc_id'] must not contain ':'; got {row.raw['doc_id']!r}"
    )
    assert row.raw["doc_id"] != "iw-ai-core:code-index", (  # type: ignore[comparison-overlap]
        "raw['doc_id'] must NOT be the composite FK"
    )


def test_i00064_view_document_link_resolves(client: TestClient, db_session: Session) -> None:
    """End-to-end: follow the URL the job detail template builds and assert HTTP 200.

    The template at job_detail.html builds:
        /project/{project_id}/docs/{raw.get('doc_id')}

    With the pre-fix composite value this URL 404s. With the post-fix inner
    value the docs route resolves correctly and returns the doc detail page.
    """
    project = _make_project(db_session, project_id="iw-ai-core")
    doc = _make_doc(db_session, project_id="iw-ai-core", doc_id="code-index")
    _make_doc_generation_job(
        db_session,
        project_id=project.id,
        doc_id=doc.id,
        public_id="DOC-00001",
    )
    db_session.commit()  # TestClient reads committed state

    aggregator = JobsAggregator(db_session)
    row = aggregator.get_job(
        project_id="iw-ai-core",
        job_type=JobType.doc_generation,
        job_id="DOC-00001",
    )

    assert row is not None
    url = f"/project/iw-ai-core/docs/{row.raw['doc_id']}"
    response = client.get(url, follow_redirects=False)

    assert response.status_code == 200, (
        f"Expected 200 from {url!r}, got {response.status_code}: {response.text[:200]}"
    )
    # Verify the doc title appears in the rendered HTML
    assert "code-index" in response.text or "Code Index" in response.text, (
        f"Doc title 'Code Index' not found in response for {url!r}"
    )


def test_i00064_orphan_doc_id_is_none(db_session: Session) -> None:
    """Orphan job (doc deleted): raw["doc_id"] must be None so the template guard
    {% if raw.get('doc_id') %} correctly hides the "View document" link.

    Two orphan cases are covered:
    1. FK is explicitly NULL (job created with doc_id=None).
    2. FK is set to a composite id whose ProjectDoc row has been deleted
       (ondelete=SET NULL makes job.doc_id NULL after the doc is removed).
    """
    project = _make_project(db_session, project_id="iw-ai-core")

    # Case 1: job with doc_id=None (no FK target at insert time)
    _make_doc_generation_job(
        db_session,
        project_id=project.id,
        doc_id=None,
        public_id="DOC-00099",
    )
    db_session.flush()

    # Case 2: job pointing at a doc that will be deleted
    doc_to_delete = _make_doc(db_session, project_id="iw-ai-core", doc_id="to-be-deleted")
    _make_doc_generation_job(
        db_session,
        project_id=project.id,
        doc_id=doc_to_delete.id,  # composite FK
        public_id="DOC-00098",
    )
    db_session.flush()

    # Delete the ProjectDoc — ON DELETE SET NULL clears job.doc_id
    db_session.delete(doc_to_delete)
    db_session.flush()

    db_session.commit()

    aggregator = JobsAggregator(db_session)

    # Case 1: null FK at insert
    row_null = aggregator.get_job(
        project_id="iw-ai-core",
        job_type=JobType.doc_generation,
        job_id="DOC-00099",
    )
    assert row_null is not None
    assert row_null.raw["doc_id"] is None, (
        f"expected doc_id=None for orphan job, got {row_null.raw['doc_id']!r}"
    )

    # Case 2: FK was set but doc was deleted
    row_orphan = aggregator.get_job(
        project_id="iw-ai-core",
        job_type=JobType.doc_generation,
        job_id="DOC-00098",
    )
    assert row_orphan is not None
    assert row_orphan.raw["doc_id"] is None, (
        f"expected doc_id=None after doc deletion, got {row_orphan.raw['doc_id']!r}"
    )
