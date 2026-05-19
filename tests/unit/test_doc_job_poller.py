"""Unit tests for DocJobPoller and DocService job lifecycle methods.

All database interaction is mocked; subprocess is mocked.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from orch.config import DaemonConfig
from orch.daemon.doc_job_poller import DocJobPoller
from orch.db.models import (
    EditorialCategory,
    JobStatus,
    Project,
    ProjectDoc,
)


def make_config(tmp_path: Path) -> DaemonConfig:
    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("")
    return DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5433/test",
        dashboard_host="0.0.0.0",  # noqa: S104
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


def make_project(
    project_id: str = "test-proj",
    enabled: bool = True,
    cli_tool: str = "opencode",
) -> MagicMock:
    proj = MagicMock(spec=Project)
    proj.id = project_id
    proj.enabled = enabled
    proj.repo_root = "/repos/test"
    proj.config = {"cli_tool": cli_tool}
    return proj


def make_doc(
    project_id: str = "test-proj",
    doc_id: str = "doc001",
    editorial_category: EditorialCategory = EditorialCategory.technical,
    source_paths: list[str] | None = None,
) -> MagicMock:
    doc = MagicMock(spec=ProjectDoc)
    doc.id = f"{project_id}:{doc_id}"
    doc.project_id = project_id
    doc.doc_id = doc_id
    doc.editorial_category = editorial_category
    doc.source_paths = source_paths or ["/src/foo.py", "/src/bar.py"]
    return doc


def make_job(
    project_id: str = "test-proj",
    doc_id: str = "doc001",
    status: JobStatus = JobStatus.queued,
    started_at: datetime | None = None,
    requested_at: datetime | None = None,
    agent_pid: int | None = None,
) -> MagicMock:
    job = MagicMock()
    job.id = str(uuid.uuid4())
    job.project_id = project_id
    job.doc_id = f"{project_id}:{doc_id}"
    job.status = status
    job.started_at = started_at
    job.requested_at = requested_at or datetime.now(UTC)
    job.agent_pid = agent_pid
    job.skill_used = None
    job.duration_seconds = None
    job.error = None
    return job


class TestDocJobPollerSkillSelection:
    def test_select_skill_technical(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        poller = DocJobPoller(MagicMock(), config)
        assert poller._select_skill(EditorialCategory.technical) == "iw-doc-generator"
        assert poller._select_skill(EditorialCategory.functional) == "iw-doc-generator"

    def test_select_skill_guide(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        poller = DocJobPoller(MagicMock(), config)
        assert poller._select_skill(EditorialCategory.guide) == "iw-doc-system"
        assert poller._select_skill(EditorialCategory.compliance) == "iw-doc-system"
        assert poller._select_skill(EditorialCategory.marketing) == "iw-doc-system"
        assert poller._select_skill(EditorialCategory.release) == "iw-doc-system"


class TestDocServiceJobLifecycle:
    def test_create_doc_job(self, tmp_path: Path) -> None:
        from orch.db.models import DocType
        from orch.doc_service import DocService

        mock_db = MagicMock()
        mock_doc = MagicMock(spec=ProjectDoc)
        mock_doc.id = "test-proj:doc001"
        mock_doc.doc_type = DocType.api
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_doc

        svc = DocService(mock_db)
        job = svc.create_doc_job("test-proj", "doc001")

        assert job.project_id == "test-proj"
        assert job.doc_id == "test-proj:doc001"
        assert job.status == JobStatus.queued
        assert job.requested_at is not None
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_create_doc_job_raises_on_missing_doc(self, tmp_path: Path) -> None:
        from orch.doc_service import DocService

        mock_db = MagicMock()
        mock_db.get.return_value = None

        svc = DocService(mock_db)
        with pytest.raises(KeyError):
            svc.create_doc_job("test-proj", "nonexistent")

    def test_start_doc_job(self, tmp_path: Path) -> None:
        from orch.doc_service import DocService

        mock_db = MagicMock()
        mock_job = MagicMock()
        mock_job.status = JobStatus.queued
        mock_db.get.return_value = mock_job

        svc = DocService(mock_db)
        result = svc.start_doc_job("job-123", pid=9999, skill_used="iw-doc-generator")

        assert result.status == JobStatus.running
        assert result.started_at is not None
        assert result.agent_pid == 9999
        assert result.skill_used == "iw-doc-generator"

    def test_start_doc_job_raises_if_not_queued(self, tmp_path: Path) -> None:
        from orch.doc_service import DocService

        mock_db = MagicMock()
        mock_job = MagicMock()
        mock_job.status = JobStatus.running
        mock_db.get.return_value = mock_job

        svc = DocService(mock_db)
        with pytest.raises(ValueError, match="in status 'running'"):
            svc.start_doc_job("job-123")

    def test_complete_doc_job_success(self, tmp_path: Path) -> None:
        from orch.doc_service import DocService

        mock_db = MagicMock()
        mock_job = MagicMock()
        mock_job.status = JobStatus.running
        mock_job.started_at = datetime.now(UTC) - timedelta(seconds=60)
        mock_job.error = None
        mock_job.completed_at = None
        mock_job.duration_seconds = None
        mock_job.doc_id = None
        # CR-00062: doc_service now raises on unknown cli_tool; supply a real
        # project mock so the cli_tool lookup yields the "opencode" default.
        mock_project = MagicMock()
        mock_project.config = {"cli_tool": "opencode"}
        mock_project.repo_root = str(tmp_path)
        mock_db.get.side_effect = [mock_job, mock_project]

        svc = DocService(mock_db)
        result = svc.complete_doc_job("job-123")

        assert result.status == JobStatus.completed
        assert result.completed_at is not None
        assert result.duration_seconds is not None
        assert result.error is None

    def test_complete_doc_job_with_error(self, tmp_path: Path) -> None:
        from orch.doc_service import DocService

        mock_db = MagicMock()
        mock_job = MagicMock()
        mock_job.status = JobStatus.running
        mock_job.started_at = datetime.now(UTC) - timedelta(seconds=60)
        mock_job.error = None
        # CR-00062: doc_service now raises on unknown cli_tool; supply a real
        # project mock so the cli_tool lookup yields the "opencode" default.
        mock_project = MagicMock()
        mock_project.config = {"cli_tool": "opencode"}
        mock_project.repo_root = str(tmp_path)
        mock_db.get.side_effect = [mock_job, mock_project]

        svc = DocService(mock_db)
        result = svc.complete_doc_job("job-123", error="something went wrong")

        assert result.status == JobStatus.failed
        assert result.error == "something went wrong"

    def test_complete_doc_job_idempotent(self, tmp_path: Path) -> None:
        from orch.doc_service import DocService

        mock_db = MagicMock()
        mock_job = MagicMock()
        mock_job.status = JobStatus.completed
        mock_job.error = None
        mock_db.get.return_value = mock_job

        svc = DocService(mock_db)
        result = svc.complete_doc_job("job-123", error="something went wrong")

        assert result.status == JobStatus.completed
        assert result.error is None

    def test_get_running_jobs_count(self, tmp_path: Path) -> None:
        from orch.doc_service import DocService

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 2

        svc = DocService(mock_db)
        count = svc.get_running_jobs_count("test-proj")

        assert count == 2

    def test_get_queued_jobs(self, tmp_path: Path) -> None:
        from orch.doc_service import DocService

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [make_job(), make_job()]

        svc = DocService(mock_db)
        jobs = svc.get_queued_jobs("test-proj", limit=5)

        assert len(jobs) == 2

    def test_get_stalled_jobs(self, tmp_path: Path) -> None:
        from orch.doc_service import DocService

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [
            make_job(
                status=JobStatus.running,
                started_at=datetime.now(UTC) - timedelta(minutes=15),
            )
        ]

        svc = DocService(mock_db)
        stalled = svc.get_stalled_jobs(timeout_minutes=10)

        assert len(stalled) == 1


class TestDocJobPollerLaunch:
    @contextmanager
    def _make_session(self, db):
        yield db

    def test_poll_launches_job_when_slot_available(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        mock_session_factory = MagicMock()

        mock_db = MagicMock()
        mock_project = make_project()
        mock_project.repo_root = str(tmp_path)
        mock_doc = make_doc()
        mock_job = make_job(status=JobStatus.queued)

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_db.get.side_effect = lambda model, key: (
            mock_job
            if model.__name__ == "DocGenerationJob" and key == mock_job.id
            else mock_project
            if model.__name__ == "Project" and key == "test-proj"
            else mock_doc
            if model.__name__ == "ProjectDoc" and key == mock_job.doc_id
            else None
        )
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_project]

        def get_running_jobs_count(project_id):
            return 0

        def get_queued_jobs(project_id, limit=10):
            return [mock_job]

        def get_stalled_jobs(timeout_minutes=10):
            return []

        def complete_doc_job(job_id, error=None, *, worktree_path=None):
            pass

        def start_doc_job(job_id, pid=None, skill_used=None):
            mock_job.status = JobStatus.running
            mock_job.agent_pid = pid
            mock_job.skill_used = skill_used
            return mock_job

        def add_event(event):
            pass

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        mock_svc_instance = MagicMock()
        mock_svc_instance.get_running_jobs_count.side_effect = get_running_jobs_count
        mock_svc_instance.get_queued_jobs.side_effect = get_queued_jobs
        mock_svc_instance.get_stalled_jobs.side_effect = get_stalled_jobs
        mock_svc_instance.complete_doc_job.side_effect = complete_doc_job
        mock_svc_instance.start_doc_job.side_effect = start_doc_job

        call_count = [0]

        def doc_service_constructor(db):
            call_count[0] += 1
            return mock_svc_instance

        mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("orch.doc_service.DocService", side_effect=doc_service_constructor),
            patch("subprocess.Popen") as mock_popen,
            patch.object(DocJobPoller, "_detect_dead_subprocess_jobs", return_value=[]),
        ):
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            poller = DocJobPoller(mock_session_factory, config)
            poller.poll()

        assert mock_svc_instance.start_doc_job.called

    def test_poll_respects_concurrent_limit(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        mock_session_factory = MagicMock()

        mock_db = MagicMock()
        mock_project = make_project()

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_project]

        mock_svc_instance = MagicMock()
        mock_svc_instance.get_running_jobs_count.return_value = 2
        mock_svc_instance.get_stalled_jobs.return_value = []
        mock_svc_instance.get_queued_jobs.return_value = []

        def doc_service_constructor(db):
            return mock_svc_instance

        mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("orch.doc_service.DocService", side_effect=doc_service_constructor),
            patch.object(DocJobPoller, "_detect_dead_subprocess_jobs", return_value=[]),
        ):
            poller = DocJobPoller(mock_session_factory, config)
            poller.poll()

        mock_svc_instance.get_queued_jobs.assert_not_called()

    def test_poll_marks_stalled_jobs_failed(self, tmp_path: Path) -> None:
        config = make_config(tmp_path)
        mock_session_factory = MagicMock()

        mock_db = MagicMock()
        stalled_job = make_job(
            status=JobStatus.running,
            started_at=datetime.now(UTC) - timedelta(minutes=15),
        )

        mock_svc_instance = MagicMock()
        mock_svc_instance.get_stalled_jobs.return_value = [stalled_job]
        mock_svc_instance.get_running_jobs_count.return_value = 0

        complete_called_with = []

        def complete_doc_job(job_id, error=None):
            complete_called_with.append((job_id, error))

        mock_svc_instance.complete_doc_job.side_effect = complete_doc_job

        def doc_service_constructor(db):
            return mock_svc_instance

        mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)

        with patch("orch.doc_service.DocService", side_effect=doc_service_constructor):
            poller = DocJobPoller(mock_session_factory, config)
            poller.poll()

        assert len(complete_called_with) == 1
        assert complete_called_with[0][0] == stalled_job.id
        assert "timeout" in (complete_called_with[0][1] or "").lower()
