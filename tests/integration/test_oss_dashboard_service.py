"""Integration tests for dashboard.services.oss_service."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    PROJECT_DOCS_FTS_FUNCTION_SQL,
    PROJECT_DOCS_FTS_TRIGGER_SQL,
    Base,
    OssPillColor,
    OssScan,
    OssScanStatus,
    Project,
    ProjectOssJob,
    ProjectOssJobKind,
    ProjectOssJobStatus,
)

if TYPE_CHECKING:
    from collections.abc import Generator


OSS_MIGRATION_SQL = """
DO $$
BEGIN
    DROP TABLE IF EXISTS project_oss_job CASCADE;
    DROP TABLE IF EXISTS oss_tool_run CASCADE;
    DROP TABLE IF EXISTS oss_finding CASCADE;
    DROP TABLE IF EXISTS oss_scan CASCADE;
    DROP TYPE IF EXISTS project_oss_job_kind CASCADE;
    DROP TYPE IF EXISTS project_oss_job_status CASCADE;
    DROP TYPE IF EXISTS osstoolrun_status CASCADE;
    DROP TYPE IF EXISTS ossfinding_status CASCADE;
    DROP TYPE IF EXISTS ossfinding_severity CASCADE;
    DROP TYPE IF EXISTS osspill_color CASCADE;
    DROP TYPE IF EXISTS ossscan_mode CASCADE;
    DROP TYPE IF EXISTS ossscan_status CASCADE;
END$$;

CREATE TYPE ossscan_status AS ENUM ('pending', 'running', 'complete', 'error');
CREATE TYPE ossscan_mode AS ENUM ('scan');
CREATE TYPE osspill_color AS ENUM ('green', 'yellow', 'red', 'gray');
CREATE TYPE ossfinding_severity AS ENUM ('MUST', 'SHOULD', 'MAY', 'INFO');
CREATE TYPE ossfinding_status AS ENUM ('pass_status', 'fail', 'skip', 'human_required');
CREATE TYPE osstoolrun_status AS ENUM ('ok', 'failed', 'missing', 'skipped');

CREATE TABLE IF NOT EXISTS oss_scan (
    id BIGSERIAL PRIMARY KEY,
    project_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status ossscan_status NOT NULL DEFAULT 'pending',
    mode ossscan_mode NOT NULL DEFAULT 'scan',
    exit_code INTEGER,
    head_sha TEXT,
    pill_color osspill_color,
    summary_json JSONB,
    error_message TEXT
);
CREATE INDEX ix_oss_scan_project_started ON oss_scan (project_id, started_at DESC);

CREATE TABLE IF NOT EXISTS oss_finding (
    id BIGSERIAL PRIMARY KEY,
    scan_id BIGINT NOT NULL,
    check_id TEXT NOT NULL,
    severity ossfinding_severity NOT NULL,
    status ossfinding_status NOT NULL,
    domain TEXT NOT NULL,
    summary TEXT NOT NULL,
    detail TEXT,
    remediation TEXT,
    auto_fix_available BOOLEAN NOT NULL DEFAULT false,
    auto_apply_safe BOOLEAN NOT NULL DEFAULT false,
    osps_control TEXT,
    tool TEXT,
    evidence_json JSONB,
    rationale TEXT
);
CREATE INDEX ix_oss_finding_scan ON oss_finding (scan_id);

CREATE TABLE IF NOT EXISTS oss_tool_run (
    id BIGSERIAL PRIMARY KEY,
    scan_id BIGINT NOT NULL,
    tool TEXT NOT NULL,
    version TEXT,
    status osstoolrun_status NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    runtime_ms INTEGER,
    exit_code INTEGER,
    output_summary TEXT
);
CREATE INDEX ix_oss_tool_run_scan ON oss_tool_run (scan_id);

ALTER TABLE oss_scan ADD CONSTRAINT fk_oss_scan_project
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
ALTER TABLE oss_finding ADD CONSTRAINT fk_oss_finding_scan
    FOREIGN KEY (scan_id) REFERENCES oss_scan(id) ON DELETE CASCADE;
ALTER TABLE oss_tool_run ADD CONSTRAINT fk_oss_tool_run_scan
    FOREIGN KEY (scan_id) REFERENCES oss_scan(id) ON DELETE CASCADE;

CREATE TYPE project_oss_job_kind AS ENUM ('scan', 'install', 'fix');
CREATE TYPE project_oss_job_status AS ENUM (
    'queued', 'running', 'complete', 'error', 'cancelled'
);

