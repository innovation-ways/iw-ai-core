"""Unit tests for the scheduled backup due-time logic in orch.daemon.backup_poller."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from orch.daemon.backup_poller import is_scheduled_backup_due


def test_disabled_backups_are_never_due() -> None:
    """Verifies that is_scheduled_backup_due returns False when backup is disabled."""
    now = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)

    assert (
        is_scheduled_backup_due(now=now, backup_time="03:00", last_success_at=None, enabled=False)
        is False
    )


def test_recent_success_within_interval_is_not_due() -> None:
    """Verifies that a recent successful backup prevents the next scheduled backup from firing."""
    now = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    last_success = datetime(2026, 6, 1, 3, 5, tzinfo=UTC)

    assert (
        is_scheduled_backup_due(
            now=now,
            backup_time="03:00",
            last_success_at=last_success,
            enabled=True,
        )
        is False
    )


def test_catch_up_when_window_missed_is_due() -> None:
    """Verifies that a missed backup window triggers a catch-up backup as due."""
    now = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    last_success = now - timedelta(days=2)

    assert (
        is_scheduled_backup_due(
            now=now,
            backup_time="03:00",
            last_success_at=last_success,
            enabled=True,
        )
        is True
    )
