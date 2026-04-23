"""Integration tests for orch.oss.persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session

from testcontainers.postgres import PostgresContainer

MIGRATION_SQL = """
DO $$
BEGIN
    -- Drop existing tables first (CASCADE drops FK constraints too)
    DROP TABLE IF EXISTS oss_tool_run CASCADE;
    DROP TABLE IF EXISTS oss_finding CASCADE;
    DROP TABLE IF EXISTS oss_scan CASCADE;

    -- Drop existing enum types (CASCADE drops column dependencies)
    DROP TYPE IF EXISTS osstoolrun_status CASCADE;
    DROP TYPE IF EXISTS ossfinding_status CASCADE;
    DROP TYPE IF EXISTS ossfinding_severity CASCADE;
    DROP TYPE IF EXISTS osspill_color CASCADE;
    DROP TYPE IF EXISTS ossscan_mode CASCADE;
    DROP TYPE IF EXISTS ossscan_status CASCADE;
END$$;

CREATE TYPE ossscan_status AS ENUM ('pending', 'running', 'complete', 'error');
CREATE TYPE ossscan_mode AS ENUM ('scan', 'make_oss', 'publish');
CREATE TYPE osspill_color AS ENUM ('green', 'yellow', 'red', 'gray');
CREATE TYPE ossfinding_severity AS ENUM ('MUST', 'SHOULD', 'MAY', 'INFO');
CREATE TYPE ossfinding_status AS ENUM ('pass_status', 'fail', 'skip', 'human_required');
CREATE TYPE osstoolrun_status AS ENUM ('ok', 'failed', 'missing', 'skipped');

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
    osps_control TEXT,
    tool TEXT,
    evidence_json JSONB
);
CREATE INDEX ix_oss_finding_scan ON oss_finding (scan_id);
CREATE INDEX ix_oss_finding_scan_sev_stat ON oss_finding (scan_id, severity, status);

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
"""


@pytest.fixture(scope="session")
def pg_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def oss_engine(pg_container: PostgresContainer):
    from sqlalchemy import create_engine, text

    from orch.db.models import (
        FTS_FUNCTION_SQL,
        FTS_TRIGGER_SQL,
        PROJECT_DOCS_FTS_FUNCTION_SQL,
        PROJECT_DOCS_FTS_TRIGGER_SQL,
        Base,
    )

    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    engine = create_engine(url, pool_pre_ping=True)

    # Raw SQL below (MIGRATION_SQL) creates oss_scan/oss_finding/oss_tool_run
    # with a custom schema. project_oss_job has an FK to oss_scan, so create it
    # AFTER the raw SQL. Do NOT mutate Base.metadata — shared state.
    raw_sql_tables = {"oss_scan", "oss_finding", "oss_tool_run"}
    deferred_tables = {"project_oss_job"}
    pre_tables = [
        t
        for name, t in Base.metadata.tables.items()
        if name not in raw_sql_tables and name not in deferred_tables
    ]
    Base.metadata.create_all(engine, tables=pre_tables)

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
def oss_session_factory(oss_engine):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=oss_engine, autocommit=False, autoflush=False)


@pytest.fixture
def oss_session(oss_engine, oss_session_factory) -> Generator[Session, None, None]:
    connection = oss_engine.connect()
    transaction = connection.begin()
    session = oss_session_factory(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def oss_test_project(oss_session: Session):
    from orch.db.models import Project

    project = Project(
        id="test-oss-proj",
        display_name="Test OSS Project",
        repo_root="/repos/test",
        config={},
    )
    oss_session.add(project)
    oss_session.flush()
    return project


class TestPersistFindings:
    def test_persist_findings_round_trip(self, oss_session: Session, oss_test_project) -> None:
        from orch.db.models import OssScan
        from orch.oss.persistence import persist_findings

        scan = OssScan(project_id=oss_test_project.id)
        oss_session.add(scan)
        oss_session.flush()

        findings_json = {
            "findings": [
                {
                    "id": "OSS-LIC-01",
                    "severity": "MUST",
                    "status": "fail",
                    "domain": "license",
                    "summary": "LICENSE file not present",
                    "detail": "No LICENSE found in root",
                    "remediation": "Run make_oss to generate",
                    "auto_fix_available": True,
                    "osps_control": "OSPS-LE-03.01",
                    "evidence": {"paths_checked": ["LICENSE", "LICENSE.md"]},
                    "tool": None,
                    "source_research": ["R-00062 #7"],
                },
                {
                    "id": "OSS-SEC-01",
                    "severity": "MUST",
                    "status": "pass",
                    "domain": "secrets",
                    "summary": "No secrets in tree",
                    "detail": None,
                    "remediation": None,
                    "auto_fix_available": False,
                    "osps_control": None,
                    "evidence": {"tool": "gitleaks", "tool_version": "8.21.2"},
                    "tool": "gitleaks",
                    "source_research": [],
                },
            ],
            "tools_available": {
                "gitleaks": "8.21.2",
                "syft": "1.15.0",
            },
        }

        persist_findings(oss_session, scan, findings_json)
        oss_session.commit()

        oss_session.refresh(scan)
        assert len(scan.findings) == 2

        lic_finding = next(f for f in scan.findings if f.check_id == "OSS-LIC-01")
        assert lic_finding.severity.value == "MUST"
        assert lic_finding.status.value == "fail"
        assert lic_finding.auto_fix_available is True

        sec_finding = next(f for f in scan.findings if f.check_id == "OSS-SEC-01")
        assert sec_finding.severity.value == "MUST"
        assert sec_finding.status.value == "pass"


class TestComputePillColor:
    def test_must_fail_returns_red(self) -> None:
        from orch.oss.persistence import compute_pill_color

        result = compute_pill_color({"must_fail": 1, "must_human_required": 0})
        assert result == "red"

    def test_must_human_required_returns_red(self) -> None:
        from orch.oss.persistence import compute_pill_color

        result = compute_pill_color({"must_fail": 0, "must_human_required": 1})
        assert result == "red"

    def test_should_fail_returns_yellow(self) -> None:
        from orch.oss.persistence import compute_pill_color

        result = compute_pill_color(
            {"must_fail": 0, "must_human_required": 0, "should_fail": 1, "should_human_required": 0}
        )
        assert result == "yellow"

    def test_should_human_required_returns_yellow(self) -> None:
        from orch.oss.persistence import compute_pill_color

        result = compute_pill_color(
            {"must_fail": 0, "must_human_required": 0, "should_fail": 0, "should_human_required": 1}
        )
        assert result == "yellow"

    def test_all_pass_returns_green(self) -> None:
        from orch.oss.persistence import compute_pill_color

        result = compute_pill_color(
            {"must_fail": 0, "must_human_required": 0, "should_fail": 0, "should_human_required": 0}
        )
        assert result == "green"

    def test_empty_returns_green(self) -> None:
        from orch.oss.persistence import compute_pill_color

        result = compute_pill_color({})
        assert result == "green"
