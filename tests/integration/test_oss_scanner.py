"""Integration tests for orch.oss.scanner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session

from testcontainers.postgres import PostgresContainer

MIGRATION_SQL = """
DO $$
BEGIN
    DROP TABLE IF EXISTS oss_tool_run CASCADE;
    DROP TABLE IF EXISTS oss_finding CASCADE;
    DROP TABLE IF EXISTS oss_scan CASCADE;

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
    evidence_json JSONB,
    rationale TEXT
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


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    (repo / ".iw").mkdir()
    (repo / "README.md").write_text("# Test Project\n")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, capture_output=True)
    return repo


class TestOssScannerRunScan:
    def test_run_scan_creates_oss_scan_row(
        self,
        oss_session: Session,
        oss_test_project,
        fixture_repo: Path,
    ) -> None:
        from orch.db.models import Project
        from orch.oss.scanner import run_scan

        project = oss_session.get(Project, oss_test_project.id)
        assert project is not None

        skill_scan_path = (
            Path(__file__).resolve().parents[4]
            / ".claude"
            / "skills"
            / "iw-oss-publish"
            / "scripts"
            / "scan.py"
        )

        if not skill_scan_path.exists():
            pytest.skip("skill scan.py not found")

        findings_file = fixture_repo / ".iw" / "oss-publish-findings.json"
        findings_file.parent.mkdir(parents=True, exist_ok=True)
        findings_file.write_text(
            json.dumps(
                {
                    "skill_version": "0.1.0",
                    "findings": [],
                    "summary": {
                        "must_pass": 0,
                        "must_fail": 0,
                        "should_pass": 0,
                        "should_fail": 0,
                        "may_pass": 0,
                        "may_fail": 0,
                        "total": 0,
                        "exit_code": 0,
                    },
                    "tools_available": {},
                    "config": {},
                    "repo": {
                        "current_branch": "main",
                        "head_sha": "abc123",
                        "visibility": "private",
                        "remote_url": "",
                        "commit_count": 1,
                        "contributor_email_count": 0,
                        "ecosystems_detected": [],
                    },
                }
            )
        )

        def session_factory():
            return oss_session

        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            scan = loop.run_until_complete(
                run_scan(
                    project,
                    "scan",
                    session_factory=session_factory,
                    skill_scan_path=skill_scan_path,
                )
            )
        finally:
            loop.close()

        assert scan is not None
        assert scan.id is not None
        oss_session.refresh(scan)
        assert scan.project_id == oss_test_project.id
