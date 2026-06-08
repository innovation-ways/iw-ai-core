"""BackupPoller — daemon component for scheduled orchestration DB backups."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.backup.engine import create_backup
from orch.backup.retention import prune_scheduled_backups
from orch.db.models import DbBackupJob, DbBackupType

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from sqlalchemy.orm import Session

    from orch.config import DaemonConfig

    SessionFactory = Callable[[], AbstractContextManager[Session]]

logger = logging.getLogger(__name__)


def _parse_backup_time(backup_time: str) -> tuple[int, int]:
    """Parse an ``HH:MM`` backup-time string into (hour, minute) integers.

    Args:
        backup_time: Time string in ``HH:MM`` format.

    Returns:
        Tuple of (hour, minute) as integers.

    Raises:
        ValueError: If the format is invalid or values are out of range.
    """
    hour_str, minute_str = backup_time.strip().split(":", 1)
    hour = int(hour_str)
    minute = int(minute_str)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid backup_time: {backup_time!r}")
    return hour, minute


def _interval_start(now: datetime, backup_time: str) -> datetime:
    """Return the start of the current daily backup window for ``now``.

    Args:
        now: Current UTC datetime.
        backup_time: Configured backup time in ``HH:MM`` format.

    Returns:
        The most recent daily window-start datetime at or before ``now``.
    """
    hour, minute = _parse_backup_time(backup_time)
    window_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= window_today:
        return window_today
    return window_today - timedelta(days=1)


def is_scheduled_backup_due(
    *,
    now: datetime,
    backup_time: str,
    last_attempt_at: datetime | None,
    enabled: bool,
) -> bool:
    """Return True if a scheduled backup should run now.

    "Attempt" means any scheduled backup recorded in ``db_backup_jobs``,
    regardless of success or failure. Counting failed attempts is what
    bounds the retry loop when a persistent config error (e.g. the
    ``pg_authid`` superuser trap) makes every backup fail — without this,
    the poller would re-fire every daemon poll cycle and flood the jobs
    table with a fresh failed row each time.

    Args:
        now: Current datetime (timezone-aware).
        backup_time: Configured backup time in ``HH:MM`` format.
        last_attempt_at: Timestamp of the most recent scheduled backup
            attempt (success OR failure), or None if no scheduled backup
            has ever been attempted.
        enabled: Whether scheduled backups are enabled in config.

    Returns:
        True when a backup is overdue; False when disabled or when an
        attempt has already been made in the current daily window.
    """
    if not enabled:
        return False
    interval_start = _interval_start(now.astimezone(UTC), backup_time)
    if last_attempt_at is None:
        return True
    return last_attempt_at.astimezone(UTC) < interval_start


class BackupPoller:
    """Daemon component that polls for scheduled orchestration-DB backup windows.

    Attributes:
        config: Daemon configuration containing backup schedule and retention settings.
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        config: DaemonConfig,
        *,
        now_fn: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self.config = config
        self._now_fn = now_fn

    def poll(self) -> None:
        """Run one backup-poll cycle.

        Checks whether a scheduled backup is due (via ``is_scheduled_backup_due``),
        creates a backup if so, and then prunes backups older than the configured
        retention period. Each phase is run inside its own session so a prune
        failure does not roll back a successful backup.
        """
        now = self._now_fn().astimezone(UTC)
        try:
            with self._session_factory() as db:
                last_attempt = self._last_scheduled_attempt_at(db)
        except Exception:
            logger.exception("BackupPoller: failed to query last scheduled backup")
            return

        if not is_scheduled_backup_due(
            now=now,
            backup_time=self.config.backup_time,
            last_attempt_at=last_attempt,
            enabled=self.config.backup_enabled,
        ):
            return

        with self._session_factory() as db:
            try:
                result = create_backup(
                    self.config,
                    backup_type=DbBackupType.scheduled,
                    session=db,
                )
                db.commit()
                logger.info(
                    "Scheduled backup completed: %s (%d bytes)",
                    result.backup_dir,
                    result.total_bytes,
                )
            except Exception:
                db.commit()
                logger.exception("Scheduled backup failed")
                return

            try:
                prune_result = prune_scheduled_backups(
                    db,
                    retention_days=self.config.backup_retention_days,
                    now_fn=lambda: now,
                )
                db.commit()
                if prune_result.deleted_job_ids:
                    logger.info(
                        "Scheduled backup prune removed %d backup(s)",
                        len(prune_result.deleted_job_ids),
                    )
            except Exception:
                logger.exception("Scheduled backup succeeded but prune failed")

    def _last_scheduled_attempt_at(self, db: Session) -> datetime | None:
        """Query the timestamp of the most recent scheduled backup attempt.

        Includes both successful and failed attempts so the poller does not
        re-fire on the next cycle when the prior attempt failed (the
        ``last_success_at``-only variant caused a tight retry loop whenever
        a persistent config error — e.g. the ``pg_authid`` superuser trap —
        made every backup fail).

        Args:
            db: Active database session.

        Returns:
            Timestamp of the last scheduled backup attempt, or None if none exists.
        """
        stmt = (
            select(DbBackupJob.created_at)
            .where(DbBackupJob.backup_type == DbBackupType.scheduled)
            .order_by(DbBackupJob.created_at.desc())
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()
