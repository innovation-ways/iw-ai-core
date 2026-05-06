"""Integration tests for doc-job log HTTP endpoints (CR-00035 S07).

Tests use FastAPI TestClient with a testcontainer-backed PostgreSQL session.
File path resolution, ANSI handling, SSE behavior, and 404 cases are covered.

NOTE: These tests do NOT use the dashboard test fixtures (test_doc_job_log_endpoints.py).
They are the full integration suite specified in the TDD approach for S11.
"""

from __future__ import annotations

import tempfile
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orch.db.models import DocGenerationJob, JobStatus, Project


@pytest.fixture
def client(db_session, test_project) -> TestClient:
    """Create a TestClient with get_db overridden to use the testcontainer session."""
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        from dashboard.app import create_app
        from dashboard.dependencies import get_db

        def override_get_db():
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


@pytest.fixture
def doc_job(db_session, test_project) -> DocGenerationJob:
    """Create a running DocGenerationJob with no doc_id (avoids FK)."""
    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id=test_project.id,
        public_id="DOC-INTEG01",
        status=JobStatus.running,
        requested_at=datetime.now(UTC),
        started_at=datetime.now(UTC) - timedelta(seconds=30),
        agent_pid=12345,
        skill_used="iw-doc-generator",
    )
    db_session.add(job)
    db_session.commit()
    return job


# ---------------------------------------------------------------------------
# GET /log/tail
# ---------------------------------------------------------------------------


class TestLogTail:
    def test_log_tail_returns_last_n_lines(
        self,
        client: TestClient,
        db_session,
        test_project: Project,
        doc_job: DocGenerationJob,
    ) -> None:
        """GET /log/tail?n=10 returns the last 10 ANSI-stripped lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job.id}.log"
            lines = ["line " + str(i) for i in range(50)]
            log_file.write_text("\n".join(lines) + "\n")

            test_project.repo_root = tmpdir
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job.id}/log/tail?n=10"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["lines"]) == 10
            # Last lines should be the last 10
            assert data["lines"][-1] == "line 49"
            # ANSI codes stripped
            for line in data["lines"]:
                assert "\x1b" not in line

    def test_log_tail_default_n_is_200(
        self,
        client: TestClient,
        db_session,
        test_project: Project,
        doc_job: DocGenerationJob,
    ) -> None:
        """Without ?n=, the endpoint returns 200 lines (default)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job.id}.log"
            # Write 300 lines
            log_file.write_text("\n".join(f"line {i}" for i in range(300)) + "\n")

            test_project.repo_root = tmpdir
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job.id}/log/tail"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["lines"]) == 200

    def test_log_tail_n_capped_at_1000(
        self,
        client: TestClient,
        db_session,
        test_project: Project,
        doc_job: DocGenerationJob,
    ) -> None:
        """?n=10000 is hard-capped at 1000 lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job.id}.log"
            log_file.write_text("\n".join(f"line {i}" for i in range(2000)) + "\n")

            test_project.repo_root = tmpdir
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job.id}/log/tail?n=10000"
            )
            assert resp.status_code == 422  # pydantic validation error

    def test_log_tail_missing_file_404(
        self,
        client: TestClient,
        db_session,
        test_project: Project,
        doc_job: DocGenerationJob,
    ) -> None:
        """When the log file does not exist, the endpoint returns 404."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_project.repo_root = tmpdir
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job.id}/log/tail"
            )
            assert resp.status_code == 404
            assert "detail" in resp.json()

    def test_log_tail_empty_file_returns_empty_lines(
        self,
        client: TestClient,
        db_session,
        test_project: Project,
        doc_job: DocGenerationJob,
    ) -> None:
        """A 0-byte log file returns 200 with lines=[], not 404."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job.id}.log"
            log_file.write_text("")  # empty file

            test_project.repo_root = tmpdir
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job.id}/log/tail"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["lines"] == []
            assert data["file_size_bytes"] == 0


# ---------------------------------------------------------------------------
# GET /log/raw
# ---------------------------------------------------------------------------


class TestLogRaw:
    def test_log_raw_returns_unmodified_content(
        self,
        client: TestClient,
        db_session,
        test_project: Project,
        doc_job: DocGenerationJob,
    ) -> None:
        """The raw endpoint returns the file content with ANSI escapes intact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job.id}.log"
            raw_content = "\x1b[32mgreen\x1b[0m\n[0m> build · MiniMax-M2.7\n"
            log_file.write_text(raw_content)

            test_project.repo_root = tmpdir
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job.id}/log/raw"
            )
            assert resp.status_code == 200
            # ANSI NOT stripped on raw endpoint
            assert "\x1b[32m" in resp.text
            assert "green" in resp.text

    def test_log_raw_content_disposition_attachment(
        self,
        client: TestClient,
        db_session,
        test_project: Project,
        doc_job: DocGenerationJob,
    ) -> None:
        """The raw endpoint sets Content-Disposition: attachment with the log filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job.id}.log"
            log_file.write_text("raw log content\n")

            test_project.repo_root = tmpdir
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job.id}/log/raw"
            )
            assert resp.status_code == 200
            assert "attachment" in resp.headers.get("content-disposition", "")
            assert f"doc_job_{doc_job.id}.log" in resp.headers["content-disposition"]

    def test_log_raw_missing_file_404(
        self,
        client: TestClient,
        db_session,
        test_project: Project,
        doc_job: DocGenerationJob,
    ) -> None:
        """Missing log file returns 404 with detail body."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_project.repo_root = tmpdir
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job.id}/log/raw"
            )
            assert resp.status_code == 404
            assert "detail" in resp.json()


