"""Integration tests for oss CLI commands.

Tests the CLI layer using Click's CliRunner with a real PostgreSQL
testcontainer (never the live DB on port 5433).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session

from testcontainers.postgres import PostgresContainer

from orch.cli.main import cli

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

ALTER TABLE oss_scan ADD CONSTRAINT fk_oss_scan_project  -- noqa: E501
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
ALTER TABLE oss_finding ADD CONSTRAINT fk_oss_finding_scan  -- noqa: E501
    FOREIGN KEY (scan_id) REFERENCES oss_scan(id) ON DELETE CASCADE;
ALTER TABLE oss_tool_run ADD CONSTRAINT fk_oss_tool_run_scan  -- noqa: E501
    FOREIGN KEY (scan_id) REFERENCES oss_scan(id) ON DELETE CASCADE;
"""


@pytest.fixture(scope="session")
def pg_container() -> PostgresContainer:
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def oss_engine(pg_container: PostgresContainer) -> Engine:
    from sqlalchemy import create_engine, text

    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    engine = create_engine(url, pool_pre_ping=True)

    from orch.db.models import FTS_FUNCTION_SQL, FTS_TRIGGER_SQL, Base

    # Raw SQL below (MIGRATION_SQL) creates oss_scan/oss_finding/oss_tool_run
    # with a custom schema. project_oss_job has an FK to oss_scan, so it must
    # be created AFTER the raw SQL. Do NOT mutate Base.metadata — shared state.
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
        conn.execute(text(MIGRATION_SQL))
        conn.commit()

    # Create project_oss_job now that oss_scan (its FK target) exists.
    Base.metadata.create_all(
        engine,
        tables=[Base.metadata.tables[name] for name in deferred_tables],
    )

    return engine


@pytest.fixture(scope="session")
def oss_session_factory(oss_engine: Engine):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=oss_engine, autocommit=False, autoflush=False)


