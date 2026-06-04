"""Integration coverage for the DbBackupJob row state machine + retention prune.

Uses the real testcontainer ``db_session`` (so the DbBackupJob row, its enum
columns and the JSONB ``row_counts`` are persisted and read back through real
PostgreSQL) but injects ``command_runner`` / ``db_introspector`` / ``which_func``
so no pg client binary is required. The full real dump→restore round-trip lives
in ``test_backup_roundtrip.py``.

Covers:
- Invariant 1 / 2 + AC2: a successful backup records a DbBackupJob with
  status=success, byte size, row counts and instance id.
- Boundary "truncated/corrupt archive" + Invariant 2: integrity failure records
  status=failed with an error and cleans up the partial set.
- AC1 / Invariant 3: retention deletes scheduled backups older than N days,
  removes their on-disk set, and never touches manual backups.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import select

from orch.backup.engine import BackupIntegrityError, create_backup
from orch.backup.retention import prune_scheduled_backups
from orch.db.models import DbBackupJob, DbBackupStatus, DbBackupType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_META: dict[str, Any] = {
    "alembic_revision": "rev-deadbeef",
    "instance_id": "11111111-1111-1111-1111-111111111111",
    "row_counts": {"projects": 2, "batches": 1, "work_items": 5},
    "server_version": "15.12",
    "server_major": 15,
}


def _config(backup_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        backup_dir=str(backup_dir),
        db_host="127.0.0.1",
        db_port=5544,
        db_name="iw_orch",
        db_user="iw_orch",
        db_password="secret",  # noqa: S106
    )


def test_successful_backup_records_success_job(db_session: Session, tmp_path: Path) -> None:
    def _runner(
        argv: list[str], *, output_path: Path | None = None, _env: dict[str, str] | None = None
    ) -> None:
        if "pg_dumpall" in argv[0]:
            assert output_path is not None
            output_path.write_text("-- globals\n")
        elif "pg_dump" in argv[0]:
            assert output_path is not None
            output_path.write_bytes(b"PGDMP-bytes")
        elif "pg_restore" in argv[0]:
            return

    result = create_backup(
        _config(tmp_path),
        backup_type=DbBackupType.manual,
        label="pre-migration",
        session=db_session,
        command_runner=_runner,
        db_introspector=lambda _cfg: dict(_META),
        now_fn=lambda: datetime(2026, 6, 1, 3, 0, tzinfo=UTC),
        which_func=lambda name: f"/usr/bin/{name}",
    )

    job = db_session.scalars(select(DbBackupJob)).one()
    assert job.status == DbBackupStatus.success
    assert job.backup_type == DbBackupType.manual
    assert job.label == "pre-migration"
    assert job.bytes == result.total_bytes
    assert job.bytes > 0
    assert job.row_counts == {"projects": 2, "batches": 1, "work_items": 5}
    assert job.instance_id == "11111111-1111-1111-1111-111111111111"
    assert job.alembic_revision == "rev-deadbeef"
    assert job.error is None
    assert job.started_at is not None
    assert job.finished_at is not None


def test_integrity_failure_records_failed_job_and_cleans_up(
    db_session: Session, tmp_path: Path
) -> None:
    def _runner(
        argv: list[str], *, output_path: Path | None = None, _env: dict[str, str] | None = None
    ) -> None:
        if "pg_dumpall" in argv[0]:
            assert output_path is not None
            output_path.write_text("-- globals\n")
        elif "pg_dump" in argv[0]:
            assert output_path is not None
            output_path.write_bytes(b"garbage-not-a-real-archive")
        elif "pg_restore" in argv[0]:
            raise RuntimeError("pg_restore: error: did not find magic string in file header")

    with pytest.raises(BackupIntegrityError):
        create_backup(
            _config(tmp_path),
            backup_type=DbBackupType.scheduled,
            session=db_session,
            command_runner=_runner,
            db_introspector=lambda _cfg: dict(_META),
            now_fn=lambda: datetime(2026, 6, 1, 3, 0, tzinfo=UTC),
            which_func=lambda name: f"/usr/bin/{name}",
        )

    job = db_session.scalars(select(DbBackupJob)).one()
    assert job.status == DbBackupStatus.failed
    assert job.error is not None
    assert "magic string" in job.error
    # The partial set directory is removed so catch-up still treats it as missing.
    assert list(tmp_path.iterdir()) == []


def _backup_set_on_disk(tmp_path: Path, name: str) -> Path:
    set_dir = tmp_path / name
    set_dir.mkdir()
    (set_dir / "iw_orch.dump").write_bytes(b"x")
    (set_dir / "globals.sql").write_text("-- g")
    (set_dir / "manifest.json").write_text("{}")
    return set_dir


def test_prune_deletes_old_scheduled_keeps_manual_and_recent(
    db_session: Session, tmp_path: Path
) -> None:
    now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

    old_sched_dir = _backup_set_on_disk(tmp_path, "old_scheduled")
    manual_dir = _backup_set_on_disk(tmp_path, "old_manual")
    recent_sched_dir = _backup_set_on_disk(tmp_path, "recent_scheduled")

    old_scheduled = DbBackupJob(
        backup_type=DbBackupType.scheduled,
        status=DbBackupStatus.success,
        path=str(old_sched_dir),
        created_at=now - timedelta(days=40),
    )
    old_manual = DbBackupJob(
        backup_type=DbBackupType.manual,
        label="keep-me-forever",
        status=DbBackupStatus.success,
        path=str(manual_dir),
        created_at=now - timedelta(days=400),
    )
    recent_scheduled = DbBackupJob(
        backup_type=DbBackupType.scheduled,
        status=DbBackupStatus.success,
        path=str(recent_sched_dir),
        created_at=now - timedelta(days=5),
    )
    db_session.add_all([old_scheduled, old_manual, recent_scheduled])
    db_session.flush()

    result = prune_scheduled_backups(db_session, retention_days=30, now_fn=lambda: now)

    assert result.deleted_job_ids == [old_scheduled.id]
    assert result.deleted_paths == [str(old_sched_dir)]

    # Only the old scheduled set is gone from disk; manual + recent survive.
    assert not old_sched_dir.exists()
    assert manual_dir.exists()
    assert recent_sched_dir.exists()

    remaining = {
        (job.backup_type, job.label) for job in db_session.scalars(select(DbBackupJob)).all()
    }
    assert remaining == {
        (DbBackupType.manual, "keep-me-forever"),
        (DbBackupType.scheduled, None),
    }
