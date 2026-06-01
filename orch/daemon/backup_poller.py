"""BackupPoller — daemon component for scheduled orchestration DB backups."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.backup.engine import create_backup
from orch.backup.retention import prune_scheduled_backups
from orch.db.models import DbBackupJob, DbBackupStatus, DbBackupType

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from sqlalchemy.orm import Session

    from orch.config import DaemonConfig

    SessionFactory = Callable[[], AbstractContextManager[Session]]

logger = logging.getLogger(__name__)


def _parse_backup_time(backup_time: str) -> tuple[int, int]:
    hour_str, minute_str = backup_time.strip().split(":", 1)
    hour = int(hour_str)
    minute = int(minute_str)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid backup_time: {backup_time!r}")
    return hour, minute


def _interval_start(now: datetime, backup_time: str) -> datetime:
    hour, minute = _parse_backup_time(backup_time)
    window_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= window_today:
        return window_today
    return window_today - timedelta(days=1)


def is_scheduled_backup_due(
    *,
    now: datetime,
    backup_time: str,
    last_success_at: datetime | None,
    enabled: bool,
) -> bool:
    if not enabled:
        return False
    interval_start = _interval_start(now.astimezone(UTC), backup_time)
    if last_success_at is None:
        return True
    return last_success_at.astimezone(UTC) < interval_start


class BackupPoller:
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
        now = self._now_fn().astimezone(UTC)
        try:
            with self._session_factory() as db:
                last_success = self._last_scheduled_success_at(db)
        except Exception:
            logger.exception("BackupPoller: failed to query last scheduled backup")
            return

        if not is_scheduled_backup_due(
            now=now,
            backup_time=self.config.backup_time,
            last_success_at=last_success,
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

    def _last_scheduled_success_at(self, db: Session) -> datetime | None:
        stmt = (
            select(DbBackupJob.created_at)
            .where(
                DbBackupJob.backup_type == DbBackupType.scheduled,
                DbBackupJob.status == DbBackupStatus.success,
            )
            .order_by(DbBackupJob.created_at.desc())
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()
