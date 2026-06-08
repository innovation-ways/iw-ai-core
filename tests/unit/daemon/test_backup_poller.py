"""Unit tests for the scheduled backup due-time logic in orch.daemon.backup_poller."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from orch.daemon.backup_poller import is_scheduled_backup_due


def test_disabled_backups_are_never_due() -> None:
    """Verifies that is_scheduled_backup_due returns False when backup is disabled."""
    now = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)

    assert (
        is_scheduled_backup_due(now=now, backup_time="03:00", last_attempt_at=None, enabled=False)
        is False
    )


def test_recent_attempt_within_interval_is_not_due() -> None:
    """Verifies that a recent backup attempt prevents the next scheduled backup from firing."""
    now = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    last_attempt = datetime(2026, 6, 1, 3, 5, tzinfo=UTC)

    assert (
        is_scheduled_backup_due(
            now=now,
            backup_time="03:00",
            last_attempt_at=last_attempt,
            enabled=True,
        )
        is False
    )


def test_catch_up_when_window_missed_is_due() -> None:
    """Verifies that a missed backup window triggers a catch-up backup as due."""
    now = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    last_attempt = now - timedelta(days=2)

    assert (
        is_scheduled_backup_due(
            now=now,
            backup_time="03:00",
            last_attempt_at=last_attempt,
            enabled=True,
        )
        is True
    )


def test_failed_attempt_within_interval_suppresses_retry() -> None:
    """Verifies that a failed attempt in the current window prevents a tight retry loop.

    Regression test: when every scheduled backup fails (e.g. a persistent
    config error like the ``pg_authid`` superuser trap), the poller must
    not re-fire on the next daemon poll cycle. Bounding the retry rate
    stops the jobs table from filling with failed rows and prevents the
    daemon log from being drowned in identical errors.
    """
    now = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    # A failed attempt at 04:00 — well inside today's 03:00 window.
    failed_attempt = datetime(2026, 6, 1, 4, 0, tzinfo=UTC)

    assert (
        is_scheduled_backup_due(
            now=now,
            backup_time="03:00",
            last_attempt_at=failed_attempt,
            enabled=True,
        )
        is False
    )
