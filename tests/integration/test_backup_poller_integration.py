"""Integration coverage for BackupPoller.poll() wiring (F-00092 S11).

The pure scheduling decision (disabled / recent-success / missed-window) is unit
tested in ``tests/unit/daemon/test_backup_poller.py``. Here we exercise the
poll() orchestration against a real testcontainer session factory, with
``create_backup`` monkeypatched so no pg client binary is needed:

- AC7 / Boundary "Backups disabled": ``backup_enabled=false`` → poll() runs no
  backup at all.
- AC4 / Boundary "missed-window catch-up": enabled with no prior scheduled
  success and the window already passed → poll() runs one scheduled backup and
  records a success DbBackupJob.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from orch.daemon.backup_poller import BackupPoller
from orch.db.models import DbBackupJob, DbBackupStatus, DbBackupType

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker


def _config(*, enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        backup_enabled=enabled,
        backup_time="03:00",
        backup_retention_days=30,
        backup_dir="/tmp/does-not-matter",  # noqa: S108 — fake create_backup ignores it
    )


def _fake_create_backup_factory(calls: list[str]) -> Any:
    def _fake_create_backup(config: Any, *, backup_type: Any, session: Any, **_: Any) -> Any:
        calls.append(backup_type.value)
        session.add(
            DbBackupJob(
                backup_type=backup_type,
                status=DbBackupStatus.success,
                path="/tmp/backups/fake-set",  # noqa: S108
                bytes=123,
            )
        )
        session.flush()
        return SimpleNamespace(backup_dir="/tmp/backups/fake-set", total_bytes=123)  # noqa: S108

    return _fake_create_backup


def test_poll_disabled_runs_no_backup(db_session_factory: sessionmaker, monkeypatch: Any) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "orch.daemon.backup_poller.create_backup", _fake_create_backup_factory(calls)
    )

    poller = BackupPoller(
        db_session_factory,
        _config(enabled=False),
        now_fn=lambda: datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
    )
    poller.poll()

    assert calls == []
    with db_session_factory() as check:
        assert check.scalars(select(DbBackupJob)).all() == []


def test_poll_missed_window_runs_scheduled_backup(
    db_session_factory: sessionmaker, monkeypatch: Any
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "orch.daemon.backup_poller.create_backup", _fake_create_backup_factory(calls)
    )

    # 10:00, no prior scheduled success, 03:00 window already passed today → due.
    poller = BackupPoller(
        db_session_factory,
        _config(enabled=True),
        now_fn=lambda: datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
    )
    poller.poll()

    assert calls == [DbBackupType.scheduled.value]
    with db_session_factory() as check:
        job = check.scalars(select(DbBackupJob)).one()
        assert job.backup_type == DbBackupType.scheduled
        assert job.status == DbBackupStatus.success


def test_poll_does_not_retry_after_failed_attempt_in_same_window(
    db_session_factory: sessionmaker, monkeypatch: Any
) -> None:
    """Regression: a failed attempt in the current window must suppress re-tries.

    Production bug: when every backup failed with the ``pg_authid``
    superuser trap, ``is_scheduled_backup_due`` returned True on every
    daemon poll cycle (it only checked ``last_success_at``, which stayed
    NULL). The poller re-fired every ~60 s, flooding the jobs table with
    6,000+ failed rows over 5 days. This test pins the fix: once a
    scheduled attempt (success OR failure) has been made inside the
    current daily window, the next poll must be a no-op.
    """
    from orch.daemon import backup_poller as poller_mod

    calls: list[str] = []
    monkeypatch.setattr(poller_mod, "create_backup", _fake_create_backup_factory(calls))

    fixed_now = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)

    # Pre-seed a FAILED scheduled job that already happened at 04:00 today
    # (inside the 03:00 window).
    with db_session_factory() as seed:
        seed.add(
            DbBackupJob(
                backup_type=DbBackupType.scheduled,
                status=DbBackupStatus.failed,
                path="/tmp/backups/earlier-failure",  # noqa: S108
                created_at=datetime(2026, 6, 1, 4, 0, tzinfo=UTC),
            )
        )
        seed.commit()

    poller = BackupPoller(
        db_session_factory,
        _config(enabled=True),
        now_fn=lambda: fixed_now,
    )
    poller.poll()

    # Critical: no new backup attempt, because a failed attempt already
    # happened in the current window.
    assert calls == []
    with db_session_factory() as check:
        jobs = check.scalars(select(DbBackupJob)).all()
        assert len(jobs) == 1
        assert jobs[0].status == DbBackupStatus.failed
        assert jobs[0].created_at == datetime(2026, 6, 1, 4, 0, tzinfo=UTC)


def test_poll_retries_after_failed_attempt_in_previous_window(
    db_session_factory: sessionmaker, monkeypatch: Any
) -> None:
    """A failed attempt from YESTERDAY's window must still let today's backup run.

    The failure-backoff rule is per-window, not forever: a stale failure
    from a prior daily window should not poison today's catch-up.
    """
    from orch.daemon import backup_poller as poller_mod

    calls: list[str] = []
    monkeypatch.setattr(poller_mod, "create_backup", _fake_create_backup_factory(calls))

    fixed_now = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)  # day after yesterday's failure

    with db_session_factory() as seed:
        seed.add(
            DbBackupJob(
                backup_type=DbBackupType.scheduled,
                status=DbBackupStatus.failed,
                path="/tmp/backups/yesterday-failure",  # noqa: S108
                created_at=datetime(2026, 6, 1, 4, 0, tzinfo=UTC),
            )
        )
        seed.commit()

    poller = BackupPoller(
        db_session_factory,
        _config(enabled=True),
        now_fn=lambda: fixed_now,
    )
    poller.poll()

    assert calls == [DbBackupType.scheduled.value]
