"""Integration tests for project_oss_job migration.

Tests:
- Migration applies cleanly and creates the table + enums + indexes
- Downgrade reverses all changes
- ORM model matches migration schema
- FK cascade deletes work correctly
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    PROJECT_DOCS_FTS_FUNCTION_SQL,
    PROJECT_DOCS_FTS_TRIGGER_SQL,
    Base,
    OssScan,
    Project,
    ProjectOssJob,
    ProjectOssJobKind,
    ProjectOssJobStatus,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy import Engine

from testcontainers.postgres import PostgresContainer

MIGRATION_SQL = """
DO $$
BEGIN
    DROP TYPE IF EXISTS ossscan_status;
    CREATE TYPE ossscan_status AS ENUM ('pending', 'running', 'complete', 'error');

    DROP TYPE IF EXISTS ossscan_mode;
    CREATE TYPE ossscan_mode AS ENUM ('scan');

    DROP TYPE IF EXISTS osspill_color;
    CREATE TYPE osspill_color AS ENUM ('green', 'yellow', 'red', 'gray');

    DROP TYPE IF EXISTS ossfinding_severity;
    CREATE TYPE ossfinding_severity AS ENUM ('MUST', 'SHOULD', 'MAY', 'INFO');

    DROP TYPE IF EXISTS ossfinding_status;
    CREATE TYPE ossfinding_status AS ENUM ('pass_status', 'fail', 'skip', 'human_required');

    DROP TYPE IF EXISTS osstoolrun_status;
    CREATE TYPE osstoolrun_status AS ENUM ('ok', 'failed', 'missing', 'skipped');

    DROP TYPE IF EXISTS project_oss_job_kind;
    CREATE TYPE project_oss_job_kind AS ENUM ('scan', 'install', 'fix');

    DROP TYPE IF EXISTS project_oss_job_status;
    CREATE TYPE project_oss_job_status AS ENUM (
        'queued', 'running', 'complete', 'error', 'cancelled'
    );
END$$;

ALTER TABLE projects ADD COLUMN IF NOT EXISTS oss_enabled BOOLEAN NOT NULL DEFAULT false;

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
CREATE INDEX IF NOT EXISTS ix_oss_scan_project_started ON oss_scan (project_id, started_at DESC);

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
CREATE INDEX IF NOT EXISTS ix_oss_finding_scan ON oss_finding (scan_id);
CREATE INDEX IF NOT EXISTS ix_oss_finding_scan_sev_stat ON oss_finding (scan_id, severity, status);

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
CREATE INDEX IF NOT EXISTS ix_oss_tool_run_scan ON oss_tool_run (scan_id);

ALTER TABLE oss_scan ADD CONSTRAINT fk_oss_scan_project
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
ALTER TABLE oss_finding ADD CONSTRAINT fk_oss_finding_scan
    FOREIGN KEY (scan_id) REFERENCES oss_scan(id) ON DELETE CASCADE;
ALTER TABLE oss_tool_run ADD CONSTRAINT fk_oss_tool_run_scan
    FOREIGN KEY (scan_id) REFERENCES oss_scan(id) ON DELETE CASCADE;

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
    base_sha TEXT,
    CONSTRAINT fk_project_oss_job_project FOREIGN KEY (project_id)
        REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_project_oss_job_scan FOREIGN KEY (scan_id)
        REFERENCES oss_scan(id) ON DELETE SET NULL
);
CREATE INDEX ix_project_oss_job_project_created ON project_oss_job (project_id, created_at DESC);
CREATE INDEX ix_project_oss_job_status ON project_oss_job (status);
CREATE UNIQUE INDEX ix_project_oss_job_public_id ON project_oss_job (public_id);
"""

DOWNGRADE_SQL = """
DO $$
BEGIN
    DROP INDEX IF EXISTS ix_project_oss_job_public_id;
    DROP INDEX IF EXISTS ix_project_oss_job_status;
    DROP INDEX IF EXISTS ix_project_oss_job_project_created;
    DROP TABLE IF EXISTS project_oss_job;
    DROP TYPE IF EXISTS project_oss_job_status;
    DROP TYPE IF EXISTS project_oss_job_kind;
    DROP INDEX IF EXISTS ix_oss_tool_run_scan;
    DROP TABLE IF EXISTS oss_tool_run;
    -- oss_finding_detail FKs into oss_finding; drop the child first.
    DROP INDEX IF EXISTS ix_oss_finding_detail_finding;
    DROP TABLE IF EXISTS oss_finding_detail;
    DROP INDEX IF EXISTS ix_oss_finding_scan_sev_stat;
    DROP INDEX IF EXISTS ix_oss_finding_scan;
    DROP TABLE IF EXISTS oss_finding;
    DROP INDEX IF EXISTS ix_oss_scan_project_started;
    DROP TABLE IF EXISTS oss_scan;
    IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'projects') THEN
        ALTER TABLE projects DROP COLUMN IF EXISTS oss_enabled;
    END IF;
    DROP TYPE IF EXISTS osstoolrun_status;
    DROP TYPE IF EXISTS ossfinding_status;
    DROP TYPE IF EXISTS ossfinding_severity;
    DROP TYPE IF EXISTS osspill_color;
    DROP TYPE IF EXISTS ossscan_mode;
    DROP TYPE IF EXISTS ossscan_status;