@pytest.fixture
def oss_session(oss_engine: Engine, oss_session_factory) -> Session:
    connection = oss_engine.connect()
    transaction = connection.begin()
    session = oss_session_factory(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Test\n")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
    return repo


class TestOssEnable:
    def test_oss_enable_writes_config_and_flips_flag(
        self,
        oss_session: Session,
        test_repo: Path,
    ) -> None:
        """iw oss enable writes .iw/oss-publish.toml and flips project.oss_enabled."""
        from orch.db.models import Project

        project = Project(
            id="cli-test-proj",
            display_name="CLI Test Project",
            repo_root=str(test_repo),
            config={},
        )
        oss_session.add(project)
        oss_session.commit()

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "enable", "--project", "cli-test-proj"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 0, result.output

        enabled_project = oss_session.get(Project, "cli-test-proj")
        assert enabled_project is not None
        assert enabled_project.oss_enabled is True

        config_path = test_repo / ".iw" / "oss-publish.toml"
        assert config_path.exists()

    def test_oss_enable_idempotent_when_config_unchanged(
        self,
        oss_session: Session,
        test_repo: Path,
    ) -> None:
        """Running enable twice with unchanged config is idempotent."""
        from orch.db.models import Project

        project = Project(
            id="cli-test-proj2",
            display_name="CLI Test Project 2",
            repo_root=str(test_repo),
            config={},
        )
        oss_session.add(project)
        oss_session.commit()

        def _get_session():
            return oss_session

        result1 = CliRunner().invoke(
            cli,
            ["oss", "enable", "--project", "cli-test-proj2"],
            obj={"get_session": _get_session},
        )
        assert result1.exit_code == 0, result1.output

        result2 = CliRunner().invoke(
            cli,
            ["oss", "enable", "--project", "cli-test-proj2"],
            obj={"get_session": _get_session},
        )
        assert result2.exit_code == 0, result2.output

    def test_oss_enable_refuses_without_force_if_config_differs(
        self,
        oss_session: Session,
        test_repo: Path,
    ) -> None:
        """enable refuses to overwrite hand-edited config without --force."""
        from orch.db.models import Project

        project = Project(
            id="cli-test-proj3",
            display_name="CLI Test Project 3",
            repo_root=str(test_repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

        config_path = test_repo / ".iw" / "oss-publish.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("# hand-edited content that differs from rendered default\n")

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "enable", "--project", "cli-test-proj3"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 2
        assert "--force" in result.output

    def test_oss_enable_overwrites_with_force(
        self,
        oss_session: Session,
        test_repo: Path,
    ) -> None:
        """enable --force overwrites hand-edited config."""
        from orch.db.models import Project

        project = Project(
            id="cli-test-proj4",
            display_name="CLI Test Project 4",
            repo_root=str(test_repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

        config_path = test_repo / ".iw" / "oss-publish.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("# hand-edited content\n")

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "enable", "--project", "cli-test-proj4", "--force"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 0

    def test_oss_enable_exits_2_on_non_git_repo(
        self,
        oss_session: Session,
    ) -> None:
        """enable exits 2 when project path is not a git repo."""
        from orch.db.models import Project

        project = Project(
            id="non-git-proj",
            display_name="Non-Git Project",
            repo_root="/tmp/non-existent-path-that-is-not-git",
            config={},
        )
        oss_session.add(project)
        oss_session.commit()

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "enable", "--project", "non-git-proj"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 2
        assert "not a git repo" in result.output

    def test_oss_enable_exits_2_when_project_not_found(self, oss_session: Session) -> None:
        """enable exits 2 when project does not exist."""

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "enable", "--project", "does-not-exist"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 2


class TestOssDisable:
    def test_oss_disable_clears_flag(
        self,
        oss_session: Session,
        test_repo: Path,
    ) -> None:
        """iw oss disable clears project.oss_enabled."""
        from orch.db.models import Project

        project = Project(
            id="cli-test-proj5",
            display_name="CLI Test Project 5",
            repo_root=str(test_repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "disable", "--project", "cli-test-proj5"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 0, result.output

        disabled_project = oss_session.get(Project, "cli-test-proj5")
        assert disabled_project is not None
        assert disabled_project.oss_enabled is False


class TestOssScan:
    def test_oss_scan_refuses_when_disabled(
        self,
        oss_session: Session,
        test_repo: Path,
    ) -> None:
        """iw oss scan refuses to scan a disabled project with exit 2."""
        from orch.db.models import Project

        project = Project(
            id="cli-test-proj6",
            display_name="CLI Test Project 6",
            repo_root=str(test_repo),
            config={},
        )
        oss_session.add(project)
        oss_session.commit()

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "scan", "--project", "cli-test-proj6"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 2
        assert "OSS not enabled" in result.output or "oss not enabled" in result.output.lower()

    def test_oss_scan_exits_2_when_project_not_found(self, oss_session: Session) -> None:
        """iw oss scan exits 2 when project does not exist."""

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "scan", "--project", "does-not-exist"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 2


class TestOssStatus:
    def test_oss_status_json_shape(
        self,
        oss_session: Session,
        test_repo: Path,
    ) -> None:
        """iw oss status --json returns the expected contract shape."""
        from orch.db.models import Project

        project = Project(
            id="cli-test-proj7",
            display_name="CLI Test Project 7",
            repo_root=str(test_repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "status", "--project", "cli-test-proj7", "--json"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 0, result.output

        data = json.loads(result.output)
        assert data["project_id"] == "cli-test-proj7"
        assert data["pill_color"] == "gray"
        assert data["exit_code"] is None
        assert data["head_sha"] is None
        assert data["stale"] is False
        assert data["counts"]["must_pass"] == 0
        assert data["counts"]["must_fail"] == 0
        assert data["scan_id"] is None

    def test_oss_status_exits_2_when_project_not_found(self, oss_session: Session) -> None:
        """iw oss status exits 2 when project does not exist."""

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "status", "--project", "does-not-exist", "--json"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 2


class TestOssInstall:
    def test_oss_install_dry_run_shows_status(self) -> None:
        """iw oss install --dry-run lists tool status."""

        def _get_session():
            from orch.db.session import get_session

            return get_session()

        result = CliRunner().invoke(
            cli,
            ["oss", "install", "--dry-run"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 0, result.output
        assert "Tool" in result.output or "Tier" in result.output or "installed" in result.output


class TestOssHelp:
    def test_oss_help_lists_all_subcommands(self) -> None:
        """iw oss --help lists all 7 subcommands."""

        def _get_session():
            from orch.db.session import get_session

            return get_session()

        result = CliRunner().invoke(
            cli,
            ["oss", "--help"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 0, result.output
        subcommands = ["install", "scan", "prepare", "publish", "enable", "disable", "status"]
        for sub in subcommands:
            assert sub in result.output, f"Missing subcommand: {sub}"
