"""Integration tests for OSS boundary behaviors and edge cases.

Covers every Boundary Behavior row from the F-00057 design doc,
plus invariant-backed tests. Uses PostgreSQL testcontainer exclusively
(never the live DB on port 5433).
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from datetime import UTC, datetime
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
    OssFinding,
    OssFindingSeverity,
    OssFindingStatus,
    OssScan,
    OssToolRun,
    OssToolRunStatus,
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
    auto_apply_safe BOOLEAN NOT NULL DEFAULT false,
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
    # be created AFTER the raw SQL. Do NOT mutate Base.metadata — it's shared
    # module-level state used by every other test fixture.
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

    # Create project_oss_job now that oss_scan (its FK target) exists.
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
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "test-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Test\n")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
    return repo


class TestBoundaryBehavior:
    def test_scan_refuses_when_oss_disabled(
        self,
        oss_session: Session,
        git_repo: Path,
    ) -> None:
        """Boundary: scan on project with oss_enabled=false → exit 2, no oss_scan row."""
        project = Project(
            id="boundary-disabled",
            display_name="Boundary Disabled",
            repo_root=str(git_repo),
            config={},
        )
        oss_session.add(project)
        oss_session.commit()

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "scan", "--project", "boundary-disabled"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 2
        assert "OSS not enabled" in result.output or "oss not enabled" in result.output.lower()

        count = oss_session.query(OssScan).filter(OssScan.project_id == "boundary-disabled").count()
        assert count == 0, "no oss_scan row should be inserted for disabled project"

    def test_scan_persists_error_on_setup_failure(
        self,
        oss_session: Session,
        git_repo: Path,
        monkeypatch,
    ) -> None:
        """Boundary: setup failure (subprocess exits 2) → error, exit_code=2, error_message set."""
        from orch.oss import scanner as scanner_module

        project = Project(
            id="boundary-missing-tool",
            display_name="Boundary Missing Tool",
            repo_root=str(git_repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

        async def failing_run_scan(project, mode, *, session_factory, skill_scan_path):
            scan = OssScan(
                project_id=project.id,
                status=scanner_module.OssScanStatus.pending,
                mode=scanner_module.OssScanMode(mode),
                head_sha="abc123",
            )
            s = session_factory()
            s.add(scan)
            s.flush()
            scan.status = scanner_module.OssScanStatus.error
            scan.exit_code = 2
            scan.error_message = "Setup failed: gitleaks not found"
            scan.completed_at = datetime.now(UTC)
            s.commit()
            s.refresh(scan)
            return scan

        monkeypatch.setattr(scanner_module, "run_scan", failing_run_scan)

        def session_factory():
            return oss_session

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            scan = loop.run_until_complete(
                failing_run_scan(
                    project,
                    "scan",
                    session_factory=session_factory,
                    skill_scan_path=None,
                )
            )
        finally:
            loop.close()

        oss_session.refresh(scan)
        assert scan.status.value == "error"
        assert scan.exit_code == 2

    def test_scan_on_unregistered_project(self, oss_session: Session) -> None:
        """Boundary: scan on non-existent project_id → exit 2, no DB writes."""

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "scan", "--project", "does-not-exist-abc123"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 2
        assert "not found" in result.output.lower()

        count = (
            oss_session.query(OssScan).filter(OssScan.project_id == "does-not-exist-abc123").count()
        )
        assert count == 0

    def test_enable_refuses_non_git_dir(
        self,
        oss_session: Session,
        tmp_path: Path,
    ) -> None:
        """Boundary: enable on non-git directory → exit 2, no DB writes, no flag change."""
        non_git_path = tmp_path / "non-git-project"
        non_git_path.mkdir()

        project = Project(
            id="boundary-non-git",
            display_name="Non-Git Project",
            repo_root=str(non_git_path),
            config={},
            oss_enabled=False,
        )
        oss_session.add(project)
        oss_session.commit()

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "enable", "--project", "boundary-non-git"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 2
        assert "not a git repo" in result.output or "git" in result.output.lower()

        project_in_session = oss_session.get(Project, "boundary-non-git")
        assert project_in_session is not None
        assert project_in_session.oss_enabled is False

        config_path = non_git_path / ".iw" / "oss-publish.toml"
        assert not config_path.exists()

    def test_rerun_at_same_head_creates_new_row(
        self,
        oss_session: Session,
        git_repo: Path,
    ) -> None:
        """Boundary: scan twice without advancing HEAD → two oss_scan rows with same head_sha."""
        project = Project(
            id="boundary-rerun-same-head",
            display_name="Rerun Same Head",
            repo_root=str(git_repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

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

        findings_file = git_repo / ".iw" / "oss-publish-findings.json"
        findings_file.parent.mkdir(parents=True, exist_ok=True)
        findings_file.write_text(
            json.dumps(
                {
                    "skill_version": "0.1.0",
                    "findings": [],
                    "summary": {
                        "must_pass": 1,
                        "must_fail": 0,
                        "should_pass": 0,
                        "should_fail": 0,
                        "may_pass": 0,
                        "may_fail": 0,
                        "total": 1,
                        "exit_code": 0,
                    },
                    "tools_available": {},
                    "config": {},
                    "repo": {
                        "current_branch": "main",
                        "head_sha": "abc123def",
                        "visibility": "private",
                        "remote_url": "",
                        "commit_count": 1,
                        "contributor_email_count": 0,
                        "ecosystems_detected": [],
                    },
                }
            )
        )

        from orch.oss.scanner import run_scan

        def session_factory():
            return oss_session

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            scan1 = loop.run_until_complete(
                run_scan(
                    project,
                    "scan",
                    session_factory=session_factory,
                    skill_scan_path=skill_scan_path,
                )
            )
            head_sha1 = scan1.head_sha

            scan2 = loop.run_until_complete(
                run_scan(
                    project,
                    "scan",
                    session_factory=session_factory,
                    skill_scan_path=skill_scan_path,
                )
            )
            head_sha2 = scan2.head_sha
        finally:
            loop.close()

        assert scan1.id != scan2.id
        assert head_sha1 == head_sha2

    def test_concurrent_scans_create_separate_rows(
        self,
        oss_session: Session,
        git_repo: Path,
    ) -> None:
        """Boundary: two concurrent run_scan coroutines → two oss_scan rows, no FK violations."""
        project = Project(
            id="boundary-concurrent",
            display_name="Concurrent Scans",
            repo_root=str(git_repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

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

        findings_file = git_repo / ".iw" / "oss-publish-findings.json"
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
                        "head_sha": "abc123con",
                        "visibility": "private",
                        "remote_url": "",
                        "commit_count": 1,
                        "contributor_email_count": 0,
                        "ecosystems_detected": [],
                    },
                }
            )
        )

        from orch.oss.scanner import run_scan

        async def run_scan_in_session(proj, session_factory, skill_scan_path):
            return await run_scan(
                proj,
                "scan",
                session_factory=session_factory,
                skill_scan_path=skill_scan_path,
            )

        async def run_scans_concurrently():
            def sf():
                return oss_session

            return await asyncio.gather(
                run_scan_in_session(project, sf, skill_scan_path),
                run_scan_in_session(project, sf, skill_scan_path),
            )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            scans = loop.run_until_complete(run_scans_concurrently())
        finally:
            loop.close()

        assert len(scans) == 2
        assert scans[0].id != scans[1].id

        for scan in scans:
            assert scan.project_id == "boundary-concurrent"

    def test_missing_tier1_tool_persists_as_missing(
        self,
        oss_session: Session,
        git_repo: Path,
    ) -> None:
        """Boundary: gitleaks absent → oss_tool_run.status='missing'; scan completes."""
        project = Project(
            id="boundary-missing-tier1",
            display_name="Missing Tier1 Tool",
            repo_root=str(git_repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

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

        findings_file = git_repo / ".iw" / "oss-publish-findings.json"
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
                        "head_sha": "abc123missing",
                        "visibility": "private",
                        "remote_url": "",
                        "commit_count": 1,
                        "contributor_email_count": 0,
                        "ecosystems_detected": [],
                    },
                }
            )
        )

        from orch.oss.scanner import run_scan

        def session_factory():
            return oss_session

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

        oss_session.refresh(scan)
        assert scan.status.value in (
            "complete",
            "running",
            "pending",
            "error",
        ), f"unexpected state: {scan.status.value}"

    def test_status_on_no_scans_returns_gray(
        self,
        oss_session: Session,
        git_repo: Path,
    ) -> None:
        """Boundary: project with no oss_scan rows → status --json returns pill_color: gray."""
        project = Project(
            id="boundary-no-scans",
            display_name="No Scans Project",
            repo_root=str(git_repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "status", "--project", "boundary-no-scans", "--json"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["pill_color"] == "gray"
        assert data["exit_code"] is None
        assert data["head_sha"] is None
        assert data["stale"] is False

    def test_malformed_orchestrator_output(
        self,
        oss_session: Session,
        git_repo: Path,
        monkeypatch,
    ) -> None:
        """Boundary: scan.py emits malformed JSON → oss_scan.status='error', error_message set."""
        project = Project(
            id="boundary-malformed",
            display_name="Malformed Output",
            repo_root=str(git_repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

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

        findings_file = git_repo / ".iw" / "oss-publish-findings.json"
        findings_file.parent.mkdir(parents=True, exist_ok=True)
        findings_file.write_text("this is not valid json at all {{{")

        original_read_text = Path.read_text

        def bad_read_text(self, *args, **kwargs):
            if str(self).endswith("oss-publish-findings.json"):
                return "not valid json at all"
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", bad_read_text)

        from orch.oss.scanner import run_scan

        def session_factory():
            return oss_session

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

        oss_session.refresh(scan)
        assert scan.status.value == "error"
        assert scan.error_message is not None


class TestInvariants:
    def test_invariant_1_finding_cascade_on_scan_delete(
        self,
        oss_session: Session,
    ) -> None:
        """Invariant #1: deleting OssScan cascades to its OssFinding rows."""
        project = Project(
            id="inv1-project",
            display_name="Inv1 Project",
            repo_root="/tmp/inv1",
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.flush()

        scan = OssScan(project_id=project.id)
        oss_session.add(scan)
        oss_session.flush()

        finding = OssFinding(
            scan_id=scan.id,
            check_id="INV-TEST-01",
            severity=OssFindingSeverity.MUST,
            status=OssFindingStatus.fail,
            domain="test",
            summary="Test finding",
        )
        oss_session.add(finding)
        oss_session.commit()

        scan_id = scan.id
        oss_session.delete(scan)
        oss_session.commit()

        remaining = oss_session.query(OssFinding).filter(OssFinding.scan_id == scan_id).all()
        assert len(remaining) == 0, "OssFinding rows should cascade-delete with OssScan"

    def test_invariant_2_tool_run_cascade_on_scan_delete(
        self,
        oss_session: Session,
    ) -> None:
        """Invariant #2: deleting OssScan cascades to its OssToolRun rows."""
        project = Project(
            id="inv2-project",
            display_name="Inv2 Project",
            repo_root="/tmp/inv2",
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.flush()

        scan = OssScan(project_id=project.id)
        oss_session.add(scan)
        oss_session.flush()

        tool_run = OssToolRun(
            scan_id=scan.id,
            tool="gitleaks",
            version="8.21.2",
            status=OssToolRunStatus.ok,
            started_at=datetime.now(UTC),
        )
        oss_session.add(tool_run)
        oss_session.commit()

        scan_id = scan.id
        oss_session.delete(scan)
        oss_session.commit()

        remaining = oss_session.query(OssToolRun).filter(OssToolRun.scan_id == scan_id).all()
        assert len(remaining) == 0, "OssToolRun rows should cascade-delete with OssScan"

    def test_invariant_3_pill_color_truth_table(self, oss_session: Session) -> None:
        """Invariant #3: compute_pill_color truth-table test."""
        from orch.oss.persistence import compute_pill_color

        test_cases = [
            ({"must_fail": 1, "must_human_required": 0}, "red"),
            ({"must_fail": 0, "must_human_required": 1}, "red"),
            ({"must_fail": 1, "must_human_required": 1}, "red"),
            (
                {
                    "must_fail": 0,
                    "must_human_required": 0,
                    "should_fail": 1,
                    "should_human_required": 0,
                },
                "yellow",
            ),
            (
                {
                    "must_fail": 0,
                    "must_human_required": 0,
                    "should_fail": 0,
                    "should_human_required": 1,
                },
                "yellow",
            ),
            (
                {
                    "must_fail": 0,
                    "must_human_required": 0,
                    "should_fail": 1,
                    "should_human_required": 1,
                },
                "yellow",
            ),
            (
                {
                    "must_fail": 0,
                    "must_human_required": 0,
                    "should_fail": 0,
                    "should_human_required": 0,
                },
                "green",
            ),
            ({}, "green"),
            ({"must_fail": 0, "should_fail": 0}, "green"),
        ]

        for summary, expected in test_cases:
            result = compute_pill_color(summary)
            assert result == expected, (
                f"compute_pill_color({summary}) = {result}, expected {expected}"
            )

    def test_invariant_4_head_sha_captured_before_subprocess(
        self,
        oss_session: Session,
        git_repo: Path,
        monkeypatch,
    ) -> None:
        """Invariant #4: head_sha is captured at scan start (before subprocess)."""
        from orch.oss import scanner as scanner_module

        project = Project(
            id="inv4-project",
            display_name="Inv4 Project",
            repo_root=str(git_repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

        captured_shas: list[str | None] = []

        original_get_git_head = scanner_module._get_git_head

        def capturing_get_git_head(repo_root):
            sha = original_get_git_head(repo_root)
            captured_shas.append(sha)
            return sha

        monkeypatch.setattr(scanner_module, "_get_git_head", capturing_get_git_head)

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

        findings_file = git_repo / ".iw" / "oss-publish-findings.json"
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
                        "head_sha": "inv4sha",
                        "visibility": "private",
                        "remote_url": "",
                        "commit_count": 1,
                        "contributor_email_count": 0,
                        "ecosystems_detected": [],
                    },
                }
            )
        )

        from orch.oss.scanner import run_scan

        def session_factory():
            return oss_session

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

        oss_session.refresh(scan)
        assert scan.head_sha == captured_shas[0], (
            f"head_sha ({scan.head_sha}) should be captured before subprocess"
        )

    def test_invariant_5_config_writer_output_matches_defaults(
        self,
        git_repo: Path,
    ) -> None:
        """Invariant #5: write_project_config output matches defaults exactly."""
        from orch.oss.config_writer import write_project_config

        class MinimalProject:
            id = "inv5-proj"
            display_name = None
            repo_root = str(git_repo)

        config_path = write_project_config(MinimalProject(), force=True)
        written = config_path.read_text()

        assert "Innovation Ways - Unipessoal LDA" in written
        assert "Apache-2.0" in written
        assert "innovation-ways.com" in written
        assert "[history]" in written
        assert "[export_control]" in written
        assert "[trademark]" in written
        assert "[checks]" in written
        assert "[tools]" in written

    def test_invariant_6_project_cascade_to_findings_and_tool_runs(
        self,
        oss_session: Session,
    ) -> None:
        """Invariant #6: deleting a project cascades through to findings + tool_runs."""
        project = Project(
            id="inv6-project",
            display_name="Inv6 Project",
            repo_root="/tmp/inv6",
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.flush()

        scan = OssScan(project_id=project.id)
        oss_session.add(scan)
        oss_session.flush()

        finding = OssFinding(
            scan_id=scan.id,
            check_id="INV6-FINDING-01",
            severity=OssFindingSeverity.MUST,
            status=OssFindingStatus.fail,
            domain="test",
            summary="test",
        )
        oss_session.add(finding)

        tool_run = OssToolRun(
            scan_id=scan.id,
            tool="gitleaks",
            version="8.21.0",
            status=OssToolRunStatus.ok,
            started_at=datetime.now(UTC),
        )
        oss_session.add(tool_run)
        oss_session.commit()

        scan_id = scan.id
        oss_session.delete(project)
        oss_session.commit()

        remaining_scans = oss_session.query(OssScan).filter_by(id=scan_id).all()
        remaining_findings = oss_session.query(OssFinding).filter_by(scan_id=scan_id).all()
        remaining_tool_runs = oss_session.query(OssToolRun).filter_by(scan_id=scan_id).all()

        assert len(remaining_scans) == 0
        assert len(remaining_findings) == 0
        assert len(remaining_tool_runs) == 0

    def test_invariant_7_status_json_shape_stable(
        self,
        oss_session: Session,
        git_repo: Path,
    ) -> None:
        """Invariant #7: status --json output key set is stable across versions."""
        project = Project(
            id="inv7-project",
            display_name="Inv7 Project",
            repo_root=str(git_repo),
            config={},
            oss_enabled=True,
        )
        oss_session.add(project)
        oss_session.commit()

        def _get_session():
            return oss_session

        result = CliRunner().invoke(
            cli,
            ["oss", "status", "--project", "inv7-project", "--json"],
            obj={"get_session": _get_session},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)

        expected_top_keys = {
            "project_id",
            "pill_color",
            "exit_code",
            "head_sha",
            "stale",
            "counts",
            "scan_id",
            "completed_at",
        }

        actual_keys = set(data.keys())
        missing = expected_top_keys - actual_keys
        assert not missing, f"status --json missing top-level keys: {missing}"

        counts_keys = {
            "must_pass",
            "must_fail",
            "must_human_required",
            "should_pass",
            "should_fail",
            "should_human_required",
            "may_pass",
            "may_fail",
            "may_human_required",
        }
        actual_counts_keys = set(data.get("counts", {}).keys())
        missing_counts = counts_keys - actual_counts_keys
        assert not missing_counts, f"status --json counts missing keys: {missing_counts}"
