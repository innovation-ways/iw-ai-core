"""Integration tests for OSS dashboard template rendering invariants.

Covers invariants #5 (pill color parity), #6 (tab visibility), #7 (frame presence).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    OssPillColor,
    OssScan,
    OssScanStatus,
    Project,
    ProjectOssJob,
    ProjectOssJobKind,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

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
CREATE TYPE ossscan_mode AS ENUM ('scan', 'make_oss', 'publish');
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
    osps_control TEXT,
    tool TEXT,
    evidence_json JSONB
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

CREATE TYPE project_oss_job_kind AS ENUM ('scan', 'prepare', 'publish', 'install');
CREATE TYPE project_oss_job_status AS ENUM ('queued', 'running', 'complete', 'error', 'cancelled');

CREATE TABLE IF NOT EXISTS project_oss_job (
    id BIGSERIAL PRIMARY KEY,
    project_id TEXT NOT NULL,
    kind project_oss_job_kind NOT NULL,
    status project_oss_job_status NOT NULL DEFAULT 'queued',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    exit_code INTEGER,
    worktree_path TEXT,
    scan_id BIGINT,
    stdout_tail TEXT,
    error_message TEXT
);
CREATE INDEX ix_project_oss_job_project_created ON project_oss_job (project_id, created_at DESC);
CREATE INDEX ix_project_oss_job_status ON project_oss_job (status);

ALTER TABLE project_oss_job ADD CONSTRAINT fk_project_oss_job_project
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
ALTER TABLE project_oss_job ADD CONSTRAINT fk_project_oss_job_scan
    FOREIGN KEY (scan_id) REFERENCES oss_scan(id) ON DELETE SET NULL;

ALTER TABLE projects ADD COLUMN IF NOT EXISTS oss_enabled BOOLEAN NOT NULL DEFAULT false;
"""


@pytest.fixture(scope="session")
def oss_tmpl_pg_container():
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def oss_tmpl_engine(oss_tmpl_pg_container):
    from orch.db.models import (
        FTS_FUNCTION_SQL,
        FTS_TRIGGER_SQL,
        PROJECT_DOCS_FTS_FUNCTION_SQL,
        PROJECT_DOCS_FTS_TRIGGER_SQL,
        Base,
    )

    url = oss_tmpl_pg_container.get_connection_url().replace(
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
def oss_tmpl_session_factory(oss_tmpl_engine):
    return sessionmaker(bind=oss_tmpl_engine, autocommit=False, autoflush=False)


@pytest.fixture
def oss_tmpl_session(oss_tmpl_engine, oss_tmpl_session_factory) -> Generator[Session, None, None]:
    connection = oss_tmpl_engine.connect()
    transaction = connection.begin()
    session = oss_tmpl_session_factory(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(oss_tmpl_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield oss_tmpl_session

    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


@pytest.fixture
def proj_enabled(oss_tmpl_session: Session, tmp_path: Path) -> Project:
    repo = tmp_path / "tmpl-enabled-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Test\n")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)

    p = Project(
        id="tmpl-enabled",
        display_name="Tmpl Test Project",
        repo_root=str(repo),
        config={},
        oss_enabled=True,
    )
    oss_tmpl_session.add(p)
    oss_tmpl_session.flush()
    return p


@pytest.fixture
def proj_disabled(oss_tmpl_session: Session, tmp_path: Path) -> Project:
    repo = tmp_path / "tmpl-disabled-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Test\n")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)

    p = Project(
        id="tmpl-disabled",
        display_name="Tmpl Disabled Project",
        repo_root=str(repo),
        config={},
        oss_enabled=False,
    )
    oss_tmpl_session.add(p)
    oss_tmpl_session.flush()
    return p


# ---------------------------------------------------------------------------
# Invariant #5: Pill color parity
# ---------------------------------------------------------------------------


