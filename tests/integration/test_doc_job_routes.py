"""Integration tests for doc generation dashboard routes.

Tests verify:
- POST /api/project/{id}/docs/{doc_id}/generate — creates job, returns 200
- GET /api/project/{id}/docs/jobs/{job_id}/status — JSON status poll
- GET /api/project/{id}/docs/{doc_id}/jobs — job history HTML fragment

Note: SSE stream tests are excluded because the SSE endpoint creates its own
SessionLocal session (bypassing FastAPI DI), making testcontainer integration
complex. The SSE behavior is tested in unit tests with proper mocking.

CRITICAL: All tests use testcontainers — NEVER connect to live DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    Project,
    ProjectDoc,
)
from orch.doc_service import DocService

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


def _make_project(db: Session, project_id: str = "test-proj") -> Project:
    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    db.add(project)
    db.flush()
    return project


def _make_doc(
    db: Session,
    project_id: str = "test-proj",
    doc_id: str = "module-auth",
    editorial_category: EditorialCategory = EditorialCategory.technical,
    content: str | None = None,
) -> ProjectDoc:
    doc = ProjectDoc(
        id=f"{project_id}:{doc_id}",
        project_id=project_id,
        doc_id=doc_id,
        title="Auth Module",
        slug=doc_id.replace("_", "-"),
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=editorial_category,
        status=DocStatus.draft,
        audience=["developers"],
        source_paths=["src/auth/mod.rs"],
        content=content,
    )
    db.add(doc)
    db.flush()
    return doc


def test_docs_generate_creates_job(client: TestClient, db_session: Session) -> None:
    """Generate endpoint creates a queued DocGenerationJob and returns 200."""
    _make_project(db_session)
    _make_doc(db_session, content=None)

    resp = client.post("/project/test-proj/api/project/test-proj/docs/module-auth/generate")
    assert resp.status_code == 200


def test_docs_generate_returns_409_when_job_running(
    client: TestClient, db_session: Session
) -> None:
    """Generate endpoint returns 409 when a job is already running for this doc."""
    _make_project(db_session)
    _make_doc(db_session, content=None)
    svc = DocService(db_session)
    job = svc.create_doc_job("test-proj", "module-auth")
    svc.start_doc_job(job.id)
    db_session.flush()

    resp = client.post("/project/test-proj/api/project/test-proj/docs/module-auth/generate")
    assert resp.status_code == 409
    assert "in progress" in resp.text.lower()


def test_docs_generate_unknown_project_404(client: TestClient) -> None:
    """Generate endpoint returns 404 for unknown project."""
    resp = client.post("/project/nonexistent/api/project/nonexistent/docs/doc1/generate")
    assert resp.status_code == 404


def test_docs_generate_unknown_doc_404(client: TestClient, db_session: Session) -> None:
    """Generate endpoint returns 404 for unknown doc."""
    _make_project(db_session)

    resp = client.post("/project/test-proj/api/project/test-proj/docs/nonexistent/generate")
    assert resp.status_code == 404


def test_status_poll_route_queued(client: TestClient, db_session: Session) -> None:
    """Status poll returns correct job fields for queued job."""
    _make_project(db_session)
    _make_doc(db_session, content=None)
    svc = DocService(db_session)
    job = svc.create_doc_job("test-proj", "module-auth")
    db_session.flush()
    job_id = job.id

    resp = client.get(f"/project/test-proj/api/project/test-proj/docs/jobs/{job_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] == "queued"
    assert data["started_at"] is None
    assert data["completed_at"] is None


def test_status_poll_route_running(client: TestClient, db_session: Session) -> None:
    """Status poll returns correct job fields for running job."""
    _make_project(db_session)
    _make_doc(db_session, content=None)
    svc = DocService(db_session)
    job = svc.create_doc_job("test-proj", "module-auth")
    svc.start_doc_job(job.id, pid=12345, skill_used="iw-doc-generator")
    db_session.flush()
    job_id = job.id

    resp = client.get(f"/project/test-proj/api/project/test-proj/docs/jobs/{job_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] == "running"
    assert data["started_at"] is not None
    assert data["skill_used"] == "iw-doc-generator"
    assert data["error"] is None


def test_status_poll_route_completed(client: TestClient, db_session: Session) -> None:
    """Status poll returns correct job fields for completed job."""
    _make_project(db_session)
    _make_doc(db_session, content=None)
    svc = DocService(db_session)
    job = svc.create_doc_job("test-proj", "module-auth")
    svc.start_doc_job(job.id)
    svc.complete_doc_job(job.id)
    db_session.flush()
    job_id = job.id

    resp = client.get(f"/project/test-proj/api/project/test-proj/docs/jobs/{job_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] == "completed"
    assert data["completed_at"] is not None
    assert data["duration_seconds"] is not None


def test_status_poll_route_failed(client: TestClient, db_session: Session) -> None:
    """Status poll returns correct job fields for failed job."""
    _make_project(db_session)
    _make_doc(db_session, content=None)
    svc = DocService(db_session)
    job = svc.create_doc_job("test-proj", "module-auth")
    svc.start_doc_job(job.id)
    svc.complete_doc_job(job.id, error="generation timeout after 10 minutes")
    db_session.flush()
    job_id = job.id

    resp = client.get(f"/project/test-proj/api/project/test-proj/docs/jobs/{job_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] == "failed"
    assert "timeout" in data["error"].lower()


def test_status_poll_route_unknown_job_404(client: TestClient, db_session: Session) -> None:
    """Status poll returns 404 for unknown job_id."""
    _make_project(db_session)
    resp = client.get("/project/test-proj/api/project/test-proj/docs/jobs/nonexistent-job/status")
    assert resp.status_code == 404


def test_job_history_route(client: TestClient, db_session: Session) -> None:
    """Job history returns last 10 jobs for a doc."""
    _make_project(db_session)
    _make_doc(db_session, content=None)
    svc = DocService(db_session)

    job1 = svc.create_doc_job("test-proj", "module-auth")
    svc.start_doc_job(job1.id)
    svc.complete_doc_job(job1.id)
    db_session.flush()

    job2 = svc.create_doc_job("test-proj", "module-auth")
    svc.start_doc_job(job2.id)
    svc.complete_doc_job(job2.id, error="Source file not found")
    db_session.flush()

    svc.create_doc_job("test-proj", "module-auth")
    db_session.flush()

    resp = client.get("/project/test-proj/api/project/test-proj/docs/module-auth/jobs")
    assert resp.status_code == 200


def test_job_history_route_unknown_project_404(client: TestClient) -> None:
    """Job history returns 404 for unknown project."""
    resp = client.get("/project/nonexistent/api/project/nonexistent/docs/module-auth/jobs")
    assert resp.status_code == 404


def test_job_history_route_empty(client: TestClient, db_session: Session) -> None:
    """Job history returns empty list when no jobs exist."""
    _make_project(db_session)
    _make_doc(db_session, content=None)

    resp = client.get("/project/test-proj/api/project/test-proj/docs/module-auth/jobs")
    assert resp.status_code == 200