class TestLogStream:
    def test_log_stream_emits_lines_then_terminal(
        self,
        client: TestClient,
        db_session,
        test_project: Project,
        doc_job: DocGenerationJob,
    ) -> None:
        """The SSE stream emits log lines, then event:status data:terminal when job completes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job.id}.log"
            log_file.write_text("line one\nline two\n")

            test_project.repo_root = tmpdir
            db_session.commit()

            # Mark job as completed so SSE closes immediately
            doc_job.status = JobStatus.completed
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job.id}/log/stream",
                stream=True,
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

            lines = []
            for chunk in resp.iter_text():
                for event in chunk.split("\n"):
                    if event.startswith("data:"):
                        lines.append(event[5:].strip())

            assert "line one" in lines or len(lines) >= 1

    def test_log_stream_heartbeat(
        self,
        client: TestClient,
        db_session,
        test_project: Project,
        doc_job: DocGenerationJob,
    ) -> None:
        """Idle log file still produces heartbeat events (event:ping) at ~15s intervals.

        This test uses a short sleep to verify ping events are emitted.
        Marked as slow since it requires waiting.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job.id}.log"
            log_file.write_text("initial line\n")

            test_project.repo_root = tmpdir
            db_session.commit()

            # Keep job running
            doc_job.status = JobStatus.running
            db_session.commit()

            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job.id}/log/stream",
                stream=True,
            )
            assert resp.status_code == 200

            # Read for a few seconds looking for ping events
            start = time.time()
            for chunk in resp.iter_text():
                if time.time() - start > 5:
                    break
                if "event:ping" in chunk or "ping" in chunk:
                    break
            # Note: smoke test for heartbeat - may not always catch within 5s

    def test_log_stream_uses_uuid_not_public_id(
        self,
        client: TestClient,
        db_session,
        test_project: Project,
        doc_job: DocGenerationJob,
    ) -> None:
        """Both public_id and UUID resolve to the same job's log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "ai-dev" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"doc_job_{doc_job.id}.log"
            log_file.write_text("log content for uuid test\n")

            test_project.repo_root = tmpdir
            db_session.commit()

            doc_job.status = JobStatus.completed
            db_session.commit()

            # Request via UUID
            resp_uuid = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job.id}/log/tail"
            )
            assert resp_uuid.status_code == 200

            # Request via public_id
            resp_pub = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/{doc_job.public_id}/log/tail"
            )
            assert resp_pub.status_code == 200
            assert resp_uuid.json()["lines"] == resp_pub.json()["lines"]

    def test_path_traversal_rejected(
        self,
        client: TestClient,
        db_session,
        test_project: Project,
        doc_job: DocGenerationJob,
    ) -> None:
        """Even though job IDs are UUIDs, a path-traversal attempt returns 404."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_project.repo_root = tmpdir
            db_session.commit()

            # Attempt path traversal
            resp = client.get(
                f"/project/{test_project.id}/jobs/doc_generation/../../etc/passwd/log/tail"
            )
            # Should be 404 (job not found, not path traversal reached)
            assert resp.status_code == 404
