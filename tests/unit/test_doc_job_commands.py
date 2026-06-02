"""Unit tests for doc-job-start and doc-job-done CLI commands.

Argument parsing and output validation — no DB required.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

from click.testing import CliRunner

from orch.cli.doc_commands import doc_job_done, doc_job_start
from orch.db.models import JobStatus


class _FakeSession:
    """Minimal session stub for argument validation tests."""

    def __init__(self, job: MagicMock | None = None) -> None:
        self._job = job

    def get(self, model: type, key: str) -> Any:  # noqa: ARG002
        """Return get."""
        return self._job

    def flush(self) -> None:
        """Return flush."""

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def _make_fake_get_session(job: MagicMock | None = None) -> Any:
    """Return a minimal session-like context manager for argument parsing tests."""

    def _get_session() -> _FakeSession:
        return _FakeSession(job)

    return _get_session


def _make_mock_job(job_id: str = "job-123", status: JobStatus = JobStatus.queued) -> MagicMock:
    """Return make mock job."""
    job = MagicMock()
    job.id = job_id
    job.project_id = "test-proj"
    job.doc_id = "test-proj:doc001"
    job.status = status
    job.started_at = None
    job.completed_at = None
    job.agent_pid = None
    job.skill_used = None
    job.error = None
    job.duration_seconds = None
    return job


class TestDocJobStart:
    """Tests for DocJobStart scenarios."""

    def test_doc_job_start_transitions_to_running(self) -> None:
        """Verifies that doc job start transitions to running."""
        runner = CliRunner()
        mock_job = _make_mock_job(status=JobStatus.queued)

        result = runner.invoke(
            doc_job_start,
            ["job-123", "--pid", "9999", "--skill", "iw-doc-generator"],
            obj={"project_id": "test-proj", "get_session": _make_fake_get_session(mock_job)},
        )

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["job_id"] == "job-123"
        assert output["status"] == "running"
        assert mock_job.status == JobStatus.running
        assert mock_job.agent_pid == 9999
        assert mock_job.skill_used == "iw-doc-generator"

    def test_doc_job_start_already_running_idempotent(self) -> None:
        """Verifies that doc job start already running idempotent."""
        runner = CliRunner()
        mock_job = _make_mock_job(status=JobStatus.running)

        result = runner.invoke(
            doc_job_start,
            ["job-123"],
            obj={"project_id": "test-proj", "get_session": _make_fake_get_session(mock_job)},
        )

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["job_id"] == "job-123"
        assert output["status"] == "running"

    def test_doc_job_start_job_not_found(self) -> None:
        """Verifies that doc job start job not found."""
        runner = CliRunner()

        result = runner.invoke(
            doc_job_start,
            ["nonexistent-job"],
            obj={"project_id": "test-proj", "get_session": _make_fake_get_session(None)},
        )

        assert result.exit_code == 1
        assert "not found" in result.stderr

    def test_doc_job_start_invalid_status(self) -> None:
        """Verifies that doc job start invalid status."""
        runner = CliRunner()
        mock_job = _make_mock_job(status=JobStatus.completed)

        result = runner.invoke(
            doc_job_start,
            ["job-123"],
            obj={"project_id": "test-proj", "get_session": _make_fake_get_session(mock_job)},
        )

        assert result.exit_code == 2
        assert "completed" in result.stderr


class TestDocJobDone:
    """Tests for DocJobDone scenarios."""

    def test_doc_job_done_marks_completed(self) -> None:
        """Verifies that doc job done marks completed."""
        runner = CliRunner()
        mock_job = _make_mock_job(status=JobStatus.running)
        mock_job.started_at = None

        result = runner.invoke(
            doc_job_done,
            ["job-123"],
            obj={"project_id": "test-proj", "get_session": _make_fake_get_session(mock_job)},
        )

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["job_id"] == "job-123"
        assert output["status"] == "completed"
        assert mock_job.status == JobStatus.completed

    def test_doc_job_done_with_error_marks_failed(self) -> None:
        """Verifies that doc job done with error marks failed."""
        runner = CliRunner()
        mock_job = _make_mock_job(status=JobStatus.running)
        mock_job.started_at = None

        result = runner.invoke(
            doc_job_done,
            ["job-123", "--error", "something went wrong"],
            obj={"project_id": "test-proj", "get_session": _make_fake_get_session(mock_job)},
        )

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["job_id"] == "job-123"
        assert output["status"] == "failed"
        assert mock_job.status == JobStatus.failed
        assert mock_job.error == "something went wrong"

    def test_doc_job_done_idempotent(self) -> None:
        """Verifies that doc job done idempotent."""
        runner = CliRunner()
        mock_job = _make_mock_job(status=JobStatus.completed)
        mock_job.error = None

        result = runner.invoke(
            doc_job_done,
            ["job-123"],
            obj={"project_id": "test-proj", "get_session": _make_fake_get_session(mock_job)},
        )

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["job_id"] == "job-123"
        assert output["status"] == "completed"

        result2 = runner.invoke(
            doc_job_done,
            ["job-123", "--error", "this should be ignored"],
            obj={"project_id": "test-proj", "get_session": _make_fake_get_session(mock_job)},
        )

        assert result2.exit_code == 0
        output2 = json.loads(result2.output)
        assert output2["status"] == "completed"
        assert mock_job.error is None

    def test_doc_job_done_job_not_found(self) -> None:
        """Verifies that doc job done job not found."""
        runner = CliRunner()

        result = runner.invoke(
            doc_job_done,
            ["nonexistent-job"],
            obj={"project_id": "test-proj", "get_session": _make_fake_get_session(None)},
        )

        assert result.exit_code == 1
        assert "not found" in result.stderr
