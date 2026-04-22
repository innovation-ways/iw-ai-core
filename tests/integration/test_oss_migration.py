"""Integration tests for OSS compliance tables migration.

Tests:
- Migration applies cleanly and creates all 3 tables + column
- Downgrade reverses all changes
- ORM models match migration schema
- FK cascade deletes work correctly

The migration SQL is applied via a session-scoped fixture because the standard
db_engine fixture uses Base.metadata.create_all() which doesn't handle custom
PostgreSQL enums defined in Alembic migrations.
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
    OssFinding,
    OssFindingStatus,
    OssScan,
    OssToolRun,
    Project,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy import Engine

from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

MIGRATION_SQL = """
-- Create ENUM types (always recreate to ensure correct values)
DO $$
BEGIN
    DROP TYPE IF EXISTS ossscan_status;
    CREATE TYPE ossscan_status AS ENUM ('pending', 'running', 'complete', 'error');

    DROP TYPE IF EXISTS ossscan_mode;
    CREATE TYPE ossscan_mode AS ENUM ('scan', 'make_oss', 'publish');

    DROP TYPE IF EXISTS osspill_color;
    CREATE TYPE osspill_color AS ENUM ('green', 'yellow', 'red', 'gray');

    DROP TYPE IF EXISTS ossfinding_severity;
    CREATE TYPE ossfinding_severity AS ENUM ('MUST', 'SHOULD', 'MAY', 'INFO');

    DROP TYPE IF EXISTS ossfinding_status;
    CREATE TYPE ossfinding_status AS ENUM ('pass_status', 'fail', 'skip', 'human_required');

    DROP TYPE IF EXISTS osstoolrun_status;
    CREATE TYPE osstoolrun_status AS ENUM ('ok', 'failed', 'missing', 'skipped');
END$$;

-- Add oss_enabled to projects
ALTER TABLE projects ADD COLUMN IF NOT EXISTS oss_enabled BOOLEAN NOT NULL DEFAULT false;

-- Create oss_scan table
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

-- Create oss_finding table
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
    osps_control TEXT,
    tool TEXT,
    evidence_json JSONB
);
CREATE INDEX IF NOT EXISTS ix_oss_finding_scan ON oss_finding (scan_id);
CREATE INDEX IF NOT EXISTS ix_oss_finding_scan_sev_stat ON oss_finding (scan_id, severity, status);

-- Create oss_tool_run table
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

-- Add FK constraints
ALTER TABLE oss_scan ADD CONSTRAINT fk_oss_scan_project
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
ALTER TABLE oss_finding ADD CONSTRAINT fk_oss_finding_scan
    FOREIGN KEY (scan_id) REFERENCES oss_scan(id) ON DELETE CASCADE;
ALTER TABLE oss_tool_run ADD CONSTRAINT fk_oss_tool_run_scan
    FOREIGN KEY (scan_id) REFERENCES oss_scan(id) ON DELETE CASCADE;
"""

DOWNGRADE_SQL = """
DO $$
BEGIN
    -- Drop tables first (CASCADE handles FK constraints automatically)
    DROP TABLE IF EXISTS oss_tool_run;
    DROP TABLE IF EXISTS oss_finding;
    DROP TABLE IF EXISTS oss_scan;

    -- Drop indexes
    DROP INDEX IF EXISTS ix_oss_tool_run_scan;
    DROP INDEX IF EXISTS ix_oss_finding_scan_sev_stat;
    DROP INDEX IF EXISTS ix_oss_finding_scan;
    DROP INDEX IF EXISTS ix_oss_scan_project_started;

    -- Drop column from projects (only if projects table exists)
    IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'projects') THEN
        ALTER TABLE projects DROP COLUMN IF EXISTS oss_enabled;
    END IF;

    -- Drop enum types (CASCADE drops columns that depend on them)
    DROP TYPE IF EXISTS osstoolrun_status CASCADE;
    DROP TYPE IF EXISTS ossfinding_status CASCADE;
    DROP TYPE IF EXISTS ossfinding_severity CASCADE;
    DROP TYPE IF EXISTS osspill_color CASCADE;
    DROP TYPE IF EXISTS ossscan_mode CASCADE;
    DROP TYPE IF EXISTS ossscan_status CASCADE;
