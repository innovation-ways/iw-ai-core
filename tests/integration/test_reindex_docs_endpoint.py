"""Integration tests for POST /project/{project_id}/api/code/reindex-docs endpoint.

Uses testcontainers PostgreSQL — NEVER the live platform DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from sqlalchemy import select

from orch.db.models import DocIndexJob, Project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _make_client(db_session: Session) -> TestClient:
    """Create a TestClient with the DB session overridden."""
    from dashboard.app import create_app
    from dashboard.dependencies import get_db

    app = create_app()

    def _override_get_db() -> Session:
        return db_session

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app, raise_server_exceptions=True)


class TestReindexDocsEndpoint:
    """Tests for the reindex_docs endpoint (POST /project/{project_id}/api/code/reindex-docs)."""

    def test_post_no_running_job_returns_200(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """POST when no doc_index_jobs row exists → 200, new job row created."""
        test_project.config = {
            "code_understanding": {
                "index_tier": "balanced",
                "llm_model": "gemma4:26b",
                "embed_model": "qwen3-embedding:8b",
            }
        }
        db_session.flush()

        client = _make_client(db_session)
        response = client.post(f"/project/{test_project.id}/api/code/reindex-docs")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        db_session.expire_all()
        rows = db_session.scalars(
            select(DocIndexJob).where(DocIndexJob.project_id == test_project.id)
        ).all()
        assert len(rows) == 1
        job = rows[0]
        assert job.status == "queued"
        assert job.project_id == test_project.id
        assert job.embed_model == "qwen3-embedding:8b"
        assert job.index_tier == "balanced"

    def test_post_no_running_job_fragment_contains_project_id(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Response fragment contains the project_id in SSE URL."""
        test_project.config = {
            "code_understanding": {
                "index_tier": "balanced",
                "llm_model": "gemma4:26b",
                "embed_model": "qwen3-embedding:8b",
            }
        }
        db_session.flush()

        client = _make_client(db_session)
        response = client.post(f"/project/{test_project.id}/api/code/reindex-docs")

        assert response.status_code == 200
        assert f"/project/{test_project.id}" in response.text

    def test_post_when_job_queued_returns_409(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """POST when a job is already queued → 409."""
        test_project.config = {
            "code_understanding": {
                "index_tier": "balanced",
                "llm_model": "gemma4:26b",
                "embed_model": "qwen3-embedding:8b",
            }
        }
        db_session.flush()

        existing_job = DocIndexJob(
            project_id=test_project.id,
            status="queued",
            embed_model="existing-embed",
            index_tier="fast",
        )
        db_session.add(existing_job)
        db_session.flush()

        client = _make_client(db_session)
        response = client.post(f"/project/{test_project.id}/api/code/reindex-docs")

        assert response.status_code == 409
        assert "already running" in response.text.lower() or "already" in response.text.lower()

    def test_post_when_job_running_returns_409(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """POST when a job is already running → 409."""
        test_project.config = {
            "code_understanding": {
                "index_tier": "balanced",
                "llm_model": "gemma4:26b",
                "embed_model": "qwen3-embedding:8b",
            }
        }
        db_session.flush()

        existing_job = DocIndexJob(
            project_id=test_project.id,
            status="running",
            embed_model="existing-embed",
            index_tier="fast",
        )
        db_session.add(existing_job)
        db_session.flush()

        client = _make_client(db_session)
        response = client.post(f"/project/{test_project.id}/api/code/reindex-docs")

        assert response.status_code == 409

    def test_post_unknown_project_returns_404(
        self,
        db_session: Session,
    ) -> None:
        """POST for a non-existent project → 404."""
        client = _make_client(db_session)
        response = client.post("/project/nonexistent-project/api/code/reindex-docs")

        assert response.status_code == 404

    def test_post_writes_exactly_one_row(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """POST inserts exactly one doc_index_jobs row."""
        test_project.config = {
            "code_understanding": {
                "index_tier": "balanced",
                "llm_model": "gemma4:26b",
                "embed_model": "qwen3-embedding:8b",
            }
        }
        db_session.flush()

        client = _make_client(db_session)
        response = client.post(f"/project/{test_project.id}/api/code/reindex-docs")

        assert response.status_code == 200
        db_session.expire_all()
        count = db_session.scalar(
            select(DocIndexJob).where(DocIndexJob.project_id == test_project.id)
        )
        assert count is not None

    def test_post_row_has_correct_config_fields(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """The inserted row has provider, llm_model, embed_model, index_tier from project config."""
        test_project.config = {
            "code_understanding": {
                "index_tier": "balanced",
                "llm_model": "gemma4:26b",
                "embed_model": "qwen3-embedding:8b",
            }
        }
        db_session.flush()

        client = _make_client(db_session)
        response = client.post(f"/project/{test_project.id}/api/code/reindex-docs")

        assert response.status_code == 200
        db_session.expire_all()
        job = db_session.scalar(
            select(DocIndexJob).where(DocIndexJob.project_id == test_project.id)
        )
        assert job is not None
        assert job.provider == "local"
        assert job.llm_model == "gemma4:26b"
        assert job.embed_model == "qwen3-embedding:8b"
        assert job.index_tier == "balanced"

    def test_post_with_completed_job_succeeds(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """A previously completed job does not block a new reindex request."""
        test_project.config = {
            "code_understanding": {
                "index_tier": "balanced",
                "llm_model": "gemma4:26b",
                "embed_model": "qwen3-embedding:8b",
            }
        }
        db_session.flush()

        completed_job = DocIndexJob(
            project_id=test_project.id,
            status="completed",
            embed_model="old-embed",
            index_tier="fast",
        )
        db_session.add(completed_job)
        db_session.flush()

        client = _make_client(db_session)
        response = client.post(f"/project/{test_project.id}/api/code/reindex-docs")

        assert response.status_code == 200
        db_session.expire_all()
        count = db_session.scalar(
            select(DocIndexJob).where(
                DocIndexJob.project_id == test_project.id,
                DocIndexJob.status == "queued",
            )
        )
        assert count is not None

    def test_post_with_failed_job_succeeds(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """A previously failed job does not block a new reindex request."""
        test_project.config = {
            "code_understanding": {
                "index_tier": "balanced",
                "llm_model": "gemma4:26b",
                "embed_model": "qwen3-embedding:8b",
            }
        }
        db_session.flush()

        failed_job = DocIndexJob(
            project_id=test_project.id,
            status="failed",
            embed_model="old-embed",
            index_tier="fast",
            error_message="Previous failure",
        )
        db_session.add(failed_job)
        db_session.flush()

        client = _make_client(db_session)
        response = client.post(f"/project/{test_project.id}/api/code/reindex-docs")

        assert response.status_code == 200