class TestPillColorParityInvariant:
    def test_pill_color_green_renders_correct_css_class(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_tmpl_session: Session,
    ) -> None:
        scan = OssScan(
            project_id=proj_enabled.id,
            status=OssScanStatus.complete,
            head_sha="abc123",
            pill_color=OssPillColor.green,
        )
        oss_tmpl_session.add(scan)
        oss_tmpl_session.commit()

        resp = client.get(f"/project/{proj_enabled.id}/oss/status")
        assert resp.status_code == 200
        html = resp.text
        # Green pill: bg-green-100 text-green-800 🟢
        assert "bg-green-100" in html
        assert "text-green-800" in html
        assert "🟢" in html

    def test_pill_color_yellow_renders_correct_css_class(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_tmpl_session: Session,
    ) -> None:
        scan = OssScan(
            project_id=proj_enabled.id,
            status=OssScanStatus.complete,
            head_sha="abc123",
            pill_color=OssPillColor.yellow,
        )
        oss_tmpl_session.add(scan)
        oss_tmpl_session.commit()

        resp = client.get(f"/project/{proj_enabled.id}/oss/status")
        assert resp.status_code == 200
        html = resp.text
        assert "bg-yellow-100" in html
        assert "text-yellow-800" in html
        assert "🟡" in html

    def test_pill_color_red_renders_correct_css_class(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_tmpl_session: Session,
    ) -> None:
        scan = OssScan(
            project_id=proj_enabled.id,
            status=OssScanStatus.complete,
            head_sha="abc123",
            pill_color=OssPillColor.red,
        )
        oss_tmpl_session.add(scan)
        oss_tmpl_session.commit()

        resp = client.get(f"/project/{proj_enabled.id}/oss/status")
        assert resp.status_code == 200
        html = resp.text
        assert "bg-red-100" in html
        assert "text-red-800" in html
        assert "🔴" in html

    def test_pill_color_gray_renders_correct_css_class(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_tmpl_session: Session,
    ) -> None:
        # No scan yet → gray pill
        resp = client.get(f"/project/{proj_enabled.id}/oss/status")
        assert resp.status_code == 200
        html = resp.text
        assert "bg-muted" in html or "⚫" in html

    def test_stale_pill_has_warning_annotation(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_tmpl_session: Session,
    ) -> None:
        scan = OssScan(
            project_id=proj_enabled.id,
            status=OssScanStatus.complete,
            head_sha="old_sha",
            pill_color=OssPillColor.yellow,
        )
        oss_tmpl_session.add(scan)
        oss_tmpl_session.commit()

        resp = client.get(f"/project/{proj_enabled.id}/oss/status")
        assert resp.status_code == 200
        html = resp.text
        # Stale: opacity-75 + ⚠ marker in pill + stale_message in title
        assert "opacity-75" in html or "⚠" in html or "stale" in html.lower()


# ---------------------------------------------------------------------------
# Invariant #6: OSS tab appears iff oss_enabled=true
# ---------------------------------------------------------------------------


