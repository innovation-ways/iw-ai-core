"""Integration tests for OSS HEAD freshness detection (AC5).

Covers the stale/fresh behavior when git HEAD advances after a scan.
Uses PostgreSQL testcontainer exclusively (never the live DB on port 5433).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session

from testcontainers.postgres import PostgresContainer

from orch.cli.main import cli
from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    PROJECT_DOCS_FTS_FUNCTION_SQL,
    PROJECT_DOCS_FTS_TRIGGER_SQL,
    Base,
    OssPillColor,
    OssScan,
    Project,
)

MIGRATION_SQL = """
DROP TABLE IF EXISTS oss_tool_run CASCADE;
DROP TABLE IF EXISTS oss_finding CASCADE;
DROP TABLE IF EXISTS oss_scan CASCADE;

DROP TYPE IF EXISTS osstoolrun_status CASCADE;
DROP TYPE IF EXISTS ossfinding_status CASCADE;
DROP TYPE IF EXISTS ossfinding_severity CASCADE;
DROP TYPE IF EXISTS osspill_color CASCADE;
DROP TYPE IF EXISTS ossscan_mode CASCADE;
DROP TYPE IF EXISTS ossscan_status CASCADE;
"""

ENGINE_SETUP_SQL = """
CREATE TYPE ossscan_status AS ENUM ('pending', 'running', 'complete', 'error');
CREATE TYPE ossscan_mode AS ENUM ('scan', 'make_oss', 'publish');
CREATE TYPE osspill_color AS ENUM ('green', 'yellow', 'red', 'gray');
CREATE TYPE ossfinding_severity AS ENUM ('MUST', 'SHOULD', 'MAY', 'INFO');
CREATE TYPE ossfinding_status AS ENUM ('pass_status', 'fail', 'skip', 'human_required');
CREATE TYPE osstoolrun_status AS ENUM ('ok', 'failed', 'missing', 'skipped');

ALTER TABLE projects ADD COLUMN IF NOT EXISTS oss_enabled BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE oss_scan (
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

CREATE TABLE oss_finding (
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

CREATE TABLE oss_tool_run (
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

    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    engine = create_engine(url, pool_pre_ping=True)

    # Raw SQL below (ENGINE_SETUP_SQL) creates oss_scan/oss_finding/oss_tool_run
    # with a custom schema. project_oss_job has an FK to oss_scan, so it must
    # be created AFTER the raw SQL. Do NOT mutate Base.metadata — shared state.
    raw_sql_tables = {"oss_scan", "oss_finding", "oss_tool_run"}
    deferred_tables = {"project_oss_job", "oss_finding_detail"}
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
        conn.execute(text(ENGINE_SETUP_SQL))
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
def git_repo_with_commit(tmp_path: Path) -> tuple[Path, str]:
    """A git repo at a known commit SHA."""
    repo = tmp_path / "freshness-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Initial\n")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, capture_output=True)

    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
    initial_sha = result.stdout.strip()

    return repo, initial_sha


class TestOssFreshness:
    def test_stale_detection_after_commit(
        self,
        oss_session: Session,
        git_repo_with_commit: tuple[Path, str],
    ) -> None:
        """AC5: scan at SHA A, commit to advance HEAD to B, status --json → stale: true."""
        repo, initial_sha = git_repo_with_commit

        project = Project(
            id="freshness-stale",
            display_name="Freshness Stale",
            repo_root=str(repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

        scan = OssScan(
            project_id=project.id,
            head_sha=initial_sha,
            status="complete",
            exit_code=0,
        )
        oss_session.add(scan)
        oss_session.commit()

        (repo / "new_feature.py").write_text("# new feature\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "new commit"], cwd=repo, capture_output=True)

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "status", "--project", "freshness-stale", "--json"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["stale"] is True
        assert data["head_sha"] == initial_sha

        current_sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
        )
        current_sha = current_sha_result.stdout.strip()
        assert current_sha != initial_sha

    def test_fresh_when_head_matches(
        self,
        oss_session: Session,
        git_repo_with_commit: tuple[Path, str],
    ) -> None:
        """AC5: scan at HEAD, status --json immediately → stale: false."""
        repo, initial_sha = git_repo_with_commit

        project = Project(
            id="freshness-fresh",
            display_name="Freshness Fresh",
            repo_root=str(repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

        scan = OssScan(
            project_id=project.id,
            head_sha=initial_sha,
            status="complete",
            exit_code=0,
        )
        oss_session.add(scan)
        oss_session.commit()

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "status", "--project", "freshness-fresh", "--json"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["stale"] is False
        assert data["head_sha"] == initial_sha

    def test_stale_preserves_last_pill_color(
        self,
        oss_session: Session,
        git_repo_with_commit: tuple[Path, str],
    ) -> None:
        """AC5: even when stale, pill_color is the last scan's value (flagged stale separately)."""
        repo, initial_sha = git_repo_with_commit

        project = Project(
            id="freshness-preserve-pill",
            display_name="Freshness Preserve Pill",
            repo_root=str(repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

        scan = OssScan(
            project_id=project.id,
            head_sha=initial_sha,
            status="complete",
            exit_code=0,
            pill_color=OssPillColor.green,
        )
        oss_session.add(scan)
        oss_session.commit()

        (repo / "breaking.py").write_text("# breaking\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "breaking change"], cwd=repo, capture_output=True)

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "status", "--project", "freshness-preserve-pill", "--json"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["stale"] is True
        assert data["pill_color"] == "green"
