"""Unit tests for DocJobPoller PID liveness probe.

These tests verify that the PID liveness probe in DocJobPoller.poll()
correctly marks dead-subprocess jobs as failed within one poll cycle,
and that recently-started / agent_pid=None jobs are not falsely flagged.

No database is used — the DB is mocked. Real os.kill is patched.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from orch.daemon.doc_job_poller import DocJobPoller

if TYPE_CHECKING:
    from pathlib import Path


def make_config(tmp_path: Path) -> MagicMock:
    """Build a minimal DaemonConfig for the poller."""
    from orch.config import DaemonConfig

    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("")
    return DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106 test fixture
        db_url="postgresql+psycopg://test:test@localhost:5433/test",
        dashboard_host="0.0.0.0.0",
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=600,
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=projects_toml,
    )


def make_job(
    job_id: str | None = None,
    project_id: str = "test-proj",
    status: str = "running",
    agent_pid: int | None = 12345,
    started_at: datetime | None = None,
) -> MagicMock:
    """Make a mock DocGenerationJob with the fields the liveness probe reads."""
    job = MagicMock()
    job.id = job_id or str(uuid.uuid4())
    job.project_id = project_id
    job.status = status
    job.agent_pid = agent_pid
    job.started_at = started_at or datetime.now(UTC) - timedelta(seconds=30)
    job.error = None
    job.skill_used = None
    job.duration_seconds = None
    return job


@contextmanager
def mock_session():
    """Fake session context manager."""
    db = MagicMock()
    yield db


class TestDetectDeadSubprocessJobs:
    """Tests for _detect_dead_subprocess_jobs (the core liveness helper)."""

    def test_dead_pid_includes_job_in_result(self, tmp_path: Path) -> None:
        """A running job whose PID is dead should be returned by _detect_dead_subprocess_jobs."""
        config = make_config(tmp_path)
        mock_factory = MagicMock()

        dead_job = make_job(agent_pid=99999, started_at=datetime.now(UTC) - timedelta(minutes=1))

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [dead_job]

        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        with patch("orch.daemon.doc_job_poller._is_pid_alive", return_value=False):
            poller = DocJobPoller(mock_factory, config)
            result = poller._detect_dead_subprocess_jobs(mock_db)

        assert dead_job in result

    def test_alive_pid_excluded(self, tmp_path: Path) -> None:
        """A running job whose PID is alive must NOT be in the result."""
        config = make_config(tmp_path)
        mock_factory = MagicMock()

        alive_job = make_job(agent_pid=12345, started_at=datetime.now(UTC) - timedelta(minutes=1))

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [alive_job]

        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        with patch("orch.daemon.doc_job_poller._is_pid_alive", return_value=True):
            poller = DocJobPoller(mock_factory, config)
            result = poller._detect_dead_subprocess_jobs(mock_db)

        assert alive_job not in result

    def test_recently_started_job_excluded(self, tmp_path: Path) -> None:
        """A job started within the last 10 seconds must be skipped even if its PID is dead.

        This is the kernel fork-to-PID race protection.
        """
        config = make_config(tmp_path)
        mock_factory = MagicMock()

        # Job started 2 seconds ago — within the 10-second protection window
        young_job = make_job(
            agent_pid=99999,
            started_at=datetime.now(UTC) - timedelta(seconds=2),
        )

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [young_job]

        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        with patch("orch.daemon.doc_job_poller._is_pid_alive", return_value=False):
            poller = DocJobPoller(mock_factory, config)
            result = poller._detect_dead_subprocess_jobs(mock_db)

        assert young_job not in result

    def test_none_agent_pid_excluded(self, tmp_path: Path) -> None:
        """A running job with agent_pid=None must not be probed (no PID to check)."""
        config = make_config(tmp_path)
        mock_factory = MagicMock()

        no_pid_job = make_job(agent_pid=None, started_at=datetime.now(UTC) - timedelta(minutes=1))

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [no_pid_job]

        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        poller = DocJobPoller(mock_factory, config)
        result = poller._detect_dead_subprocess_jobs(mock_db)

        # Should return empty — no dead jobs
        assert result == []


class TestIsPidAlive:
    """Tests for the _is_pid_alive helper used by _detect_dead_subprocess_jobs."""

    def test_processlookuperror_means_dead(self, tmp_path: Path) -> None:
        """os.kill raising ProcessLookupError means the process is gone."""
        with patch("os.kill") as mock_kill:
            mock_kill.side_effect = ProcessLookupError
            from orch.daemon.doc_job_poller import _is_pid_alive

            assert _is_pid_alive(99999) is False

    def test_permission_error_means_alive(self, tmp_path: Path) -> None:
        """os.kill raising PermissionError means the process is alive.

        PermissionError means the kernel knows about the PID — we just
        don't have permission to send it a signal.
        """
        with patch("os.kill") as mock_kill:
            mock_kill.side_effect = PermissionError
            from orch.daemon.doc_job_poller import _is_pid_alive

            assert _is_pid_alive(99999) is True

    def test_no_exception_means_alive(self, tmp_path: Path) -> None:
        """os.kill returning without exception means the process is alive."""
        with patch("os.kill") as mock_kill:
            mock_kill.return_value = None
            from orch.daemon.doc_job_poller import _is_pid_alive

            assert _is_pid_alive(12345) is True


class TestPollDeadSubprocessIntegration:
    """End-to-end poll() behavior when a dead subprocess is detected.

    These tests verify the full flow: poll() → _detect_dead_subprocess_jobs →
    complete_doc_job(error="agent process exited without calling iw doc-job-done").
    """

    def test_dead_pid_marks_job_failed_within_one_cycle(self, tmp_path: Path) -> None:
        """A dead PID causes complete_doc_job to be called with the 'agent process exited' error."""
        config = make_config(tmp_path)
        mock_factory = MagicMock()

        dead_job = make_job(
            agent_pid=99999,
            started_at=datetime.now(UTC) - timedelta(minutes=1),
        )

        mock_db = MagicMock()
        # Return the dead job from the query used by _detect_dead_subprocess_jobs
        mock_db.query.return_value.filter.return_value.all.return_value = [dead_job]
        mock_db.get.return_value = dead_job  # for complete_doc_job lookup

        complete_calls: list[tuple] = []

        def complete_doc_job(job_id, error=None, *, worktree_path=None):
            """Return complete doc job."""
            complete_calls.append((job_id, error, worktree_path))
            return dead_job

        mock_svc = MagicMock()
        mock_svc.get_running_jobs_count.return_value = 0
        mock_svc.get_stalled_jobs.return_value = []
        mock_svc.complete_doc_job.side_effect = complete_doc_job

        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("orch.doc_service.DocService", return_value=mock_svc),
            patch("os.kill") as mock_kill,
        ):
            mock_kill.side_effect = ProcessLookupError  # PID is dead

            poller = DocJobPoller(mock_factory, config)
            poller.poll()

        # complete_doc_job should have been called with the "agent process exited" error
        assert len(complete_calls) == 1
        job_id, error, worktree_path = complete_calls[0]
        assert job_id == dead_job.id
        assert "agent process exited" in (error or "")
        assert worktree_path is not None  # repo_root from the project

    def test_alive_pid_no_change(self, tmp_path: Path) -> None:
        """When os.kill succeeds (alive PID), poll() must NOT call complete_doc_job for that job."""
        config = make_config(tmp_path)
        mock_factory = MagicMock()

        alive_job = make_job(
            agent_pid=12345,
            started_at=datetime.now(UTC) - timedelta(minutes=1),
        )

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [alive_job]

        complete_calls: list = []

        def complete_doc_job(job_id, error=None, *, worktree_path=None):
            """Return complete doc job."""
            complete_calls.append((job_id, error))
            return alive_job

        mock_svc = MagicMock()
        mock_svc.get_running_jobs_count.return_value = 0
        mock_svc.get_stalled_jobs.return_value = []
        mock_svc.complete_doc_job.side_effect = complete_doc_job

        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("orch.doc_service.DocService", return_value=mock_svc),
            patch("os.kill") as mock_kill,
        ):
            mock_kill.return_value = None  # alive

            poller = DocJobPoller(mock_factory, config)
            poller.poll()

        # No complete_doc_job call because the PID is alive
        assert complete_calls == []

    def test_permission_error_treated_as_alive(self, tmp_path: Path) -> None:
        """When os.kill raises PermissionError, the job is treated as alive.

        The job must NOT be marked failed — only ProcessLookupError kills it.
        """
        config = make_config(tmp_path)
        mock_factory = MagicMock()

        job = make_job(agent_pid=12345, started_at=datetime.now(UTC) - timedelta(minutes=1))

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [job]

        complete_calls: list = []

        def complete_doc_job(job_id, error=None, *, worktree_path=None):
            """Return complete doc job."""
            complete_calls.append((job_id, error))
            return job

        mock_svc = MagicMock()
        mock_svc.get_running_jobs_count.return_value = 0
        mock_svc.get_stalled_jobs.return_value = []
        mock_svc.complete_doc_job.side_effect = complete_doc_job

        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("orch.doc_service.DocService", return_value=mock_svc),
            patch("os.kill") as mock_kill,
        ):
            mock_kill.side_effect = PermissionError  # alive but can't signal

            poller = DocJobPoller(mock_factory, config)
            poller.poll()

        assert complete_calls == []

    def test_recently_started_job_skipped(self, tmp_path: Path) -> None:
        """A job started <10s ago must NOT be marked failed even with a dead PID.

        This is the race-protection window for newly forked processes.
        """
        config = make_config(tmp_path)
        mock_factory = MagicMock()

        # 2 seconds old — within the 10-second protection window
        young_job = make_job(
            agent_pid=99999,
            started_at=datetime.now(UTC) - timedelta(seconds=2),
        )

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [young_job]

        complete_calls: list = []

        def complete_doc_job(job_id, error=None, *, worktree_path=None):
            """Return complete doc job."""
            complete_calls.append((job_id, error))
            return young_job

        mock_svc = MagicMock()
        mock_svc.get_running_jobs_count.return_value = 0
        mock_svc.get_stalled_jobs.return_value = []
        mock_svc.complete_doc_job.side_effect = complete_doc_job

        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("orch.doc_service.DocService", return_value=mock_svc),
            patch("os.kill") as mock_kill,
        ):
            mock_kill.side_effect = ProcessLookupError  # dead

            poller = DocJobPoller(mock_factory, config)
            poller.poll()

        # Job should be skipped — no complete_doc_job call
        assert complete_calls == []

    def test_agent_pid_none_skipped(self, tmp_path: Path) -> None:
        """A running job with agent_pid=None must not trigger an os.kill call."""
        config = make_config(tmp_path)
        mock_factory = MagicMock()

        job = make_job(agent_pid=None, started_at=datetime.now(UTC) - timedelta(minutes=1))

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [job]

        complete_calls: list = []

        def complete_doc_job(job_id, error=None, *, worktree_path=None):
            """Return complete doc job."""
            complete_calls.append((job_id, error))
            return job

        mock_svc = MagicMock()
        mock_svc.get_running_jobs_count.return_value = 0
        mock_svc.get_stalled_jobs.return_value = []
        mock_svc.complete_doc_job.side_effect = complete_doc_job

        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        with patch("orch.doc_service.DocService", return_value=mock_svc):
            poller = DocJobPoller(mock_factory, config)
            poller.poll()

        # No complete_doc_job — job is not dead, it has no PID
        assert complete_calls == []

    def test_multiple_dead_jobs_all_marked_failed(self, tmp_path: Path) -> None:
        """When multiple jobs have dead PIDs, all should get complete_doc_job calls."""
        config = make_config(tmp_path)
        mock_factory = MagicMock()

        job1 = make_job(agent_pid=99901, started_at=datetime.now(UTC) - timedelta(minutes=1))
        job2 = make_job(agent_pid=99902, started_at=datetime.now(UTC) - timedelta(minutes=1))

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [job1, job2]

        complete_calls: list = []

        def complete_doc_job(job_id, error=None, *, worktree_path=None):
            """Return complete doc job."""
            complete_calls.append(job_id)
            return job1 if job_id == job1.id else job2

        mock_svc = MagicMock()
        mock_svc.get_running_jobs_count.return_value = 0
        mock_svc.get_stalled_jobs.return_value = []
        mock_svc.complete_doc_job.side_effect = complete_doc_job

        mock_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_factory.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("orch.doc_service.DocService", return_value=mock_svc),
            patch("os.kill") as mock_kill,
        ):
            mock_kill.side_effect = ProcessLookupError  # all dead

            poller = DocJobPoller(mock_factory, config)
            poller.poll()

        assert len(complete_calls) == 2
        assert set(complete_calls) == {job1.id, job2.id}
