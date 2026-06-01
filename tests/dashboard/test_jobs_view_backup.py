"""Dashboard render test: backup jobs appear in the unified Jobs view (AC6).

Seeds a single DbBackupJob and asserts the rendered Jobs page contains *that
specific* backup row — its id, its "DB backup — manual (…)" title, the
``db_backup`` job-type cell, and the normalised ``completed`` status that a
``success`` DbBackupJob maps to. Shape-only checks (``"jobs" in html``) are
deliberately avoided (I003 lesson).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import DbBackupJob, DbBackupStatus, DbBackupType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """TestClient that overrides get_db to use the test db_session."""
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


def _seed_backup_job(db_session: Session) -> DbBackupJob:
    now = datetime(2026, 6, 1, 3, 0, tzinfo=UTC)
    job = DbBackupJob(
        id="backup-job-abc123",
        backup_type=DbBackupType.manual,
        label="pre-migration",
        status=DbBackupStatus.success,
        path="/opt/postgres/data/backups/20260601T030000Z",
        bytes=4096,
        started_at=now,
        finished_at=now + timedelta(seconds=12),
        created_at=now,
    )
    db_session.add(job)
    db_session.flush()
    return job


def test_jobs_view_renders_backup_job_row(
    client: TestClient, db_session: Session, test_project
) -> None:
    job = _seed_backup_job(db_session)
    db_session.commit()

    resp = client.get(f"/project/{test_project.id}/jobs")
    assert resp.status_code == 200
    html = resp.text

    # The specific backup row is present (id is the detail-link + the sort key).
    assert job.id in html, "backup job id should render in the Jobs table"
    # Title built by the aggregator: "DB backup — manual (pre-migration)".
    assert "DB backup — manual (pre-migration)" in html
    # Type cell renders the db_backup JobType value (plain text, per I-00039 fix).
    assert 'data-sort-job_type="db_backup"' in html
    # success → normalised "completed" status string for this row's status badge.
    assert 'data-sort-status="completed"' in html
    # "manual" surfaces as the Triggered-by value for the row.
    assert 'data-sort-triggered_by="manual"' in html


def test_jobs_view_renders_failed_backup_status(
    client: TestClient, db_session: Session, test_project
) -> None:
    now = datetime(2026, 6, 1, 3, 0, tzinfo=UTC)
    db_session.add(
        DbBackupJob(
            id="backup-job-failed-1",
            backup_type=DbBackupType.scheduled,
            status=DbBackupStatus.failed,
            path="/opt/postgres/data/backups/20260601T030500Z",
            error="pg_restore: error: did not find magic string in file header",
            started_at=now,
            finished_at=now + timedelta(seconds=3),
            created_at=now,
        )
    )
    db_session.commit()

    resp = client.get(f"/project/{test_project.id}/jobs")
    assert resp.status_code == 200
    html = resp.text

    assert "backup-job-failed-1" in html
    assert "DB backup — scheduled" in html
    assert 'data-sort-status="failed"' in html