END$$;
"""


@pytest.fixture(scope="session")
def pg_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def oss_job_engine(pg_container: PostgresContainer) -> Engine:
    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    engine = create_engine(url, pool_pre_ping=True)

    with engine.connect() as conn:
        conn.execute(text(DOWNGRADE_SQL))
        conn.commit()

    # Raw SQL below (MIGRATION_SQL) creates all four OSS tables with the
    # migration-mirrored schema, so exclude them from ORM create_all.
    # oss_finding_detail has an FK to oss_finding (raw-SQL-created), so defer
    # it until after the raw SQL runs.
    # Do NOT mutate Base.metadata — it's shared state across fixtures.
    raw_sql_tables = {"oss_scan", "oss_finding", "oss_tool_run", "project_oss_job"}
    deferred_tables = {"oss_finding_detail"}
    tables_to_create = [
        t
        for name, t in Base.metadata.tables.items()
        if name not in raw_sql_tables and name not in deferred_tables
    ]
    Base.metadata.create_all(engine, tables=tables_to_create)

    with engine.connect() as conn:
        conn.execute(text(FTS_FUNCTION_SQL))
        conn.execute(text(FTS_TRIGGER_SQL))
        conn.execute(text(PROJECT_DOCS_FTS_FUNCTION_SQL))
        conn.execute(text(PROJECT_DOCS_FTS_TRIGGER_SQL))
        conn.execute(text(MIGRATION_SQL))
        conn.commit()

    Base.metadata.create_all(
        engine,
        tables=[Base.metadata.tables[name] for name in deferred_tables],
    )

    return engine


@pytest.fixture(scope="session")
def oss_job_session_factory(oss_job_engine: Engine):
    return sessionmaker(bind=oss_job_engine, autocommit=False, autoflush=False)


@pytest.fixture
def oss_job_session(
    oss_job_engine: Engine, oss_job_session_factory
) -> Generator[Session, None, None]:
    connection = oss_job_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session: Session = session_factory()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def oss_job_test_project(oss_job_session: Session) -> Project:
    project = Project(
        id="test-proj-oss-job",
        display_name="Test OSS Job Project",
        repo_root="/repos/test-oss-job",
        config={},
    )
    oss_job_session.add(project)
    oss_job_session.flush()
    return project


class TestProjectOssJobMigrationApply:
    def test_table_exists(self, oss_job_engine: Engine) -> None:
        inspector = inspect(oss_job_engine)
        assert "project_oss_job" in inspector.get_table_names()

    def test_columns(self, oss_job_engine: Engine) -> None:
        inspector = inspect(oss_job_engine)
        columns = {c["name"] for c in inspector.get_columns("project_oss_job")}
        expected = {
            "id",
            "project_id",
            "kind",
            "status",
            "created_at",
            "started_at",
            "completed_at",
            "exit_code",
            "scan_id",
            "stdout_tail",
            "error_message",
        }
        assert expected.issubset(columns), f"Missing: {expected - columns}"
        # CR-00022: old columns removed
        assert "worktree_path" not in columns
        assert "branch_name" not in columns
        assert "commit_sha" not in columns
        assert "files_changed_summary" not in columns

    def test_kind_enum(self, oss_job_engine: Engine) -> None:
        """project_oss_job_kind enum has exactly {scan, install, fix}."""
        with oss_job_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT enumlabel FROM pg_enum "
                    "WHERE enumtypid = 'project_oss_job_kind'::regtype"
                )
            )
        labels = {row[0] for row in result}
        assert labels == {"scan", "install", "fix"}

    def test_status_enum(self, oss_job_engine: Engine) -> None:
        """project_oss_job_status enum has exactly {queued, running, complete, error, cancelled}."""
        with oss_job_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT enumlabel FROM pg_enum "
                    "WHERE enumtypid = 'project_oss_job_status'::regtype"
                )
            )
        labels = {row[0] for row in result}
        assert labels == {"queued", "running", "complete", "error", "cancelled"}

    def test_insert_scan_job(self, oss_job_session: Session, oss_job_test_project: Project) -> None:
        job = ProjectOssJob(
            project_id=oss_job_test_project.id,
            kind=ProjectOssJobKind.scan,
        )
        oss_job_session.add(job)
        oss_job_session.flush()
        assert job.id is not None
        assert job.project_id == oss_job_test_project.id
        assert job.kind == ProjectOssJobKind.scan
        assert job.status == ProjectOssJobStatus.queued
        assert job.created_at is not None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.exit_code is None
        assert job.scan_id is None
        assert job.stdout_tail is None
        assert job.error_message is None

    def test_insert_all_fields(
        self, oss_job_session: Session, oss_job_test_project: Project
    ) -> None:
        from datetime import UTC, datetime

        now = datetime.now(UTC).replace(tzinfo=None)

        scan = OssScan(project_id=oss_job_test_project.id)
        oss_job_session.add(scan)
        oss_job_session.flush()

        job = ProjectOssJob(
            project_id=oss_job_test_project.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.running,
            started_at=now,
            exit_code=0,
            scan_id=scan.id,
            stdout_tail="gitleaks v1.2.3\n...",
        )
        oss_job_session.add(job)
        oss_job_session.flush()

        assert job.status == ProjectOssJobStatus.running
        assert job.started_at is not None
        assert job.scan_id == scan.id
        assert job.stdout_tail is not None

    def test_insert_scan_job_all_fields(
        self, oss_job_session: Session, oss_job_test_project: Project
    ) -> None:
        """Insert scan job with all available fields (no worktree_path)."""
        from datetime import UTC, datetime

        now = datetime.now(UTC).replace(tzinfo=None)

        scan = OssScan(project_id=oss_job_test_project.id)
        oss_job_session.add(scan)
        oss_job_session.flush()

        job = ProjectOssJob(
            project_id=oss_job_test_project.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.running,
            started_at=now,
            exit_code=0,
            scan_id=scan.id,
            stdout_tail="gitleaks v1.2.3\n...",
        )
        oss_job_session.add(job)
        oss_job_session.flush()

        assert job.status == ProjectOssJobStatus.running
        assert job.started_at is not None
        assert job.scan_id == scan.id
        assert job.stdout_tail is not None

    def test_insert_install_job(
        self, oss_job_session: Session, oss_job_test_project: Project
    ) -> None:
        job = ProjectOssJob(
            project_id=oss_job_test_project.id,
            kind=ProjectOssJobKind.install,
        )
        oss_job_session.add(job)
        oss_job_session.flush()
        assert job.kind == ProjectOssJobKind.install

    def test_complete_job(self, oss_job_session: Session, oss_job_test_project: Project) -> None:
        from datetime import UTC, datetime

        now = datetime.now(UTC).replace(tzinfo=None)
        later = datetime.now(UTC).replace(tzinfo=None)

        job = ProjectOssJob(
            project_id=oss_job_test_project.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.complete,
            started_at=now,
            completed_at=later,
            exit_code=0,
            stdout_tail="scan complete",
        )
        oss_job_session.add(job)
        oss_job_session.flush()
        assert job.status == ProjectOssJobStatus.complete
        assert job.completed_at is not None
        assert job.exit_code == 0

    def test_error_job(self, oss_job_session: Session, oss_job_test_project: Project) -> None:
        job = ProjectOssJob(
            project_id=oss_job_test_project.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.error,
            exit_code=1,
            error_message="scan failed",
            stdout_tail="ERROR: scan failed",
        )
        oss_job_session.add(job)
        oss_job_session.flush()
        assert job.status == ProjectOssJobStatus.error
        assert job.exit_code == 1
        assert job.error_message is not None


class TestProjectOssJobFKConstraints:
    def test_fk_to_project(self, oss_job_session: Session, oss_job_test_project: Project) -> None:
        job = ProjectOssJob(
            project_id=oss_job_test_project.id,
            kind=ProjectOssJobKind.scan,
        )
        oss_job_session.add(job)
        oss_job_session.flush()
        assert job.project_id == oss_job_test_project.id

    def test_fk_invalid_project_id(self, oss_job_session: Session) -> None:
        job = ProjectOssJob(
            project_id="nonexistent-project",
            kind=ProjectOssJobKind.scan,
        )
        oss_job_session.add(job)
        with pytest.raises(IntegrityError):
            oss_job_session.flush()

    def test_fk_scan_id(self, oss_job_session: Session, oss_job_test_project: Project) -> None:
        scan = OssScan(project_id=oss_job_test_project.id)
        oss_job_session.add(scan)
        oss_job_session.flush()

        job = ProjectOssJob(
            project_id=oss_job_test_project.id,
            kind=ProjectOssJobKind.scan,
            scan_id=scan.id,
        )
        oss_job_session.add(job)
        oss_job_session.flush()
        assert job.scan_id == scan.id

    def test_fk_scan_id_set_null_on_delete(
        self, oss_job_session: Session, oss_job_test_project: Project
    ) -> None:
        scan = OssScan(project_id=oss_job_test_project.id)
        oss_job_session.add(scan)
        oss_job_session.flush()

        job = ProjectOssJob(
            project_id=oss_job_test_project.id,
            kind=ProjectOssJobKind.scan,
            scan_id=scan.id,
        )
        oss_job_session.add(job)
        oss_job_session.flush()
        job_id = job.id

        oss_job_session.delete(scan)
        oss_job_session.flush()

        result = oss_job_session.execute(
            text("SELECT scan_id FROM project_oss_job WHERE id = :id"), {"id": job_id}
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] is None


class TestProjectOssJobCascadeDeletes:
    def test_delete_project_cascades_to_jobs(
        self, oss_job_session: Session, oss_job_test_project: Project
    ) -> None:
        job = ProjectOssJob(
            project_id=oss_job_test_project.id,
            kind=ProjectOssJobKind.scan,
        )
        oss_job_session.add(job)
        oss_job_session.flush()
        job_id = job.id

        oss_job_session.delete(oss_job_test_project)
        oss_job_session.flush()

        result = oss_job_session.execute(
            text("SELECT id FROM project_oss_job WHERE id = :id"), {"id": job_id}
        )
        assert result.fetchone() is None


class TestProjectOssJobRelationships:
    def test_project_oss_jobs_relationship(
        self, oss_job_session: Session, oss_job_test_project: Project
    ) -> None:
        job1 = ProjectOssJob(project_id=oss_job_test_project.id, kind=ProjectOssJobKind.scan)
        job2 = ProjectOssJob(project_id=oss_job_test_project.id, kind=ProjectOssJobKind.install)
        oss_job_session.add_all([job1, job2])
        oss_job_session.flush()

        oss_job_session.refresh(oss_job_test_project)
        assert len(oss_job_test_project.oss_jobs) == 2


class TestProjectOssJobMigrationDowngrade:
    def test_downgrade_drops_table(self, oss_job_engine: Engine) -> None:
        inspector = inspect(oss_job_engine)
        assert "project_oss_job" in inspector.get_table_names()

        with oss_job_engine.connect() as conn:
            conn.execute(text(DOWNGRADE_SQL))
            conn.commit()

        inspector = inspect(oss_job_engine)
        assert "project_oss_job" not in inspector.get_table_names()

        with oss_job_engine.connect() as conn:
            result = conn.execute(
                text("SELECT typname FROM pg_type WHERE typname = 'project_oss_job_kind'")
            )
        assert result.fetchone() is None

        # CR-00055 / R-00077: this module shares a session-scoped oss_job_engine.
        # Re-apply the migration SQL so the schema is restored for any test
        # that runs after this one under -p randomly.
        with oss_job_engine.connect() as conn:
            conn.execute(text(MIGRATION_SQL))
            conn.commit()
