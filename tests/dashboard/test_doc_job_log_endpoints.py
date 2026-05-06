"""Smoke tests for the doc-job log endpoints added in CR-00035 S07.

Tests that the three new routes (log/tail, log/stream, log/raw) respond
correctly without crashing (404, 200, content-type assertions only).
Full integration coverage is S11's responsibility.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import DocGenerationJob, JobStatus, Project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a TestClient that overrides get_db to use the test db_session."""
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


@pytest.fixture
def doc_job_with_project(db_session: Session, test_project: Project) -> DocGenerationJob:
    """Create a DocGenerationJob row for testing (no doc_id to avoid FK constraint)."""
    job = DocGenerationJob(
        id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        project_id=test_project.id,
        public_id="DOC-99999",
        status=JobStatus.running,
        requested_at=None,
    )
    db_session.add(job)
    db_session.commit()
    return job


class TestDocJobLogTail:
    """GET /project/{project_id}/jobs/doc_generation/{job_id}/log/tail"""

    def test_returns_404_for_unknown_job(self, client: TestClient, test_project) -> None:
        resp = client.get(f"/project/{test_project.id}/jobs/doc_generation/nonexistent/log/tail")
        assert resp.status_code == 404

    def test_returns_404_for_missing_log_file(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        doc_job_with_project: DocGenerationJob,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_project.repo_root = tmpdir
            db_session.commit()
            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job_with_project.id}/log/tail"
            )
            assert resp.status_code == 404
            assert resp.json()["detail"] == "log file not found"

    def test_returns_200_with_lines_for_existing_log(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        doc_job_with_project: DocGenerationJob,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job_with_project.id}.log"
            log_file.write_text("line one\nline two\nline three\n")

            test_project.repo_root = tmpdir
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job_with_project.id}/log/tail"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "lines" in data
            assert "file_size_bytes" in data
            assert "line_count" in data
            assert isinstance(data["lines"], list)
            assert data["line_count"] == 3

    def test_respects_n_parameter(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        doc_job_with_project: DocGenerationJob,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job_with_project.id}.log"
            log_file.write_text("".join(f"line {i}\n" for i in range(20)))

            test_project.repo_root = tmpdir
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job_with_project.id}/log/tail?n=5"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["lines"]) == 5

    def test_n_parameter_hard_capped_at_1000(
        self, client: TestClient, test_project: Project
    ) -> None:
        resp = client.get(f"/project/{test_project.id}/jobs/doc_generation/some-id/log/tail?n=9999")
        assert resp.status_code == 422


class TestDocJobLogStream:
    """GET /project/{project_id}/jobs/doc_generation/{job_id}/log/stream"""

    def test_returns_404_for_unknown_job(self, client: TestClient, test_project) -> None:
        resp = client.get(f"/project/{test_project.id}/jobs/doc_generation/nonexistent/log/stream")
        assert resp.status_code == 404

    def test_returns_sse_content_type(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        doc_job_with_project: DocGenerationJob,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job_with_project.id}.log"
            log_file.write_text("initial line\n")

            test_project.repo_root = tmpdir
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job_with_project.id}/log/stream"
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]


class TestDocJobLogRaw:
    """GET /project/{project_id}/jobs/doc_generation/{job_id}/log/raw"""

    def test_returns_404_for_unknown_job(self, client: TestClient, test_project) -> None:
        resp = client.get(f"/project/{test_project.id}/jobs/doc_generation/nonexistent/log/raw")
        assert resp.status_code == 404

    def test_returns_404_for_missing_log_file(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        doc_job_with_project: DocGenerationJob,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            test_project.repo_root = tmpdir
            db_session.commit()
            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job_with_project.id}/log/raw"
            )
            assert resp.status_code == 404

    def test_returns_text_plain_with_attachment_header(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        doc_job_with_project: DocGenerationJob,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job_with_project.id}.log"
            log_file.write_text("raw log content\n")

            test_project.repo_root = tmpdir
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job_with_project.id}/log/raw"
            )
            assert resp.status_code == 200
            assert "text/plain" in resp.headers["content-type"]
            assert "attachment" in resp.headers.get("content-disposition", "")
            assert f"doc_job_{doc_job_with_project.id}.log" in resp.headers["content-disposition"]