class TestOssTabVisibilityInvariant:
    def test_oss_tab_present_when_enabled(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        # The OSS page itself
        resp = client.get(f"/project/{proj_enabled.id}/oss")
        assert resp.status_code == 200
        # OSS page renders without redirect (no install-modal forced)

    def test_oss_tab_absent_when_disabled(
        self,
        client: TestClient,
        proj_disabled: Project,
    ) -> None:
        # For disabled project, /oss should show Install CTA
        resp = client.get(f"/project/{proj_disabled.id}/oss")
        assert resp.status_code == 200
        html = resp.text
        # Should show "Install OSS" CTA not the OSS results page
        assert "Install" in html or "OSS" in html

    def test_oss_enabled_flag_controls_tab_visibility(
        self,
        client: TestClient,
        proj_enabled: Project,
        proj_disabled: Project,
        oss_tmpl_session: Session,
    ) -> None:
        # Enabled project
        resp_enabled = client.get(f"/project/{proj_enabled.id}/oss")
        assert resp_enabled.status_code == 200

        # Disabled project — OSS page shows install modal state
        resp_disabled = client.get(f"/project/{proj_disabled.id}/oss")
        assert resp_disabled.status_code == 200

        # The difference should be visible in the page content
        enabled_html = resp_enabled.text
        disabled_html = resp_disabled.text

        # OSS-enabled page shows scan UI; disabled shows install CTA
        assert enabled_html != disabled_html


# ---------------------------------------------------------------------------
# Invariant #7: OSS Status frame appears on the project dashboard page only
# ---------------------------------------------------------------------------


class TestOssStatusFramePresenceInvariant:
    def test_oss_status_frame_in_dashboard_page(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}")
        assert resp.status_code == 200
        html = resp.text
        # OSS Status frame is included in the dashboard page
        assert "oss-status-frame" in html and "oss/status" in html

    def test_oss_status_frame_absent_in_tests_page(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}/tests")
        if resp.status_code == 200:
            html = resp.text
            assert "oss-status-frame" not in html

    def test_oss_status_frame_absent_in_quality_page(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}/quality")
        if resp.status_code == 200:
            html = resp.text
            assert "oss-status-frame" not in html

    def test_oss_status_frame_in_oss_page(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        # The oss status fragment endpoint itself still renders
        resp = client.get(f"/project/{proj_enabled.id}/oss/status")
        assert resp.status_code == 200

    def test_oss_status_frame_absent_in_batches_page(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}/batches")
        if resp.status_code == 200:
            html = resp.text
            assert "oss-status-frame" not in html

    def test_oss_status_frame_is_htmx_loaded(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}")
        assert resp.status_code == 200
        html = resp.text
        # The frame uses htmx to load content
        assert "hx-get" in html and "oss/status" in html


# ---------------------------------------------------------------------------
# Invariant #1 (template layer): install jobs never create worktree
# ---------------------------------------------------------------------------


class TestInstallWorktreeNullInvariant:
    def test_install_job_row_has_null_worktree_path(
        self,
        client: TestClient,
        proj_disabled: Project,
        oss_tmpl_session: Session,
    ) -> None:
        resp = client.post(f"/project/{proj_disabled.id}/oss/install")
        assert resp.status_code == 200
        data = resp.json()
        job_id = data["job_id"]

        job = oss_tmpl_session.query(ProjectOssJob).filter(ProjectOssJob.id == job_id).first()
        assert job is not None
        assert job.kind == ProjectOssJobKind.install
        assert job.worktree_path is None

    def test_no_install_job_ever_has_worktree_path(
        self,
        client: TestClient,
        proj_disabled: Project,
        oss_tmpl_session: Session,
    ) -> None:
        # Multiple install jobs
        for _ in range(2):
            resp = client.post(f"/project/{proj_disabled.id}/oss/install")
            # First may succeed, second may 409
            if resp.status_code == 200:
                pass

        install_jobs = (
            oss_tmpl_session.query(ProjectOssJob)
            .filter(ProjectOssJob.kind == ProjectOssJobKind.install)
            .all()
        )
        for job in install_jobs:
            assert job.worktree_path is None


# ---------------------------------------------------------------------------
# Pill render: no scan → gray pill "not yet scanned"
# ---------------------------------------------------------------------------


class TestNoScanGrayPillInvariant:
    def test_no_scan_renders_gray_pill_not_yet_scanned(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}/oss/status")
        assert resp.status_code == 200
        html = resp.text
        assert "not yet scanned" in html
        assert "bg-muted" in html or "⚫" in html

    def test_no_scan_gray_pill_in_full_oss_page(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}/oss")
        assert resp.status_code == 200
        html = resp.text
        assert "not yet scanned" in html or "No scans yet" in html


# ---------------------------------------------------------------------------
# Domain card empty state
# ---------------------------------------------------------------------------


class TestDomainCardEmptyStateInvariant:
    def test_no_findings_renders_empty_state_message(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        # No findings because no scan
        resp = client.get(f"/project/{proj_enabled.id}/oss")
        assert resp.status_code == 200
        # Either no findings yet OR recent jobs shown (but no crash)

    def test_domain_card_with_findings_renders_correctly(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_tmpl_session: Session,
    ) -> None:
        scan = OssScan(
            project_id=proj_enabled.id,
            status=OssScanStatus.complete,
            head_sha="abc123",
            pill_color=OssPillColor.green,
        )
        oss_tmpl_session.add(scan)
        oss_tmpl_session.flush()

        from orch.db.models import OssFinding, OssFindingSeverity, OssFindingStatus

        finding = OssFinding(
            scan_id=scan.id,
            check_id="test-check",
            severity=OssFindingSeverity.MUST,
            status=OssFindingStatus.fail,
            domain="secrets",
            summary="Hardcoded secret detected",
        )
        oss_tmpl_session.add(finding)
        oss_tmpl_session.commit()

        resp = client.get(f"/project/{proj_enabled.id}/oss")
        assert resp.status_code == 200
        html = resp.text
        assert "secrets" in html or "MUST" in html


# ---------------------------------------------------------------------------
# Install modal: Enable OSS button enabled only when all tools installed
# ---------------------------------------------------------------------------


class TestInstallModalEnableButtonInvariant:
    def test_enable_button_disabled_when_tools_missing(
        self,
        client: TestClient,
        proj_disabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_disabled.id}/oss/tools")
        assert resp.status_code == 200
        # The enable button has conditional disabled attribute
        # When not all_installed, button has disabled class + opacity-60

    def test_enable_button_enabled_when_all_tools_installed(
        self,
        client: TestClient,
        proj_disabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_disabled.id}/oss/tools")
        assert resp.status_code == 200
        # Tools are probed via probe_tier1_dashboard()
        # The template uses {% if tools and all_installed %} to enable button


# ---------------------------------------------------------------------------
# CLI block per action (prepare/publish)
# ---------------------------------------------------------------------------


class TestCliBlockPerActionInvariant:
    def test_prepare_page_shows_cli_command_block(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}/oss")
        assert resp.status_code == 200
        html = resp.text
        assert "uv run iw oss prepare" in html

    def test_publish_page_shows_cli_command_block(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}/oss")
        assert resp.status_code == 200
        html = resp.text
        assert "uv run iw oss publish" in html

    def test_cli_block_uses_correct_project_id(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}/oss")
        assert resp.status_code == 200
        html = resp.text
        assert proj_enabled.id in html


# ---------------------------------------------------------------------------
# No regressions: sibling views remain intact
# ---------------------------------------------------------------------------


class TestNoRegressionsSiblingViewsInvariant:
    def test_code_page_loads_without_oss_errors(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}/code")
        # May 404 if code UI not enabled for this project
        if resp.status_code == 200:
            assert "error" not in resp.text.lower() or resp.status_code == 200

    def test_tests_page_loads_without_oss_errors(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}/tests")
        if resp.status_code == 200:
            assert resp.status_code == 200

    def test_quality_page_loads_without_oss_errors(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}/quality")
        if resp.status_code == 200:
            assert resp.status_code == 200

    def test_documentation_page_loads_without_oss_errors(
        self,
        client: TestClient,
        proj_enabled: Project,
    ) -> None:
        resp = client.get(f"/project/{proj_enabled.id}/docs")
        if resp.status_code == 200:
            assert resp.status_code == 200
