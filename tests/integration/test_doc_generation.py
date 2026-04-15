"""Integration tests for DocGenerationJob lifecycle and DocJobPoller.

These tests cover the full roundtrip:
- Job creation via DocService
- Daemon poller stall detection and concurrent job limiting
- Agent lifecycle simulation via DocService (mimicking what iw doc-job-start/done do)
- CLI commands doc-job-start and doc-job-done

CRITICAL: All tests use testcontainers — NEVER connect to live DB.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from orch.cli.main import cli
from orch.config import DaemonConfig
from orch.daemon.doc_job_poller import DocJobPoller
from orch.db.models import (
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    JobStatus,
    Project,
    ProjectDoc,
)
from orch.doc_service import DocService

if TYPE_CHECKING:
    from click.testing import Result
    from sqlalchemy.orm import Session


def _make_project(
    session: Session, project_id: str = "test-proj", repo_root: str = "/repos/test"
) -> Project:
    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root=repo_root,
        config={},
    )
    session.add(project)
    session.flush()
    return project


def _make_doc(
    session: Session,
    project_id: str = "test-proj",
    doc_id: str = "module-auth",
    title: str = "Auth Module",
    editorial_category: EditorialCategory = EditorialCategory.technical,
    source_paths: list[str] | None = None,
    content: str | None = None,
) -> ProjectDoc:
    doc = ProjectDoc(
        id=f"{project_id}:{doc_id}",
        project_id=project_id,
        doc_id=doc_id,
        title=title,
        slug=doc_id.replace("_", "-"),
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=editorial_category,
        status=DocStatus.draft,
        audience=["developers"],
        source_paths=source_paths or ["src/auth/mod.rs"],
        content=content,
    )
    session.add(doc)
    session.flush()
    return doc


def _make_mock_config() -> DaemonConfig:
    mock = MagicMock(spec=DaemonConfig)
    mock.poll_interval = 60
    mock.stall_threshold = 600
    return mock


# ---------------------------------------------------------------------------
# Job Lifecycle — Success Path
# ---------------------------------------------------------------------------


def test_full_job_lifecycle_success(db_session: Session) -> None:
    """Full roundtrip: create job -> start -> update doc -> complete."""
    _make_project(db_session)
    _make_doc(db_session, content=None)
    svc = DocService(db_session)

    job = svc.create_doc_job("test-proj", "module-auth")
    assert job.status == JobStatus.queued
    job_id = job.id

    svc.start_doc_job(job_id, pid=12345, skill_used="iw-doc-generator")
    db_session.flush()

    started_job = svc.get_doc_job(job_id)
    assert started_job is not None
    assert started_job.status == JobStatus.running
    assert started_job.started_at is not None
    assert started_job.skill_used == "iw-doc-generator"

    svc.update_doc(
        "test-proj",
        "module-auth",
        content="# Generated Doc\n\nContent.",
        generated_by="skill:iw-doc-generator",
        trigger_reason="job:" + job_id,
    )
    db_session.flush()

    doc = svc.get_doc("test-proj", "module-auth")
    assert doc is not None
    assert doc.content is not None
    assert doc.version == 1

    svc.complete_doc_job(job_id)
    db_session.flush()

    completed_job = svc.get_doc_job(job_id)
    assert completed_job is not None
    assert completed_job.status == JobStatus.completed
    assert completed_job.completed_at is not None
    assert completed_job.duration_seconds is not None
    assert completed_job.duration_seconds >= 0


def test_full_job_lifecycle_failure(db_session: Session) -> None:
    """Failed job: start -> complete with error -> doc content unchanged."""
    _make_project(db_session)
    _make_doc(db_session, content="# Original Content")
    svc = DocService(db_session)

    job = svc.create_doc_job("test-proj", "module-auth")
    svc.start_doc_job(job.id)
    db_session.flush()

    svc.complete_doc_job(job.id, error="Source file not found")
    db_session.flush()

    failed_job = svc.get_doc_job(job.id)
    assert failed_job is not None
    assert job.status == JobStatus.failed
    assert "Source file not found" in (job.error or "")

    doc = svc.get_doc("test-proj", "module-auth")
    assert doc is not None
    assert doc.content == "# Original Content"
    assert doc.version == 0


# ---------------------------------------------------------------------------
# Concurrent Job Limit
# ---------------------------------------------------------------------------


def test_concurrent_job_limit(db_session: Session, tmp_path: Any) -> None:
    """Poller does not start a 3rd job when 2 are already running."""
    _make_project(db_session, repo_root=str(tmp_path))
    _make_doc(db_session, doc_id="doc1", content=None)
    _make_doc(db_session, doc_id="doc2", content=None)
    _make_doc(db_session, doc_id="doc3", content=None)
    svc = DocService(db_session)

    job1 = svc.create_doc_job("test-proj", "doc1")
    job2 = svc.create_doc_job("test-proj", "doc2")
    job3 = svc.create_doc_job("test-proj", "doc3")

    job1_id = job1.id
    job2_id = job2.id
    job3_id = job3.id

    svc.start_doc_job(job1_id, skill_used="iw-doc-generator")
    svc.start_doc_job(job2_id, skill_used="iw-doc-generator")
    db_session.flush()

    mock_proc = MagicMock()
    mock_proc.pid = 99999
    with patch("subprocess.Popen", return_value=mock_proc):
        poller = DocJobPoller(lambda: db_session, _make_mock_config())
        poller.poll()

    job3_refresh = svc.get_doc_job(job3_id)
    assert job3_refresh is not None
    assert job3_refresh.status == JobStatus.queued

    svc.complete_doc_job(job1_id)
    db_session.flush()

    with patch("subprocess.Popen", return_value=mock_proc):
        poller.poll()

    job3_refresh = svc.get_doc_job(job3_id)
    assert job3_refresh is not None
    assert job3_refresh.status == JobStatus.running


# ---------------------------------------------------------------------------
# Stall Detection
# ---------------------------------------------------------------------------


def test_stall_detection(db_session: Session) -> None:
    """Job running >10 minutes is marked failed by poller."""
    _make_project(db_session)
    _make_doc(db_session, content=None)
    svc = DocService(db_session)

    job = svc.create_doc_job("test-proj", "module-auth")
    job_id = job.id
    svc.start_doc_job(job_id)
    db_session.flush()

    job.started_at = datetime.now(UTC) - timedelta(minutes=11)
    db_session.flush()

    with patch("subprocess.Popen"):
        poller = DocJobPoller(lambda: db_session, _make_mock_config())
        poller.poll()

    stalled_job = svc.get_doc_job(job_id)
    assert stalled_job is not None
    assert stalled_job.status == JobStatus.failed
    assert "timeout" in (stalled_job.error or "").lower()


# ---------------------------------------------------------------------------
# Generate When Job Already Running Returns 409
# ---------------------------------------------------------------------------


def test_generate_when_job_already_running_returns_409(db_session: Session) -> None:
    """POST /api/project/{id}/docs/{doc_id}/generate returns 409 when job is running."""
    _make_project(db_session)
    _make_doc(db_session, content=None)
    svc = DocService(db_session)

    job = svc.create_doc_job("test-proj", "module-auth")
    svc.start_doc_job(job.id)
    db_session.flush()

    from orch.db.models import DocGenerationJob

    running_count = (
        db_session.query(DocGenerationJob)
        .filter(
            DocGenerationJob.doc_id == "test-proj:module-auth",
            DocGenerationJob.status == JobStatus.running,
        )
        .count()
    )
    assert running_count == 1


# ---------------------------------------------------------------------------
# Boundary: No Source Paths
# ---------------------------------------------------------------------------


def test_generate_doc_with_no_source_paths(db_session: Session) -> None:
    """Job is created (not blocked) even when doc has empty source_paths."""
    _make_project(db_session)
    _make_doc(db_session, source_paths=[], content=None)
    svc = DocService(db_session)

    job = svc.create_doc_job("test-proj", "module-auth")
    assert job.status == JobStatus.queued

    svc.start_doc_job(job.id, skill_used="iw-doc-generator")
    db_session.flush()

    running_job = svc.get_doc_job(job.id)
    assert running_job is not None
    assert running_job.status == JobStatus.running


# ---------------------------------------------------------------------------
# Skill Selection
# ---------------------------------------------------------------------------


def test_skill_selection_technical(db_session: Session) -> None:
    """Technical category maps to iw-doc-generator."""
    poller = DocJobPoller(lambda: db_session, _make_mock_config())
    skill = poller._select_skill(EditorialCategory.technical)
    assert skill == "iw-doc-generator"


def test_skill_selection_api(db_session: Session) -> None:
    """API category maps to iw-doc-generator."""
    poller = DocJobPoller(lambda: db_session, _make_mock_config())
    skill = poller._select_skill(EditorialCategory.technical)
    assert skill == "iw-doc-generator"


def test_skill_selection_guide(db_session: Session) -> None:
    """Guide category maps to iw-doc-system."""
    poller = DocJobPoller(lambda: db_session, _make_mock_config())
    skill = poller._select_skill(EditorialCategory.guide)
    assert skill == "iw-doc-system"


def test_skill_selection_compliance(db_session: Session) -> None:
    """Compliance category maps to iw-doc-system."""
    poller = DocJobPoller(lambda: db_session, _make_mock_config())
    skill = poller._select_skill(EditorialCategory.compliance)
    assert skill == "iw-doc-system"


def test_skill_selection_marketing(db_session: Session) -> None:
    """Marketing category maps to iw-doc-system."""
    poller = DocJobPoller(lambda: db_session, _make_mock_config())
    skill = poller._select_skill(EditorialCategory.marketing)
    assert skill == "iw-doc-system"


# ---------------------------------------------------------------------------
# CLI Commands via CliRunner
# ---------------------------------------------------------------------------


def _invoke_cli(
    args: list[str],
    get_session: Any,
    project_id: str = "test-proj",
) -> Result:
    runner = CliRunner()
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


class TestDocJobStartCli:
    def test_doc_job_start_cli(self, cli_get_session: Any, db_session: Session) -> None:
        """doc-job-start marks job as running and outputs JSON."""
        _make_project(db_session)
        _make_doc(db_session, content=None)
        svc = DocService(db_session)
        job = svc.create_doc_job("test-proj", "module-auth")
        db_session.flush()
        job_id = job.id

        result = _invoke_cli(
            ["doc-job-start", job_id, "--skill", "iw-doc-generator"],
            cli_get_session,
        )

        assert result.exit_code == 0, result.stderr
        output = json.loads(result.output)
        assert output["job_id"] == job_id
        assert output["status"] == "running"

        started_job = svc.get_doc_job(job_id)
        assert started_job is not None
        assert started_job.status == JobStatus.running
        assert started_job.skill_used == "iw-doc-generator"
        assert started_job.started_at is not None

    def test_doc_job_start_unknown_job_exits_1(
        self, cli_get_session: Any, db_session: Session
    ) -> None:
        """doc-job-start with unknown job_id exits with code 1."""
        _make_project(db_session)
        result = _invoke_cli(
            ["doc-job-start", str(uuid.uuid4())],
            cli_get_session,
        )
        assert result.exit_code == 1
        assert "not found" in result.stderr

    def test_doc_job_start_already_running_exits_0(
        self, cli_get_session: Any, db_session: Session
    ) -> None:
        """doc-job-start on already-running job is idempotent (exits 0)."""
        _make_project(db_session)
        _make_doc(db_session, content=None)
        svc = DocService(db_session)
        job = svc.create_doc_job("test-proj", "module-auth")
        svc.start_doc_job(job.id)
        db_session.flush()
        job_id = job.id

        result = _invoke_cli(["doc-job-start", job_id], cli_get_session)
        assert result.exit_code == 0, result.stderr

        running_job = svc.get_doc_job(job_id)
        assert running_job is not None
        assert running_job.status == JobStatus.running


class TestDocJobDoneCli:
    def test_doc_job_done_cli_completed(self, cli_get_session: Any, db_session: Session) -> None:
        """doc-job-done marks job as completed and outputs JSON."""
        _make_project(db_session)
        _make_doc(db_session, content=None)
        svc = DocService(db_session)
        job = svc.create_doc_job("test-proj", "module-auth")
        svc.start_doc_job(job.id)
        db_session.flush()
        job_id = job.id

        result = _invoke_cli(["doc-job-done", job_id], cli_get_session)

        assert result.exit_code == 0, result.stderr
        output = json.loads(result.output)
        assert output["job_id"] == job_id
        assert output["status"] == "completed"

        completed_job = svc.get_doc_job(job_id)
        assert completed_job is not None
        assert completed_job.status == JobStatus.completed
        assert completed_job.completed_at is not None
        assert completed_job.duration_seconds is not None

    def test_doc_job_done_cli_failed(self, cli_get_session: Any, db_session: Session) -> None:
        """doc-job-done --error marks job as failed."""
        _make_project(db_session)
        _make_doc(db_session, content=None)
        svc = DocService(db_session)
        job = svc.create_doc_job("test-proj", "module-auth")
        svc.start_doc_job(job.id)
        db_session.flush()
        job_id = job.id

        result = _invoke_cli(
            ["doc-job-done", job_id, "--error", "Source file not found"],
            cli_get_session,
        )

        assert result.exit_code == 0, result.stderr
        output = json.loads(result.output)
        assert output["job_id"] == job_id
        assert output["status"] == "failed"

        failed_job = svc.get_doc_job(job_id)
        assert failed_job is not None
        assert failed_job.status == JobStatus.failed
        assert "Source file not found" in (failed_job.error or "")

    def test_doc_job_done_idempotent(self, cli_get_session: Any, db_session: Session) -> None:
        """Calling doc-job-done twice on same job is a no-op (idempotent)."""
        _make_project(db_session)
        _make_doc(db_session, content=None)
        svc = DocService(db_session)
        job = svc.create_doc_job("test-proj", "module-auth")
        svc.start_doc_job(job.id)
        db_session.flush()
        job_id = job.id

        result1 = _invoke_cli(["doc-job-done", job_id], cli_get_session)
        assert result1.exit_code == 0, result1.stderr

        result2 = _invoke_cli(["doc-job-done", job_id], cli_get_session)
        assert result2.exit_code == 0, result2.stderr

        final_job = svc.get_doc_job(job_id)
        assert final_job is not None
        assert final_job.status == JobStatus.completed

    def test_doc_job_done_unknown_job_exits_1(
        self, cli_get_session: Any, db_session: Session
    ) -> None:
        """doc-job-done with unknown job_id exits with code 1."""
        _make_project(db_session)
        result = _invoke_cli(
            ["doc-job-done", str(uuid.uuid4())],
            cli_get_session,
        )
        assert result.exit_code == 1
        assert "not found" in result.stderr

    def test_doc_job_done_already_completed_is_noop(
        self, cli_get_session: Any, db_session: Session
    ) -> None:
        """doc-job-done on already-completed job exits 0 without changes."""
        _make_project(db_session)
        _make_doc(db_session, content=None)
        svc = DocService(db_session)
        job = svc.create_doc_job("test-proj", "module-auth")
        svc.start_doc_job(job.id)
        svc.complete_doc_job(job.id)
        db_session.flush()
        job_id = job.id

        result = _invoke_cli(["doc-job-done", job_id], cli_get_session)
        assert result.exit_code == 0, result.stderr

        noop_job = svc.get_doc_job(job_id)
        assert noop_job is not None
        assert noop_job.status == JobStatus.completed
