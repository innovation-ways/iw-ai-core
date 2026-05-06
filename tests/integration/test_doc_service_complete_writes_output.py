"""Unit tests for DocService.complete_doc_job writing agent_output and report.

These tests use a testcontainer-backed db_session fixture to exercise
the real SQLAlchemy model with a real log file on disk.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from orch.db.models import DocGenerationJob, JobStatus
from orch.doc_service import DocService


class TestCompleteDocJobOutput:
    """Test complete_doc_job writes agent_output and report correctly."""

    def test_complete_writes_full_log_when_small(
        self,
        db_session,
        test_project,
        tmp_path: Path,
    ) -> None:
        """A small log file (<64 KB) is written in full to agent_output."""
        # Set up project repo_root to tmp_path
        test_project.repo_root = str(tmp_path)
        db_session.commit()

        # Create a running job
        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            doc_id=None,  # explicitly None — skips lint gate
            public_id="DOC-TEST01",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            agent_pid=12345,
            skill_used="iw-doc-generator",
        )
        db_session.add(job)
        db_session.flush()

        # Write a small log file
        log_dir = tmp_path / "ai-dev" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"doc_job_{job.id}.log"
        log_file.write_text("small log content\nline two\n")

        # Call complete_doc_job
        svc = DocService(db_session)
        result = svc.complete_doc_job(job.id, worktree_path=str(tmp_path))

        assert result.agent_output == "small log content\nline two\n"
        assert result.report is not None
        assert result.report["outcome"] == "completed"

    def test_complete_truncates_when_large(
        self,
        db_session,
        test_project,
        tmp_path: Path,
    ) -> None:
        """A log file >64 KB is truncated to the last 64 KB with a marker."""
        test_project.repo_root = str(tmp_path)
        db_session.commit()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            doc_id=None,
            public_id="DOC-TEST02",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            agent_pid=12345,
            skill_used="iw-doc-generator",
        )
        db_session.add(job)
        db_session.flush()

        # Write a large log file (>64 KB)
        log_dir = tmp_path / "ai-dev" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"doc_job_{job.id}.log"
        large_content = "x" * 100_000
        log_file.write_text(large_content)

        svc = DocService(db_session)
        result = svc.complete_doc_job(job.id, worktree_path=str(tmp_path))

        # agent_output should start with the truncation marker
        assert result.agent_output.startswith("[truncated:")
        assert len(result.agent_output) <= 65536 + 100  # tail + marker overhead
        # report captures the full size
        assert result.report["log_size_bytes"] == len(large_content)

    def test_complete_writes_report_on_success(
        self,
        db_session,
        test_project,
        tmp_path: Path,
    ) -> None:
        """When error=None (success), outcome=completed and all AC4 fields are present."""
        test_project.repo_root = str(tmp_path)
        db_session.commit()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            public_id="DOC-TEST03",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            agent_pid=12345,
            skill_used="iw-doc-generator",
        )
        db_session.add(job)
        db_session.commit()

        log_dir = tmp_path / "ai-dev" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"doc_job_{job.id}.log"
        log_file.write_text("$ uv run iw doc-update X\nok\n")

        svc = DocService(db_session)
        result = svc.complete_doc_job(job.id, worktree_path=str(tmp_path))

        assert result.report["outcome"] == "completed"
        assert result.report["skill_used"] == "iw-doc-generator"
        assert result.report["cli_tool"] == "opencode"
        assert "doc_update_invocations" in result.report
        assert "tool_calls" in result.report
        assert "log_size_bytes" in result.report
        assert "log_line_count" in result.report
        assert "diagnosis" in result.report

    def test_complete_writes_report_on_timeout_error(
        self,
        db_session,
        test_project,
        tmp_path: Path,
    ) -> None:
        """When error contains 'timeout', outcome=failed_timeout."""
        test_project.repo_root = str(tmp_path)
        db_session.commit()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            public_id="DOC-TEST04",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            agent_pid=12345,
            skill_used="iw-doc-generator",
        )
        db_session.add(job)
        db_session.commit()

        log_dir = tmp_path / "ai-dev" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"doc_job_{job.id}.log"
        log_file.write_text("agent log\n")

        svc = DocService(db_session)
        result = svc.complete_doc_job(
            job.id,
            error="generation timeout after 15 minutes",
            worktree_path=str(tmp_path),
        )

        assert result.report["outcome"] == "failed_timeout"
        assert "timeout" in result.report["diagnosis"].lower()

    def test_complete_writes_report_on_process_exited_error(
        self,
        db_session,
        test_project,
        tmp_path: Path,
    ) -> None:
        """When error contains 'agent process exited', outcome=failed_process_exited."""
        test_project.repo_root = str(tmp_path)
        db_session.commit()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            public_id="DOC-TEST05",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            agent_pid=12345,
            skill_used="iw-doc-generator",
        )
        db_session.add(job)
        db_session.commit()

        log_dir = tmp_path / "ai-dev" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"doc_job_{job.id}.log"
        log_file.write_text("$ uv run iw item-status X\nError: not found\n")

        svc = DocService(db_session)
        result = svc.complete_doc_job(
            job.id,
            error="agent process exited without calling iw doc-job-done",
            worktree_path=str(tmp_path),
        )

        assert result.report["outcome"] == "failed_process_exited"
        assert result.report["doc_update_invocations"] == 0

    def test_complete_idempotent(
        self,
        db_session,
        test_project,
        tmp_path: Path,
    ) -> None:
        """Calling complete_doc_job twice does not re-truncate or re-overwrite."""
        test_project.repo_root = str(tmp_path)
        db_session.commit()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            public_id="DOC-TEST06",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            agent_pid=12345,
            skill_used="iw-doc-generator",
        )
        db_session.add(job)
        db_session.commit()

        log_dir = tmp_path / "ai-dev" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"doc_job_{job.id}.log"
        log_file.write_text("log content\n")

        svc = DocService(db_session)

        # First call
        result1 = svc.complete_doc_job(job.id, worktree_path=str(tmp_path))
        first_output = result1.agent_output
        first_report = result1.report

        # Second call — job is now completed, should be a no-op
        result2 = svc.complete_doc_job(job.id, worktree_path=str(tmp_path))

        assert result2.agent_output == first_output
        assert result2.report == first_report
        # Status should still be completed (idempotent)
        assert result2.status == JobStatus.completed

    def test_complete_handles_missing_log_file(
        self,
        db_session,
        test_project,
        tmp_path: Path,
    ) -> None:
        """When the log file doesn't exist, agent_output is empty and report has size 0."""
        test_project.repo_root = str(tmp_path)
        db_session.commit()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            public_id="DOC-TEST07",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            agent_pid=12345,
            skill_used="iw-doc-generator",
        )
        db_session.add(job)
        db_session.commit()

        # No log file written — path doesn't exist

        svc = DocService(db_session)
        result = svc.complete_doc_job(job.id, worktree_path=str(tmp_path))

        assert result.agent_output == ""
        assert result.report["log_size_bytes"] == 0

    def test_complete_falls_back_to_repo_root_when_no_kwarg(
        self,
        db_session,
        test_project,
        tmp_path: Path,
    ) -> None:
        """When worktree_path=None, complete_doc_job falls back to project.repo_root."""
        test_project.repo_root = str(tmp_path)
        db_session.commit()

        job = DocGenerationJob(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            public_id="DOC-TEST08",
            status=JobStatus.running,
            requested_at=datetime.now(UTC),
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            agent_pid=12345,
            skill_used="iw-doc-generator",
        )
        db_session.add(job)
        db_session.commit()

        log_dir = tmp_path / "ai-dev" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"doc_job_{job.id}.log"
        log_file.write_text("fallback repo_root test\n")

        svc = DocService(db_session)
        # Explicitly pass worktree_path=None — should use project.repo_root
        result = svc.complete_doc_job(job.id, worktree_path=None)

        assert result.agent_output == "fallback repo_root test\n"
