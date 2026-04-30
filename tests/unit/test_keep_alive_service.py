"""Unit tests for KeepAliveService — due-slot detection, message randomization.

All database and subprocess interactions are mocked where needed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helper: make a mock KeepAliveSlot
# ---------------------------------------------------------------------------


def make_slot(
    slot_id: int = 1,
    time_hhmm: str = "10:00",
    enabled: bool = True,
) -> MagicMock:
    slot = MagicMock()
    slot.id = slot_id
    slot.time_hhmm = time_hhmm
    slot.enabled = enabled
    return slot


# ---------------------------------------------------------------------------
# Due-slot detection (mock DB query results)
# ---------------------------------------------------------------------------


class TestGetDueSlots:
    """Tests for get_due_slots() — slot fires within 30-min window."""

    def _mock_db_with_slots(self, slots: list[MagicMock]) -> MagicMock:
        """Build a mock DB that returns the given slots from query."""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = slots
        return mock_db

    def test_get_due_slots_fires_when_slot_in_window(self) -> None:
        """Slot at current time → returned."""
        from orch.db.models import KeepAliveRun, KeepAliveSlot
        from orch.keep_alive_service import get_due_slots

        # Use a fixed time to ensure deterministic results
        now = datetime(2026, 4, 30, 10, 0, 0, tzinfo=UTC)
        current_time_str = "10:00"

        mock_slot = make_slot(slot_id=1, time_hhmm=current_time_str, enabled=True)

        # Build mock DB that returns our slot for enabled slots query
        mock_db = MagicMock()
        mock_slot_query = MagicMock()
        mock_slot_query.filter.return_value = mock_slot_query
        mock_slot_query.all.return_value = [mock_slot]

        # Build mock for run check query - returns None (no prior run)
        mock_run_query = MagicMock()
        mock_run_query.filter.return_value = mock_run_query
        mock_run_query.first.return_value = None

        def query_side_effect(model):
            if model is KeepAliveSlot:
                return mock_slot_query
            if model is KeepAliveRun:
                return mock_run_query
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        # Patch datetime.now() to return our fixed time
        with patch("orch.keep_alive_service.datetime") as mock_dt:
            mock_dt.now.return_value = now

            result = get_due_slots(mock_db)

        assert len(result) == 1
        assert result[0].id == 1

    def test_get_due_slots_skips_disabled_slot(self) -> None:
        """Slot.enabled=False → not returned."""
        from orch.keep_alive_service import get_due_slots

        mock_slot = make_slot(slot_id=1, time_hhmm="10:00", enabled=False)
        mock_db = self._mock_db_with_slots([mock_slot])

        result = get_due_slots(mock_db)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Message randomization
# ---------------------------------------------------------------------------


class TestPickMessage:
    """Tests for pick_message()."""

    def test_pick_message_returns_string(self) -> None:
        """pick_message() returns a non-empty string."""
        from orch.keep_alive_service import pick_message

        result = pick_message()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_pick_message_is_random(self) -> None:
        """Calling pick_message() 100 times returns at least 3 distinct messages."""
        from orch.keep_alive_service import pick_message

        messages = {pick_message() for _ in range(100)}
        assert len(messages) >= 3


# ---------------------------------------------------------------------------
# fire_claude (mock subprocess.run)
# ---------------------------------------------------------------------------


class TestFireClaude:
    """Tests for fire_claude() subprocess invocation."""

    def test_fire_claude_returns_true_on_success(self) -> None:
        """subprocess.run returns CompletedProcess(returncode=0) → (True, None)."""
        from subprocess import CompletedProcess

        from orch.keep_alive_service import fire_claude

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            success, error = fire_claude("test message")

        assert success is True
        assert error is None

    def test_fire_claude_returns_false_on_nonzero(self) -> None:
        """returncode=1, stderr="error" → (False, "error")."""
        from subprocess import CompletedProcess

        from orch.keep_alive_service import fire_claude

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = CompletedProcess(
                args=[], returncode=1, stdout="", stderr="connection failed"
            )
            success, error = fire_claude("test message")

        assert success is False
        assert error == "connection failed"

    def test_fire_claude_returns_false_on_timeout(self) -> None:
        """subprocess.run raises TimeoutExpired → (False, <exception str>)."""
        from subprocess import TimeoutExpired

        from orch.keep_alive_service import fire_claude

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = TimeoutExpired(cmd=["claude"], timeout=30)
            success, error = fire_claude("test message")

        assert success is False
        assert error is not None
        assert "timed out" in error


# ---------------------------------------------------------------------------
# Time parsing
# ---------------------------------------------------------------------------


class TestValidateTimeHhmm:
    """Tests for _validate_time_hhmm() called by add_slot()."""

    def test_add_slot_rejects_invalid_format(self) -> None:
        """Invalid formats raise ValueError."""
        from orch.keep_alive_service import _validate_time_hhmm

        invalid_times = ["25:00", "5:00", "abc", "12:60", "12:5", "1:00", "", "1200", "12-00"]
        for invalid in invalid_times:
            with pytest.raises(ValueError, match="Invalid time"):
                _validate_time_hhmm(invalid)

    def test_add_slot_accepts_valid_format(self) -> None:
        """Valid HH:MM formats do not raise."""
        from orch.keep_alive_service import _validate_time_hhmm

        valid_times = ["00:00", "23:59", "10:02", "05:00", "12:30", "00:01"]
        for valid in valid_times:
            # Should not raise
            _validate_time_hhmm(valid)
