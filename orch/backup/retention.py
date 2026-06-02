"""Retention policy for scheduled backup jobs.

Identifies backup set directories that have exceeded the configured retention
window and removes both their on-disk artifacts and the corresponding
DbBackupJob rows. Manual (labeled) backups are always preserved.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.db.models import DbBackupJob, DbBackupType

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from sqlalchemy.orm import Session


@dataclass(frozen=True)
class BackupRetentionCandidate:
    """Lightweight view of a DbBackupJob used for retention evaluation.

    Attributes:
        job_id: The DbBackupJob primary key UUID.
        backup_type: The string value of DbBackupType (e.g. "scheduled").
        created_at: When the backup job was created (UTC).
    """

    job_id: str
    backup_type: str
    created_at: datetime


@dataclass(frozen=True)
class PruneResult:
    """Summary of a pruning run.

    Attributes:
        deleted_job_ids: Primary key UUIDs of the DbBackupJob rows deleted.
        deleted_paths: On-disk backup set directory paths that were removed.
    """

    deleted_job_ids: list[str]
    deleted_paths: list[str]


def select_prunable_backup_jobs(
    candidates: Sequence[BackupRetentionCandidate],
    *,
    retention_days: int,
    now: datetime,
) -> list[BackupRetentionCandidate]:
    """Return scheduled backups strictly older than retention_days.

    Boundary rule: created_at == now - retention_days is kept.
    Manual backups are always kept.
    """
    cutoff = now - timedelta(days=retention_days)
    return [
        item
        for item in candidates
        if item.backup_type == DbBackupType.scheduled.value and item.created_at < cutoff
    ]


def prune_scheduled_backups(
    session: Session,
    *,
    retention_days: int,
    now_fn: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> PruneResult:
    """Delete scheduled backup jobs and their on-disk artifacts past retention_days.

    Loads all DbBackupJob rows, applies select_prunable_backup_jobs, removes
    the on-disk set directories, deletes the rows, and flushes the session.
    Manual backups are never pruned.

    Args:
        session: Active SQLAlchemy session (caller must commit after this returns).
        retention_days: Backups strictly older than this many days are pruned.
        now_fn: Injectable clock for tests.

    Returns:
        PruneResult listing which job IDs and paths were deleted.
    """
    now = now_fn().astimezone(UTC)
    rows = list(session.scalars(select(DbBackupJob)).all())

    candidates = [
        BackupRetentionCandidate(
            job_id=row.id,
            backup_type=row.backup_type.value,
            created_at=row.created_at,
        )
        for row in rows
    ]
    prunable = select_prunable_backup_jobs(candidates, retention_days=retention_days, now=now)
    prunable_ids = {item.job_id for item in prunable}

    deleted_job_ids: list[str] = []
    deleted_paths: list[str] = []
    for row in rows:
        if row.id not in prunable_ids:
            continue
        shutil.rmtree(Path(row.path), ignore_errors=True)
        deleted_paths.append(row.path)
        deleted_job_ids.append(row.id)
        session.delete(row)

    session.flush()
    return PruneResult(deleted_job_ids=deleted_job_ids, deleted_paths=deleted_paths)