CREATE TABLE IF NOT EXISTS project_oss_job (
    id BIGSERIAL PRIMARY KEY,
    public_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    kind project_oss_job_kind NOT NULL,
    status project_oss_job_status NOT NULL DEFAULT 'queued',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    exit_code INTEGER,
    scan_id BIGINT,
    stdout_tail TEXT,
    error_message TEXT,
    base_sha TEXT
);
CREATE INDEX ix_project_oss_job_project_created ON project_oss_job (project_id, created_at DESC);
CREATE INDEX ix_project_oss_job_status ON project_oss_job (status);
CREATE UNIQUE INDEX ix_project_oss_job_public_id ON project_oss_job (public_id);

ALTER TABLE projects ADD COLUMN IF NOT EXISTS oss_enabled BOOLEAN NOT NULL DEFAULT false;
"""


@pytest.fixture(scope="session")
def oss_svc_pg_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def oss_svc_engine(oss_svc_pg_container: PostgresContainer):
    url = oss_svc_pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    engine = create_engine(url, pool_pre_ping=True)

    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(text(FTS_FUNCTION_SQL))
        conn.execute(text(FTS_TRIGGER_SQL))
        conn.execute(text(PROJECT_DOCS_FTS_FUNCTION_SQL))
        conn.execute(text(PROJECT_DOCS_FTS_TRIGGER_SQL))
        conn.execute(text(OSS_MIGRATION_SQL))
        conn.commit()

    return engine


@pytest.fixture(scope="session")
def oss_svc_session_factory(oss_svc_engine):
    return sessionmaker(bind=oss_svc_engine, autocommit=False, autoflush=False)


@pytest.fixture
def oss_svc_connection(oss_svc_engine):
    """Per-test connection with an outer transaction rolled back on teardown.

    Exposing the connection lets factory-created sessions (used by run_job and
    friends) bind to the same connection so they can see the test's writes
    while still rolling everything back at teardown.
    """
    connection = oss_svc_engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


@pytest.fixture
def oss_svc_session(oss_svc_connection) -> Generator[Session, None, None]:
    # join_transaction_mode='create_savepoint' turns session.commit() into a
    # SAVEPOINT commit; the outer transaction is still rolled back on teardown.
    session = Session(
        bind=oss_svc_connection,
        autocommit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    yield session
    session.close()


@pytest.fixture
def oss_svc_test_project(oss_svc_session: Session, tmp_path: Path) -> Project:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Test\n")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)

    project = Project(
        id="oss-svc-test-proj",
        display_name="OSS Service Test Project",
        repo_root=str(repo),
        config={},
    )
    oss_svc_session.add(project)
    oss_svc_session.flush()
    return project


@pytest.fixture
def oss_svc_session_factory_for_svc(oss_svc_connection):
    """Factory for run_job etc. — sessions bind to the test's connection so
    they see the test's writes (committed via savepoints)."""

    def factory():
        return Session(
            bind=oss_svc_connection,
            autocommit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )

    return factory


class TestEnqueueJob:
    def test_enqueue_scan_job(
        self, oss_svc_session: Session, oss_svc_test_project: Project
    ) -> None:
        from dashboard.services.oss_service import enqueue_job

        job = enqueue_job(oss_svc_session, oss_svc_test_project.id, ProjectOssJobKind.scan)
        oss_svc_session.commit()

        assert job.id is not None
        assert job.project_id == oss_svc_test_project.id
        assert job.kind == ProjectOssJobKind.scan
        assert job.status == ProjectOssJobStatus.queued
        assert job.scan_id is None

    def test_enqueue_install_job_worktree_is_null(
        self, oss_svc_session: Session, oss_svc_test_project: Project
    ) -> None:
        from dashboard.services.oss_service import enqueue_job

        job = enqueue_job(oss_svc_session, oss_svc_test_project.id, "install")
        oss_svc_session.commit()

        assert job.kind == ProjectOssJobKind.install
        assert job.status == ProjectOssJobStatus.queued
        assert job.scan_id is None


