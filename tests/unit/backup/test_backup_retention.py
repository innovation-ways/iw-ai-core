from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from orch.backup.retention import select_prunable_backup_jobs


@dataclass(frozen=True)
class _Candidate:
    job_id: str
    backup_type: str
    created_at: datetime


def test_manual_backups_are_never_pruned() -> None:
    now = datetime(2026, 6, 1, tzinfo=UTC)
    candidates = [
        _Candidate("m1", "manual", now - timedelta(days=365)),
        _Candidate("s1", "scheduled", now - timedelta(days=365)),
    ]

    prunable = select_prunable_backup_jobs(candidates, retention_days=30, now=now)

    assert [item.job_id for item in prunable] == ["s1"]


def test_retention_boundary_exactly_n_days_is_kept() -> None:
    now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    exactly_n = now - timedelta(days=30)
    older_than_n = exactly_n - timedelta(seconds=1)
    candidates = [
        _Candidate("keep", "scheduled", exactly_n),
        _Candidate("drop", "scheduled", older_than_n),
    ]

    prunable = select_prunable_backup_jobs(candidates, retention_days=30, now=now)

    assert [item.job_id for item in prunable] == ["drop"]