END$$;
"""


@pytest.fixture(scope="session")
def pg_container() -> Generator[PostgresContainer, None, None]:
    """Start a PostgreSQL 15 container for the entire test session."""
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def oss_engine(pg_container: PostgresContainer) -> Engine:
    """Create a SQLAlchemy engine with OSS migration applied.

    This fixture creates a fresh testcontainer, applies Base.metadata.create_all()
    (for standard tables, excluding OSS tables since they need custom enums),
    then applies the OSS migration SQL (for custom enums and OSS-specific tables).
    """
    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    engine = create_engine(url, pool_pre_ping=True)

    # First, clean up any existing OSS objects from previous test runs
    # This ensures a clean state even if previous tests failed
    with engine.connect() as conn:
        conn.execute(text(DOWNGRADE_SQL))
        conn.commit()

    # Create non-OSS tables via create_all, but exclude OSS models since they
    # require custom PostgreSQL enums that create_all() can't handle
    non_oss_metadata = Base.metadata
    for table in [OssScan.__table__, OssFinding.__table__, OssToolRun.__table__]:
        non_oss_metadata.remove(table)
    non_oss_metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(text(FTS_FUNCTION_SQL))
        conn.execute(text(FTS_TRIGGER_SQL))
        conn.execute(text(PROJECT_DOCS_FTS_FUNCTION_SQL))
        conn.execute(text(PROJECT_DOCS_FTS_TRIGGER_SQL))
        conn.execute(text(MIGRATION_SQL))
        conn.commit()

    return engine


@pytest.fixture(scope="session")
def oss_session_factory(oss_engine: Engine):
    """Return a sessionmaker bound to the OSS-migrated engine."""
    return sessionmaker(bind=oss_engine, autocommit=False, autoflush=False)


@pytest.fixture
def oss_session(oss_engine: Engine, oss_session_factory) -> Generator[Session, None, None]:
    """Provide a transactional DB session with OSS tables that rolls back after each test."""
    connection = oss_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session: Session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def oss_test_project(oss_session: Session) -> Project:
    """Insert a minimal Project row inside the current test transaction."""
    project = Project(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    oss_session.add(project)
    oss_session.flush()
    return project


class TestOssMigrationApply:
    def test_oss_scan_table_exists(self, oss_engine: Engine) -> None:
        """oss_scan table is created by migration."""
        inspector = inspect(oss_engine)
        tables = inspector.get_table_names()
        assert "oss_scan" in tables

    def test_oss_finding_table_exists(self, oss_engine: Engine) -> None:
        """oss_finding table is created by migration."""
        inspector = inspect(oss_engine)
        tables = inspector.get_table_names()
        assert "oss_finding" in tables

    def test_oss_tool_run_table_exists(self, oss_engine: Engine) -> None:
        """oss_tool_run table is created by migration."""
        inspector = inspect(oss_engine)
        tables = inspector.get_table_names()
        assert "oss_tool_run" in tables

    def test_project_oss_enabled_column_exists(self, oss_engine: Engine) -> None:
        """projects.oss_enabled column is created."""
        inspector = inspect(oss_engine)
        columns = {c["name"] for c in inspector.get_columns("projects")}
        assert "oss_enabled" in columns

    def test_oss_scan_columns(self, oss_engine: Engine) -> None:
        """oss_scan has all required columns."""
        inspector = inspect(oss_engine)
        columns = {c["name"] for c in inspector.get_columns("oss_scan")}
        expected = {
            "id",
            "project_id",
            "started_at",
            "completed_at",
            "status",
            "mode",
            "exit_code",
            "head_sha",
            "pill_color",
            "summary_json",
            "error_message",
        }
        assert expected.issubset(columns), f"Missing: {expected - columns}"

    def test_oss_finding_columns(self, oss_engine: Engine) -> None:
        """oss_finding has all required columns."""
        inspector = inspect(oss_engine)
        columns = {c["name"] for c in inspector.get_columns("oss_finding")}
        expected = {
            "id",
            "scan_id",
            "check_id",
            "severity",
            "status",
            "domain",
            "summary",
            "detail",
            "remediation",
            "auto_fix_available",
            "osps_control",
            "tool",
            "evidence_json",
        }
        assert expected.issubset(columns), f"Missing: {expected - columns}"

    def test_oss_tool_run_columns(self, oss_engine: Engine) -> None:
        """oss_tool_run has all required columns."""
        inspector = inspect(oss_engine)
        columns = {c["name"] for c in inspector.get_columns("oss_tool_run")}
        expected = {
            "id",
            "scan_id",
            "tool",
            "version",
            "status",
            "started_at",
            "runtime_ms",
            "exit_code",
            "output_summary",
        }
        assert expected.issubset(columns), f"Missing: {expected - columns}"

    def test_oss_scan_indexes(self, oss_engine: Engine) -> None:
        """oss_scan indexes exist."""
        inspector = inspect(oss_engine)
        indexes = {idx["name"] for idx in inspector.get_indexes("oss_scan")}
        assert "ix_oss_scan_project_started" in indexes

    def test_oss_finding_indexes(self, oss_engine: Engine) -> None:
        """oss_finding indexes exist."""
        inspector = inspect(oss_engine)
        indexes = {idx["name"] for idx in inspector.get_indexes("oss_finding")}
        assert "ix_oss_finding_scan" in indexes
        assert "ix_oss_finding_scan_sev_stat" in indexes

    def test_oss_tool_run_indexes(self, oss_engine: Engine) -> None:
        """oss_tool_run indexes exist."""
        inspector = inspect(oss_engine)
        indexes = {idx["name"] for idx in inspector.get_indexes("oss_tool_run")}
        assert "ix_oss_tool_run_scan" in indexes


class TestOssEnumValues:
    def test_oss_scan_status_enum(self, oss_engine: Engine) -> None:
        """ossscan_status enum has correct values."""
        with oss_engine.connect() as conn:
            result = conn.execute(
                text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'ossscan_status'::regtype")
            )
        labels = {row[0] for row in result}
        assert labels == {"pending", "running", "complete", "error"}

    def test_oss_scan_mode_enum(self, oss_engine: Engine) -> None:
        """ossscan_mode enum has correct values."""
        with oss_engine.connect() as conn:
            result = conn.execute(
                text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'ossscan_mode'::regtype")
            )
        labels = {row[0] for row in result}
        assert labels == {"scan", "make_oss", "publish"}

    def test_oss_pill_color_enum(self, oss_engine: Engine) -> None:
        """osspill_color enum has correct values."""
        with oss_engine.connect() as conn:
            result = conn.execute(
                text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'osspill_color'::regtype")
            )
        labels = {row[0] for row in result}
        assert labels == {"green", "yellow", "red", "gray"}

    def test_oss_finding_severity_enum(self, oss_engine: Engine) -> None:
        """ossfinding_severity enum has correct values."""
        with oss_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT enumlabel FROM pg_enum WHERE enumtypid = 'ossfinding_severity'::regtype"
                )
            )
        labels = {row[0] for row in result}
        assert labels == {"MUST", "SHOULD", "MAY", "INFO"}

    def test_oss_finding_status_enum(self, oss_engine: Engine) -> None:
        """ossfinding_status enum has correct values."""
        with oss_engine.connect() as conn:
            result = conn.execute(
                text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'ossfinding_status'::regtype")
            )
        labels = {row[0] for row in result}
        assert labels == {"pass_status", "fail", "skip", "human_required"}

    def test_oss_tool_run_status_enum(self, oss_engine: Engine) -> None:
        """osstoolrun_status enum has correct values."""
        with oss_engine.connect() as conn:
            result = conn.execute(
                text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'osstoolrun_status'::regtype")
            )
        labels = {row[0] for row in result}
        assert labels == {"ok", "failed", "missing", "skipped"}


class TestOssORMModels:
    def test_oss_scan_defaults(self, oss_session: Session, oss_test_project: Project) -> None:
        """OssScan model inserts with correct defaults."""
        scan = OssScan(project_id=oss_test_project.id)
        oss_session.add(scan)
        oss_session.flush()

        assert scan.id is not None
        assert scan.project_id == oss_test_project.id
        assert str(scan.status.value) == "pending"
        assert str(scan.mode.value) == "scan"
        assert scan.started_at is not None
        assert scan.completed_at is None
        assert scan.exit_code is None
        assert scan.head_sha is None
        assert scan.pill_color is None
        assert scan.summary_json is None
        assert scan.error_message is None

    def test_oss_scan_all_fields(self, oss_session: Session, oss_test_project: Project) -> None:
        """OssScan model inserts with all fields populated."""
        from datetime import UTC, datetime

        datetime.now(UTC).replace(tzinfo=None)

        scan = OssScan(
            project_id=oss_test_project.id,
            status="running",
            mode="make_oss",
            exit_code=0,
            head_sha="abc123",
            pill_color="green",
            summary_json={"MUST": 0, "SHOULD": 2},
            error_message=None,
        )
        oss_session.add(scan)
        oss_session.flush()

        assert scan.id is not None
        assert str(scan.status) == "running"
        assert str(scan.mode) == "make_oss"
        assert scan.exit_code == 0
        assert scan.head_sha == "abc123"
        assert str(scan.pill_color) == "green"
        assert scan.summary_json == {"MUST": 0, "SHOULD": 2}

    def test_oss_finding_defaults(self, oss_session: Session, oss_test_project: Project) -> None:
        """OssFinding model inserts with correct defaults."""
        scan = OssScan(project_id=oss_test_project.id)
        oss_session.add(scan)
        oss_session.flush()

        finding = OssFinding(
            scan_id=scan.id,
            check_id="OSS-LIC-01",
            severity="MUST",
            status=OssFindingStatus.pass_status,
            domain="license",
            summary="License header present",
        )
        oss_session.add(finding)
        oss_session.flush()

        assert finding.id is not None
        assert finding.scan_id == scan.id
        assert finding.check_id == "OSS-LIC-01"
        assert str(finding.severity) == "MUST"
        assert finding.status.value == "pass"
        assert finding.domain == "license"
        assert finding.summary == "License header present"
        assert finding.detail is None
        assert finding.remediation is None
        assert finding.auto_fix_available is False
        assert finding.osps_control is None
        assert finding.tool is None
        assert finding.evidence_json is None

    def test_oss_tool_run_defaults(self, oss_session: Session, oss_test_project: Project) -> None:
        """OssToolRun model inserts with correct defaults."""
        from datetime import UTC, datetime

        now = datetime.now(UTC).replace(tzinfo=None)

        scan = OssScan(project_id=oss_test_project.id)
        oss_session.add(scan)
        oss_session.flush()

        tool_run = OssToolRun(
            scan_id=scan.id,
            tool="gitleaks",
            status="ok",
            started_at=now,
        )
        oss_session.add(tool_run)
        oss_session.flush()

        assert tool_run.id is not None
        assert tool_run.scan_id == scan.id
        assert tool_run.tool == "gitleaks"
        assert tool_run.version is None
        status_val = tool_run.status.value if hasattr(tool_run.status, "value") else tool_run.status
        assert str(status_val) == "ok"
        assert tool_run.started_at == now
        assert tool_run.runtime_ms is None
        assert tool_run.exit_code is None
        assert tool_run.output_summary is None


class TestOssFKConstraints:
    def test_oss_finding_fk_to_oss_scan(
        self, oss_session: Session, oss_test_project: Project
    ) -> None:
        """OssFinding FK to OssScan enforces referential integrity."""
        scan = OssScan(project_id=oss_test_project.id)
        oss_session.add(scan)
        oss_session.flush()

        finding = OssFinding(
            scan_id=scan.id,
            check_id="OSS-LIC-01",
            severity="MUST",
            status=OssFindingStatus.pass_status,
            domain="license",
            summary="test",
        )
        oss_session.add(finding)
        oss_session.flush()
        assert finding.scan_id == scan.id

    def test_oss_finding_fk_invalid_scan_id(self, oss_session: Session) -> None:
        """OssFinding with invalid scan_id raises IntegrityError."""
        finding = OssFinding(
            scan_id=999999,
            check_id="OSS-LIC-01",
            severity="MUST",
            status=OssFindingStatus.pass_status,
            domain="license",
            summary="test",
        )
        oss_session.add(finding)
        with pytest.raises(IntegrityError):
            oss_session.flush()

    def test_oss_tool_run_fk_to_oss_scan(
        self, oss_session: Session, oss_test_project: Project
    ) -> None:
        """OssToolRun FK to OssScan enforces referential integrity."""
        from datetime import UTC, datetime

        now = datetime.now(UTC).replace(tzinfo=None)

        scan = OssScan(project_id=oss_test_project.id)
        oss_session.add(scan)
        oss_session.flush()

        tool_run = OssToolRun(
            scan_id=scan.id,
            tool="gitleaks",
            status="ok",
            started_at=now,
        )
        oss_session.add(tool_run)
        oss_session.flush()
        assert tool_run.scan_id == scan.id

    def test_oss_tool_run_fk_invalid_scan_id(self, oss_session: Session) -> None:
        """OssToolRun with invalid scan_id raises IntegrityError."""
        from datetime import UTC, datetime

        now = datetime.now(UTC).replace(tzinfo=None)

        tool_run = OssToolRun(
            scan_id=999999,
            tool="gitleaks",
            status="ok",
            started_at=now,
        )
        oss_session.add(tool_run)
        with pytest.raises(IntegrityError):
            oss_session.flush()

    def test_oss_scan_fk_to_project(self, oss_session: Session, oss_test_project: Project) -> None:
        """OssScan FK to Project enforces referential integrity."""
        scan = OssScan(project_id=oss_test_project.id)
        oss_session.add(scan)
        oss_session.flush()
        assert scan.project_id == oss_test_project.id

    def test_oss_scan_fk_invalid_project_id(self, oss_session: Session) -> None:
        """OssScan with invalid project_id raises IntegrityError."""
        scan = OssScan(project_id="nonexistent-project")
        oss_session.add(scan)
        with pytest.raises(IntegrityError):
            oss_session.flush()


class TestOssCascadeDeletes:
    def test_delete_project_cascades_to_scans(
        self, oss_session: Session, oss_test_project: Project
    ) -> None:
        """Deleting a project deletes its oss_scans."""
        scan = OssScan(project_id=oss_test_project.id)
        oss_session.add(scan)
        oss_session.flush()
        scan_id = scan.id

        oss_session.delete(oss_test_project)
        oss_session.flush()

        result = oss_session.execute(
            text("SELECT id FROM oss_scan WHERE id = :id"), {"id": scan_id}
        )
        assert result.fetchone() is None

    def test_delete_scan_cascades_to_findings(
        self, oss_session: Session, oss_test_project: Project
    ) -> None:
        """Deleting an oss_scan deletes its oss_findings."""
        scan = OssScan(project_id=oss_test_project.id)
        oss_session.add(scan)
        oss_session.flush()

        finding = OssFinding(
            scan_id=scan.id,
            check_id="OSS-LIC-01",
            severity="MUST",
            status=OssFindingStatus.pass_status,
            domain="license",
            summary="test",
        )
        oss_session.add(finding)
        oss_session.flush()
        finding_id = finding.id

        oss_session.delete(scan)
        oss_session.flush()

        result = oss_session.execute(
            text("SELECT id FROM oss_finding WHERE id = :id"), {"id": finding_id}
        )
        assert result.fetchone() is None

    def test_delete_scan_cascades_to_tool_runs(
        self, oss_session: Session, oss_test_project: Project
    ) -> None:
        """Deleting an oss_scan deletes its oss_tool_runs."""
        from datetime import UTC, datetime

        now = datetime.now(UTC).replace(tzinfo=None)

        scan = OssScan(project_id=oss_test_project.id)
        oss_session.add(scan)
        oss_session.flush()

        tool_run = OssToolRun(
            scan_id=scan.id,
            tool="gitleaks",
            status="ok",
            started_at=now,
        )
        oss_session.add(tool_run)
        oss_session.flush()
        tool_run_id = tool_run.id

        oss_session.delete(scan)
        oss_session.flush()

        result = oss_session.execute(
            text("SELECT id FROM oss_tool_run WHERE id = :id"), {"id": tool_run_id}
        )
        assert result.fetchone() is None


class TestOssRelationships:
    def test_project_oss_scans_relationship(
        self, oss_session: Session, oss_test_project: Project
    ) -> None:
        """Project.oss_scans relationship works."""
        scan1 = OssScan(project_id=oss_test_project.id)
        scan2 = OssScan(project_id=oss_test_project.id)
        oss_session.add_all([scan1, scan2])
        oss_session.flush()

        oss_session.refresh(oss_test_project)
        assert len(oss_test_project.oss_scans) == 2

    def test_oss_scan_findings_relationship(
        self, oss_session: Session, oss_test_project: Project
    ) -> None:
        """OssScan.findings relationship works."""
        scan = OssScan(project_id=oss_test_project.id)
        oss_session.add(scan)
        oss_session.flush()

        finding1 = OssFinding(
            scan_id=scan.id,
            check_id="OSS-LIC-01",
            severity="MUST",
            status=OssFindingStatus.pass_status,
            domain="license",
            summary="test1",
        )
        finding2 = OssFinding(
            scan_id=scan.id,
            check_id="OSS-LIC-02",
            severity="SHOULD",
            status="fail",
            domain="license",
            summary="test2",
        )
        oss_session.add_all([finding1, finding2])
        oss_session.flush()

        oss_session.refresh(scan)
        assert len(scan.findings) == 2

    def test_oss_scan_tool_runs_relationship(
        self, oss_session: Session, oss_test_project: Project
    ) -> None:
        """OssScan.tool_runs relationship works."""
        from datetime import UTC, datetime

        now = datetime.now(UTC).replace(tzinfo=None)

        scan = OssScan(project_id=oss_test_project.id)
        oss_session.add(scan)
        oss_session.flush()

        tr1 = OssToolRun(scan_id=scan.id, tool="gitleaks", status="ok", started_at=now)
        tr2 = OssToolRun(scan_id=scan.id, tool="syft", status="ok", started_at=now)
        oss_session.add_all([tr1, tr2])
        oss_session.flush()

        oss_session.refresh(scan)
        assert len(scan.tool_runs) == 2


class TestProjectOssEnabled:
    def test_project_oss_enabled_default(
        self, oss_session: Session, oss_test_project: Project
    ) -> None:
        """Project.oss_enabled defaults to False."""
        assert oss_test_project.oss_enabled is False

    def test_project_oss_enabled_can_be_set(
        self, oss_session: Session, oss_test_project: Project
    ) -> None:
        """Project.oss_enabled can be set to True."""
        oss_test_project.oss_enabled = True
        oss_session.flush()
        assert oss_test_project.oss_enabled is True


class TestOssMigrationDowngrade:
    def test_downgrade_drops_tables(self, oss_engine: Engine) -> None:
        """Downgrade removes oss_tool_run, oss_finding, oss_scan tables."""
        inspector = inspect(oss_engine)
        assert "oss_tool_run" in inspector.get_table_names()
        assert "oss_finding" in inspector.get_table_names()
        assert "oss_scan" in inspector.get_table_names()

        with oss_engine.connect() as conn:
            conn.execute(text(DOWNGRADE_SQL))
            conn.commit()

        inspector = inspect(oss_engine)
        assert "oss_tool_run" not in inspector.get_table_names()
        assert "oss_finding" not in inspector.get_table_names()
        assert "oss_scan" not in inspector.get_table_names()

        with oss_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'projects' AND column_name = 'oss_enabled'"
                )
            )
        assert result.fetchone() is None