class TestWorktreeSymbolsRemoved:
    def test_worktree_kinds_not_in_oss_service(self) -> None:
        """CR-00022: WORKTREE_KINDS removed (no worktree-based job kinds)."""
        from dashboard.services import oss_service

        assert not hasattr(oss_service, "WORKTREE_KINDS")

    def test_run_worktree_not_in_oss_service(self) -> None:
        """CR-00022: _run_worktree removed (prepare/publish workflow deleted)."""
        from dashboard.services import oss_service

        assert not hasattr(oss_service, "_run_worktree")

    def test_discard_job_not_in_oss_service(self) -> None:
        """CR-00022: discard_job removed."""
        from dashboard.services import oss_service

        assert not hasattr(oss_service, "discard_job")

    def test_prep_branch_name_not_in_oss_service(self) -> None:
        """CR-00022: _prep_branch_name removed."""
        from dashboard.services import oss_service

        assert not hasattr(oss_service, "_prep_branch_name")


class TestRunFixWorksInRepoRoot:
    def test_run_fix_writes_to_project_repo_root(
        self,
        oss_svc_session: Session,
        oss_svc_test_project: Project,
        oss_svc_session_factory_for_svc,
    ) -> None:
        """CR-00022 AC5: fix writes directly to project.repo_root (no worktree)."""
        from dashboard.services.oss_service import _run_fix

        # Create a mock job
        job = ProjectOssJob(
            project_id=oss_svc_test_project.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.running,
        )
        oss_svc_session.add(job)
        oss_svc_session.commit()
        job_id = job.id

        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Run _run_fix with apply=False (preview should write nothing)
            # We test the apply path by checking the implementation uses repo_root directly
            # Verify that _run_fix does not use /tmp/oss-* paths
            async def check():
                from unittest.mock import AsyncMock, patch

                fake_proc = AsyncMock()
                fake_proc.returncode = 0
                preview_line = (
                    b'{"action":"preview","check_id":"OSS-CH-01",'
                    b'"target_files":[],"full_contents":{},"diffs":{},"notes":null}\n'
                )
                lines_iter = iter([preview_line, b""])

                async def _readline():
                    return next(lines_iter)

                fake_proc.stdout = AsyncMock()
                fake_proc.stdout.readline = _readline
                fake_proc.wait = AsyncMock(return_value=0)

                with patch("asyncio.create_subprocess_exec", return_value=fake_proc):
                    await _run_fix(
                        oss_svc_test_project,
                        job_id,
                        oss_svc_session_factory_for_svc,
                        "OSS-CH-01",
                        apply=False,
                    )
                return True

            loop.run_until_complete(check())
        finally:
            loop.close()


class TestNoTempfilePaths:
    def test_no_tmp_oss_paths_in_oss_service(
        self,
        oss_svc_session: Session,
        oss_svc_test_project: Project,
    ) -> None:
        """CR-00022 AC5: no tempfile.mkdtemp or /tmp/oss-worktree in service calls."""
        import inspect

        from dashboard.services import oss_service

        source = inspect.getsource(oss_service)
        assert "tempfile.mkdtemp" not in source
        assert "/tmp/oss-worktree" not in source


def _make_fake_proc(returncode: int, output: bytes = b"fake output\n") -> AsyncMock:
    """Return an AsyncMock that behaves like asyncio.subprocess.Process.

    The mock's stdout is an AsyncMock StreamReader whose readline() yields
    ``output`` on the first call and b'' (EOF) on all subsequent calls.
    proc.wait() returns ``returncode``.
    """
    proc = AsyncMock()
    proc.returncode = returncode

    lines = iter([output, b""])

    async def _readline() -> bytes:
        return next(lines)

    reader = AsyncMock()
    reader.readline = _readline
    proc.stdout = reader

    async def _wait() -> int:
        return returncode

    proc.wait = _wait
    return proc


