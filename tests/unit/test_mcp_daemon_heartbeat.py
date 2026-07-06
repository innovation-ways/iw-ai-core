"""Unit tests for the daemon-heartbeat liveness helpers in orch.mcp.tools.read_tools.

Covers _heartbeat_age_seconds (parsing + age) and _heartbeat_window_seconds
(interval-derived freshness window), which let daemon_status judge liveness from
the shared DB poll heartbeat rather than a namespace-local PID file.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from orch.mcp.tools.read_tools import _heartbeat_age_seconds, _heartbeat_window_seconds


class TestHeartbeatAgeSeconds:
    """Covers _heartbeat_age_seconds parsing and age computation."""

    def test_none_timestamp_returns_none(self) -> None:
        """A missing last-poll timestamp yields None age."""
        assert _heartbeat_age_seconds(None, datetime.now(UTC)) is None

    def test_unparseable_timestamp_returns_none(self) -> None:
        """A non-ISO timestamp string yields None rather than raising."""
        assert _heartbeat_age_seconds("not-a-timestamp", datetime.now(UTC)) is None

    def test_recent_timestamp_small_age(self) -> None:
        """A poll 30s ago yields an age near 30 seconds."""
        now = datetime(2026, 7, 6, 12, 0, 30, tzinfo=UTC)
        age = _heartbeat_age_seconds("2026-07-06T12:00:00+00:00", now)
        assert age == pytest.approx(30.0, abs=0.5)

    def test_naive_timestamp_treated_as_utc(self) -> None:
        """A timezone-naive ISO string is interpreted as UTC (no crash, sane age)."""
        now = datetime(2026, 7, 6, 12, 1, 0, tzinfo=UTC)
        age = _heartbeat_age_seconds("2026-07-06T12:00:00", now)
        assert age == pytest.approx(60.0, abs=0.5)

    def test_future_timestamp_clamped_to_zero(self) -> None:
        """A clock-skewed future poll yields a non-negative (clamped) age."""
        now = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
        future = (now + timedelta(seconds=45)).isoformat()
        assert _heartbeat_age_seconds(future, now) == 0.0


class TestHeartbeatWindowSeconds:
    """Covers _heartbeat_window_seconds interval derivation and floor."""

    def test_default_window_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unset IW_CORE_POLL_INTERVAL yields 3×60 = 180s window."""
        monkeypatch.delenv("IW_CORE_POLL_INTERVAL", raising=False)
        assert _heartbeat_window_seconds() == 180.0

    def test_window_is_three_intervals(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A 120s interval yields a 360s window (3×)."""
        monkeypatch.setenv("IW_CORE_POLL_INTERVAL", "120")
        assert _heartbeat_window_seconds() == 360.0

    def test_tiny_interval_floored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A 5s interval is floored to the 180s minimum, not 15s."""
        monkeypatch.setenv("IW_CORE_POLL_INTERVAL", "5")
        assert _heartbeat_window_seconds() == 180.0

    def test_invalid_interval_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-integer interval falls back to the 180s default window."""
        monkeypatch.setenv("IW_CORE_POLL_INTERVAL", "banana")
        assert _heartbeat_window_seconds() == 180.0
