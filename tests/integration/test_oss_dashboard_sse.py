"""Integration tests for OSS dashboard SSE behavior.

Covers SSE lifecycle events, reconnect replay, and heartbeat.
"""

from __future__ import annotations

import asyncio
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
    ProjectOssJobStatus,
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
    base_sha TEXT,
    CONSTRAINT fk_project_oss_job_project FOREIGN KEY (project_id)
        REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_project_oss_job_scan FOREIGN KEY (scan_id)
        REFERENCES oss_scan(id) ON DELETE SET NULL
);
CREATE INDEX ix_project_oss_job_project_created ON project_oss_job (project_id, created_at DESC);
CREATE INDEX ix_project_oss_job_status ON project_oss_job (status);
CREATE UNIQUE INDEX ix_project_oss_job_public_id ON project_oss_job (public_id);

ALTER TABLE projects ADD COLUMN IF NOT EXISTS oss_enabled BOOLEAN NOT NULL DEFAULT false;
"""


@pytest.fixture(scope="session")
def oss_sse_pg_container():
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def oss_sse_engine(oss_sse_pg_container):
    from orch.db.models import (
        FTS_FUNCTION_SQL,
        FTS_TRIGGER_SQL,
        PROJECT_DOCS_FTS_FUNCTION_SQL,
        PROJECT_DOCS_FTS_TRIGGER_SQL,
        Base,
    )

    url = oss_sse_pg_container.get_connection_url().replace(
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
def oss_sse_session_factory(oss_sse_engine):
    return sessionmaker(bind=oss_sse_engine, autocommit=False, autoflush=False)


@pytest.fixture
def oss_sse_connection(oss_sse_engine):
    """Per-test connection with an outer transaction rolled back on teardown."""
    connection = oss_sse_engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


@pytest.fixture
def oss_sse_session(oss_sse_connection) -> Generator[Session, None, None]:
    # join_transaction_mode='create_savepoint' makes session.commit() a SAVEPOINT
    # commit, so data is visible to other sessions bound to the same connection
    # (i.e. the SSE stream's factory sessions) while the outer transaction still
    # rolls back at teardown.
    from sqlalchemy.orm import Session as SASession

    session = SASession(
        bind=oss_sse_connection,
        autocommit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    yield session
    session.close()


@pytest.fixture
def client(
    oss_sse_session: Session,
    oss_sse_connection,
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield oss_sse_session

    # Stream factory yields sessions bound to the SAME connection as the test's
    # session so each stream tick sees the test's committed savepoint data.
    from sqlalchemy.orm import Session as SASession

    def stream_factory() -> Session:
        return SASession(
            bind=oss_sse_connection,
            autocommit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )

    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        app.state.oss_session_factory = stream_factory

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


@pytest.fixture
def proj_enabled(oss_sse_session: Session, tmp_path: Path) -> Project:
    repo = tmp_path / "sse-enabled-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Test\n")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)

    p = Project(
        id="sse-enabled",
        display_name="SSE Test Project",
        repo_root=str(repo),
        config={},
        oss_enabled=True,
    )
    oss_sse_session.add(p)
    oss_sse_session.flush()
    return p


class TestSseRowUpdateEvents:
    def test_stream_emits_row_update_events(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_sse_session: Session,
    ) -> None:
        """CR-00022 AC8: scan SSE emits row-update events during scan."""
        scan = OssScan(
            project_id=proj_enabled.id,
            status=OssScanStatus.running,
            head_sha="abc123",
        )
        oss_sse_session.add(scan)
        oss_sse_session.flush()

        from orch.db.models import OssFinding, OssFindingSeverity, OssFindingStatus

        finding = OssFinding(
            scan_id=scan.id,
            check_id="OSS-CH-01",
            severity=OssFindingSeverity.MUST,
            status=OssFindingStatus.fail,
            domain="community",
            summary="Missing README",
            auto_apply_safe=True,
            auto_fix_available=True,
        )
        oss_sse_session.add(finding)
        oss_sse_session.commit()

        job = ProjectOssJob(
            project_id=proj_enabled.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.complete,
            scan_id=scan.id,
            stdout_tail="",
        )
        oss_sse_session.add(job)
        oss_sse_session.commit()

        resp = client.get(
            f"/project/{proj_enabled.id}/oss/stream/{job.public_id}",
            headers={"Accept": "text/event-stream"},
            timeout=5,
        )
        assert resp.status_code == 200
        content = b"".join(resp.iter_bytes()).decode("utf-8", errors="replace")

        assert "event: row-update" in content, f"Expected row-update event in: {content[:500]}"
        assert "OSS-CH-01" in content
        assert "community" in content
        assert "MUST" in content

    def test_row_update_event_data_shape(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_sse_session: Session,
    ) -> None:
        """CR-00022 AC8: row-update data includes all required fields."""
        scan = OssScan(
            project_id=proj_enabled.id,
            status=OssScanStatus.running,
            head_sha="abc123",
        )
        oss_sse_session.add(scan)
        oss_sse_session.flush()

        from orch.db.models import OssFinding, OssFindingSeverity, OssFindingStatus

        finding = OssFinding(
            scan_id=scan.id,
            check_id="OSS-CH-01",
            severity=OssFindingSeverity.MUST,
            status=OssFindingStatus.fail,
            domain="community",
            summary="Missing README",
            auto_apply_safe=True,
            auto_fix_available=True,
        )
        oss_sse_session.add(finding)
        oss_sse_session.commit()

        job = ProjectOssJob(
            project_id=proj_enabled.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.complete,
            scan_id=scan.id,
            stdout_tail="",
        )
        oss_sse_session.add(job)
        oss_sse_session.commit()

        resp = client.get(
            f"/project/{proj_enabled.id}/oss/stream/{job.public_id}",
            headers={"Accept": "text/event-stream"},
            timeout=5,
        )
        assert resp.status_code == 200
        content = b"".join(resp.iter_bytes()).decode("utf-8", errors="replace")

        import json

        for line in content.split("\n"):
            if line.startswith("data: ") and "OSS-CH-01" in line:
                data = json.loads(line[6:])
                assert "check_id" in data
                assert "domain" in data
                assert "severity" in data
                assert "status" in data
                assert "summary" in data
                assert "auto_apply_safe" in data
                assert "auto_fix_available" in data
                assert "finding_hash" in data
                break

    def test_stream_emits_complete_event_at_end(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_sse_session: Session,
    ) -> None:
        """CR-00022 AC8: complete event still emitted at end of scan."""
        scan = OssScan(
            project_id=proj_enabled.id,
            status=OssScanStatus.complete,
            head_sha="abc123",
            pill_color=OssPillColor.green,
        )
        oss_sse_session.add(scan)
        oss_sse_session.flush()

        job = ProjectOssJob(
            project_id=proj_enabled.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.complete,
            exit_code=0,
            scan_id=scan.id,
            stdout_tail="done",
        )
        oss_sse_session.add(job)
        oss_sse_session.commit()

        resp = client.get(
            f"/project/{proj_enabled.id}/oss/stream/{job.public_id}",
            headers={"Accept": "text/event-stream"},
            timeout=5,
        )
        assert resp.status_code == 200
        content = b"".join(resp.iter_bytes()).decode("utf-8", errors="replace")

        assert "event: complete" in content


class TestSseEmitsStatusProgressCompleteInOrder:
    def test_stream_emits_status_before_complete(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_sse_session: Session,
    ) -> None:
        scan = OssScan(
            project_id=proj_enabled.id,
            status=OssScanStatus.complete,
            head_sha="abc123",
            pill_color=OssPillColor.green,
        )
        oss_sse_session.add(scan)
        oss_sse_session.flush()

        job = ProjectOssJob(
            project_id=proj_enabled.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.complete,
            exit_code=0,
            scan_id=scan.id,
            stdout_tail="scan complete\nall tools passed\n",
        )
        oss_sse_session.add(job)
        oss_sse_session.commit()

        resp = client.get(
            f"/project/{proj_enabled.id}/oss/stream/{job.public_id}",
            headers={"Accept": "text/event-stream"},
            timeout=5,
        )
        assert resp.status_code == 200
        content = b"".join(resp.iter_bytes()).decode("utf-8", errors="replace")

        status_pos = content.find("event: status")
        complete_pos = content.find("event: complete")

        assert status_pos != -1, f"No 'event: status' found in: {content[:500]}"
        assert complete_pos != -1, f"No 'event: complete' found in: {content[:500]}"
        assert status_pos < complete_pos, "status event must come before complete event"

    def test_stream_emits_progress_events_for_stdout_tail(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_sse_session: Session,
    ) -> None:
        # Emitting progress events for an existing stdout_tail is first-iteration
        # behavior in job_event_stream — it happens regardless of status. Use a
        # terminal status so the stream actually finishes within the test and we
        # don't need streaming-with-break plumbing.
        job = ProjectOssJob(
            project_id=proj_enabled.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.complete,
            exit_code=0,
            stdout_tail="line1\nline2\nline3\n",
        )
        oss_sse_session.add(job)
        oss_sse_session.commit()

        resp = client.get(
            f"/project/{proj_enabled.id}/oss/stream/{job.public_id}",
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        content = resp.content.decode("utf-8", errors="replace")

        assert "event: progress" in content
        assert "line1" in content
        assert "line2" in content
        assert "line3" in content


class TestSseReconnectReplaysTail:
    def test_stream_replay_on_reconnect_precedes_live_events(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_sse_session: Session,
    ) -> None:
        # First-iteration replay is status-independent. Use terminal status so
        # the stream finishes cleanly each time and we can exercise the reconnect
        # path synchronously. Intent: every fresh connection re-emits the
        # current stdout_tail as progress events.
        job = ProjectOssJob(
            project_id=proj_enabled.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.complete,
            exit_code=0,
            stdout_tail="tail_line1\ntail_line2\n",
        )
        oss_sse_session.add(job)
        oss_sse_session.commit()

        url = f"/project/{proj_enabled.id}/oss/stream/{job.public_id}"
        # First connection
        resp1 = client.get(url, headers={"Accept": "text/event-stream"})
        assert resp1.status_code == 200
        content1 = resp1.content.decode("utf-8", errors="replace")

        # Second connection (reconnect) — tail is re-emitted from scratch
        resp2 = client.get(url, headers={"Accept": "text/event-stream"})
        assert resp2.status_code == 200
        content2 = resp2.content.decode("utf-8", errors="replace")

        assert "tail_line1" in content1
        assert "event: progress" in content1
        assert "tail_line1" in content2
        assert "event: progress" in content2

    def test_reconnect_replays_before_live_stream(
        self,
        client: TestClient,
        proj_enabled: Project,
        oss_sse_session: Session,
    ) -> None:
        """Invariant #4: SSE stream idempotent — reconnect replays tail.

        First-iteration replay is status-independent, so terminal status keeps
        the test synchronous while still exercising the replay code path.
        """
        job = ProjectOssJob(
            project_id=proj_enabled.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.complete,
            exit_code=0,
            stdout_tail="replay_line_a\nreplay_line_b\n",
        )
        oss_sse_session.add(job)
        oss_sse_session.commit()

        resp = client.get(
            f"/project/{proj_enabled.id}/oss/stream/{job.public_id}",
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        content = resp.content.decode("utf-8", errors="replace")

        # The stream must start with replayed tail events before any live-only content
        lines = content.split("\n")
        replay_indices = [i for i, line in enumerate(lines) if "replay_line" in line]
        assert len(replay_indices) >= 2, f"Expected replay lines in stream: {content[:500]}"


class TestSseHeartbeatEvery20s:
    @pytest.mark.asyncio
    async def test_heartbeat_emitted_at_20s_interval(
        self,
        proj_enabled: Project,
        oss_sse_session: Session,
        oss_sse_connection,
    ) -> None:
        from sqlalchemy.orm import Session as SASession

        from dashboard.services.oss_service import job_event_stream

        job = ProjectOssJob(
            project_id=proj_enabled.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.running,
        )
        oss_sse_session.add(job)
        oss_sse_session.commit()

        # Factory must yield a NEW session each call: job_event_stream closes
        # the session after each poll. Bind to the test's connection with
        # savepoint mode so rows committed by the test are visible.
        def factory():
            return SASession(
                bind=oss_sse_connection,
                autocommit=False,
                autoflush=False,
                join_transaction_mode="create_savepoint",
            )

        events = []
        heartbeat_seen = False

        async def collect():
            nonlocal heartbeat_seen
            async for msg in job_event_stream(factory, job.id, heartbeat_interval=0.1):
                events.append(msg)
                if "heartbeat" in msg or ": heartbeat" in msg:
                    heartbeat_seen = True
                # Exit as soon as we've observed at least one heartbeat
                # alongside the status event (running jobs never terminate).
                if heartbeat_seen and len(events) >= 3:
                    break

        await asyncio.wait_for(collect(), timeout=5)

        # A running job emits: status(running) + heartbeat(s) forever.
        assert len(events) > 0
        assert heartbeat_seen, f"Expected heartbeat in events: {events[:10]}"

    @pytest.mark.asyncio
    async def test_heartbeat_comment_format(
        self,
        proj_enabled: Project,
        oss_sse_session: Session,
    ) -> None:
        from dashboard.services.oss_service import job_event_stream

        job = ProjectOssJob(
            project_id=proj_enabled.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.running,
            stdout_tail="",
        )
        oss_sse_session.add(job)
        oss_sse_session.commit()

        def factory():
            return oss_sse_session

        events = []
        async for msg in job_event_stream(factory, job.id, heartbeat_interval=0.5):
            events.append(msg)
            if len(events) >= 5:
                break

        # Heartbeat format: ": heartbeat <iso_timestamp>\n\n"
        heartbeat_events = [e for e in events if ": heartbeat" in e or "heartbeat" in e]
        assert len(heartbeat_events) >= 1, f"Expected heartbeat in events: {events}"