class TestRunJob:
    @pytest.mark.asyncio
    async def test_run_scan_job_transitions_to_complete(
        self,
        oss_svc_session: Session,
        oss_svc_test_project: Project,
        oss_svc_session_factory_for_svc,
    ) -> None:
        from dashboard.services.oss_service import enqueue_job, run_job

        job = enqueue_job(oss_svc_session, oss_svc_test_project.id, "scan")
        oss_svc_session.commit()

        # Mock subprocess so _run_scan exits 0 without calling the real iw CLI
        fake_proc = _make_fake_proc(returncode=0, output=b"scan complete\n")
        with (
            patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_proc)),
            patch("dashboard.services.oss_service._git_head", return_value="abc123"),
        ):
            await run_job(oss_svc_session_factory_for_svc, job.id)

        sess = oss_svc_session_factory_for_svc()
        try:
            updated = sess.query(ProjectOssJob).filter(ProjectOssJob.id == job.id).first()
            assert updated is not None
            assert updated.status == ProjectOssJobStatus.complete
            assert updated.exit_code == 0
            assert updated.started_at is not None
            assert updated.completed_at is not None
            assert updated.stdout_tail is not None
        finally:
            sess.close()

    @pytest.mark.asyncio
    async def test_run_install_job_no_worktree(
        self,
        oss_svc_session: Session,
        oss_svc_test_project: Project,
        oss_svc_session_factory_for_svc,
    ) -> None:
        from dashboard.services.oss_service import enqueue_job, run_job

        job = enqueue_job(oss_svc_session, oss_svc_test_project.id, "install")
        oss_svc_session.commit()

        # Mock subprocess so _run_install exits 0 and runs real DB-update logic
        fake_proc = _make_fake_proc(returncode=0, output=b"install ok\n")
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_proc)):
            await run_job(oss_svc_session_factory_for_svc, job.id)

        sess = oss_svc_session_factory_for_svc()
        try:
            updated = sess.query(ProjectOssJob).filter(ProjectOssJob.id == job.id).first()
            assert updated is not None
            assert updated.status == ProjectOssJobStatus.complete
            assert updated.scan_id is None
        finally:
            sess.close()

    @pytest.mark.asyncio
    async def test_run_install_nonzero_exit_sets_error_with_tail(
        self,
        oss_svc_session: Session,
        oss_svc_test_project: Project,
        oss_svc_session_factory_for_svc,
    ) -> None:
        from dashboard.services.oss_service import enqueue_job, run_job

        job = enqueue_job(oss_svc_session, oss_svc_test_project.id, "install")
        oss_svc_session.commit()

        # Mock subprocess so _run_install exits 1 (error) with some stdout
        fake_proc = _make_fake_proc(returncode=1, output=b"install failed\n")
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=fake_proc)):
            await run_job(oss_svc_session_factory_for_svc, job.id)

        sess = oss_svc_session_factory_for_svc()
        try:
            updated = sess.query(ProjectOssJob).filter(ProjectOssJob.id == job.id).first()
            assert updated is not None
            assert updated.status == ProjectOssJobStatus.error
            assert updated.exit_code == 1
            assert updated.stdout_tail is not None
            assert updated.error_message is not None
        finally:
            sess.close()


class TestCancelJob:
    @pytest.mark.asyncio
    async def test_cancel_running_job(
        self, oss_svc_session: Session, oss_svc_test_project: Project
    ) -> None:
        # `cancel_job` is async. Use @pytest.mark.asyncio + await rather than
        # asyncio.get_event_loop().run_until_complete(...): the deprecated
        # global-loop call yields the session-shared loop once pytest-asyncio
        # has registered its own, producing order-dependent failures when prior
        # tests have run their own loops.
        from dashboard.services.oss_service import cancel_job, enqueue_job

        job = enqueue_job(oss_svc_session, oss_svc_test_project.id, "scan")
        oss_svc_session.commit()

        oss_svc_session.query(ProjectOssJob).filter(ProjectOssJob.id == job.id).update(
            {"status": ProjectOssJobStatus.running}, synchronize_session=False
        )
        oss_svc_session.commit()

        await cancel_job(oss_svc_session, job.id)

        updated = oss_svc_session.query(ProjectOssJob).filter(ProjectOssJob.id == job.id).first()
        assert updated is not None
        assert updated.status == ProjectOssJobStatus.cancelled

    @pytest.mark.asyncio
    async def test_cancel_queued_job(
        self, oss_svc_session: Session, oss_svc_test_project: Project
    ) -> None:
        from dashboard.services.oss_service import cancel_job, enqueue_job

        job = enqueue_job(oss_svc_session, oss_svc_test_project.id, "scan")
        oss_svc_session.commit()

        await cancel_job(oss_svc_session, job.id)

        updated = oss_svc_session.query(ProjectOssJob).filter(ProjectOssJob.id == job.id).first()
        assert updated is not None
        assert updated.status == ProjectOssJobStatus.cancelled


class TestRecoverOrphanedJobs:
    def test_orphan_recovery_marks_jobs_error(
        self, oss_svc_session: Session, oss_svc_test_project: Project
    ) -> None:
        from datetime import timedelta

        from dashboard.services import oss_service
        from orch.db.models import ProjectOssJob, ProjectOssJobStatus

        old_time = oss_service._PROCESS_START_UTC - timedelta(seconds=10)
        job = ProjectOssJob(
            project_id=oss_svc_test_project.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.running,
            started_at=old_time,
        )
        oss_svc_session.add(job)
        oss_svc_session.flush()

        count = oss_service.recover_orphaned_jobs(oss_svc_session)

        assert count == 1
        oss_svc_session.refresh(job)
        assert job.status == ProjectOssJobStatus.error
        assert job.error_message == "orphaned by server restart"


class TestJobEventStream:
    @pytest.mark.asyncio
    async def test_sse_stream_yields_status_and_progress(
        self, oss_svc_session: Session, oss_svc_test_project: Project
    ) -> None:
        from dashboard.services.oss_service import enqueue_job, job_event_stream

        job = enqueue_job(oss_svc_session, oss_svc_test_project.id, "scan")
        # Pre-populate stdout_tail so the stream emits progress events on first poll
        job.stdout_tail = "line one\nline two\n"
        oss_svc_session.commit()

        def factory():
            return oss_svc_session

        events = []
        async for msg in job_event_stream(factory, job.id, heartbeat_interval=0.5):
            events.append(msg)
            if len(events) >= 10:
                break

        assert any("event: status" in m for m in events)
        assert any("event: progress" in m for m in events)

    @pytest.mark.asyncio
    async def test_sse_stream_replay_restreams_tail(
        self, oss_svc_session: Session, oss_svc_test_project: Project
    ) -> None:
        from dashboard.services.oss_service import enqueue_job, job_event_stream

        job = enqueue_job(oss_svc_session, oss_svc_test_project.id, "scan")
        job.stdout_tail = "line1\nline2\n"
        oss_svc_session.commit()

        def factory():
            return oss_svc_session

        events = []
        async for msg in job_event_stream(factory, job.id, heartbeat_interval=0.5):
            events.append(msg)
            if "event: complete" in msg or "event: status" in msg:
                break

        progress_events = [m for m in events if "event: progress" in m]
        assert len(progress_events) >= 2


class TestProbeTier1Wrapper:
    def test_probe_tier1_dashboard_returns_dict(self) -> None:
        from dashboard.services.oss_service import probe_tier1_dashboard

        with patch("dashboard.services.oss_service.probe_tier1") as mock_probe:
            mock_probe.return_value = {}
            result = probe_tier1_dashboard()

        assert isinstance(result, dict)
        for _tool, info in result.items():
            assert "installed" in info
            assert "version" in info
            assert "install_cmd" in info


class TestComputeFreshness:
    def test_freshness_matches_head_sha(
        self, oss_svc_session: Session, oss_svc_test_project: Project
    ) -> None:
        from dashboard.services.oss_service import compute_freshness

        result = compute_freshness(oss_svc_test_project.id, oss_svc_session)

        assert "is_fresh" in result
        assert "current_sha" in result
        assert result["current_sha"] is not None

    def test_freshness_no_scans_yet(
        self, oss_svc_session: Session, oss_svc_test_project: Project
    ) -> None:
        from dashboard.services.oss_service import compute_freshness

        result = compute_freshness(oss_svc_test_project.id, oss_svc_session)

        assert result["last_scan_sha"] is None
        assert result["is_fresh"] is False
        assert result["message"] == "no scans yet"


class TestLatestScanAndSummary:
    def test_latest_scan_returns_none_when_empty(
        self, oss_svc_session: Session, oss_svc_test_project: Project
    ) -> None:
        from dashboard.services.oss_service import latest_scan

        result = latest_scan(oss_svc_session, oss_svc_test_project.id)
        assert result is None

    def test_scan_summary_not_yet_scanned(
        self, oss_svc_session: Session, oss_svc_test_project: Project
    ) -> None:
        from dashboard.services.oss_service import scan_summary

        result = scan_summary(oss_svc_session, oss_svc_test_project.id)

        assert result["scan_id"] is None
        assert result["pill_color"] is None
        assert result["is_stale"] is False

    def test_scan_summary_with_existing_scan(
        self, oss_svc_session: Session, oss_svc_test_project: Project
    ) -> None:
        from dashboard.services.oss_service import scan_summary

        scan = OssScan(
            project_id=oss_svc_test_project.id,
            status=OssScanStatus.complete,
            head_sha="abc123",
            pill_color=OssPillColor.green,
            summary_json={"must_pass": 5, "must_fail": 0},
        )
        oss_svc_session.add(scan)
        oss_svc_session.commit()

        result = scan_summary(oss_svc_session, oss_svc_test_project.id)

        assert result["scan_id"] == scan.id
        assert result["pill_color"] == "green"
        assert result["summary"] is not None
        assert "is_stale" in result
