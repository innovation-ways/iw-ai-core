"""Integration tests for KeepAliveService against a real PostgreSQL testcontainer.

All DB operations use the real database — no mocking.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError

from orch.db.models import KeepAliveConfig, KeepAliveSlot
from orch.keep_alive_service import (
    add_slot,
    delete_slot,
    get_config,
    get_due_slots,
    get_recent_runs,
    log_run,
    toggle_slot,
    upsert_config,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helper: make a real KeepAliveSlot in the DB
# ---------------------------------------------------------------------------


def _make_slot(db: Session, time_hhmm: str, enabled: bool = True) -> KeepAliveSlot:
    """Create a real KeepAliveSlot in the test DB."""
    get_config(db)
    db.flush()
    slot = add_slot(db, time_hhmm)
    if not enabled:
        slot.enabled = False
        db.flush()
    return slot


# ---------------------------------------------------------------------------
# Due-slot detection (real DB)
# ---------------------------------------------------------------------------


class TestGetDueSlotsIntegration:
    """Integration tests for get_due_slots() with real DB."""

    def test_get_due_slots_fires_when_slot_in_window(self, db_session: Session) -> None:
        """Slot at current time → returned."""
        now = datetime.now(UTC).astimezone()
        current_time_str = now.strftime("%H:%M")

        slot = _make_slot(db_session, current_time_str)
        db_session.commit()

        due = get_due_slots(db_session)
        assert len(due) == 1
        assert due[0].id == slot.id

    def test_get_due_slots_skips_disabled_slot(self, db_session: Session) -> None:
        """Slot.enabled=False → not returned."""
        now = datetime.now(UTC).astimezone()
        current_time_str = now.strftime("%H:%M")

        _make_slot(db_session, current_time_str, enabled=False)
        db_session.commit()

        due = get_due_slots(db_session)
        assert len(due) == 0


# ---------------------------------------------------------------------------
# Config CRUD
# ---------------------------------------------------------------------------


class TestConfigCrud:
    """Tests for KeepAliveConfig CRUD operations."""

    def test_get_config_creates_default_if_missing(self, db_session: Session) -> None:
        """No row exists → get_config() creates and returns default."""
        # Ensure no config row exists
        existing = db_session.get(KeepAliveConfig, 1)
        if existing:
            db_session.delete(existing)
            db_session.flush()

        config = get_config(db_session)
        db_session.commit()

        assert config.id == 1
        assert config.model == "claude-sonnet-4-6"
        assert config.window_duration_hours == 5

    def test_upsert_config_creates_then_updates(self, db_session: Session) -> None:
        """First upsert: creates row. Second upsert: updates. Assert only one row exists."""
        # Ensure clean state
        existing = db_session.get(KeepAliveConfig, 1)
        if existing:
            db_session.delete(existing)
            db_session.flush()

        # First upsert — creates
        upsert_config(db_session, "claude-opus-4-7", 4)
        db_session.commit()
        count = db_session.query(KeepAliveConfig).count()
        assert count == 1

        # Second upsert — updates
        config2 = upsert_config(db_session, "claude-haiku-4-5-20251001", 6)
        db_session.commit()

        assert config2.id == 1
        assert config2.model == "claude-haiku-4-5-20251001"
        assert config2.window_duration_hours == 6

        # Still only one row
        count = db_session.query(KeepAliveConfig).count()
        assert count == 1


# ---------------------------------------------------------------------------
# Slot CRUD
# ---------------------------------------------------------------------------


class TestSlotCrud:
    """Tests for KeepAliveSlot CRUD operations."""

    def test_add_slot_creates_row(self, db_session: Session) -> None:
        """add_slot creates a slot row with correct fields."""
        # Ensure config exists (required FK)
        get_config(db_session)
        db_session.flush()

        slot = add_slot(db_session, "10:02")
        db_session.commit()

        assert slot.id is not None
        assert slot.time_hhmm == "10:02"
        assert slot.enabled is True

    def test_add_slot_rejects_duplicate(self, db_session: Session) -> None:
        """Adding the same time_hhmm twice raises IntegrityError."""
        get_config(db_session)
        db_session.flush()

        add_slot(db_session, "10:02")
        db_session.commit()

        with pytest.raises(IntegrityError):
            add_slot(db_session, "10:02")

    def test_toggle_slot_flips_enabled(self, db_session: Session) -> None:
        """toggle_slot flips enabled True→False→True."""
        get_config(db_session)
        db_session.flush()

        slot = add_slot(db_session, "05:00")
        db_session.commit()

        assert slot.enabled is True

        toggled = toggle_slot(db_session, slot.id)
        db_session.commit()
        assert toggled is not None
        assert toggled.enabled is False

        back = toggle_slot(db_session, slot.id)
        db_session.commit()
        assert back is not None
        assert back.enabled is True

    def test_delete_slot_nullifies_run_slot_id(self, db_session: Session) -> None:
        """Deleting a slot sets KeepAliveRun.slot_id to NULL (not cascade delete)."""
        get_config(db_session)
        db_session.flush()

        slot = add_slot(db_session, "15:04")
        db_session.flush()

        run = log_run(db_session, slot.id, "15:04", "success")
        db_session.flush()

        delete_slot(db_session, slot.id)
        db_session.commit()

        db_session.refresh(run)
        assert run.slot_id is None
        assert run.slot_time == "15:04"  # snapshot preserved


# ---------------------------------------------------------------------------
# Run Logging
# ---------------------------------------------------------------------------


class TestRunLogging:
    """Tests for KeepAliveRun logging functions."""

    def test_log_run_with_null_slot_id(self, db_session: Session) -> None:
        """log_run can be called with slot_id=None (e.g., claude binary not found)."""
        run = log_run(db_session, None, "05:00", "retried_failed", error="claude not found")
        db_session.commit()

        assert run.slot_id is None
        assert run.slot_time == "05:00"
        assert run.status == "retried_failed"
        assert run.error == "claude not found"

    def test_get_recent_runs_returns_ten_newest(self, db_session: Session) -> None:
        """get_recent_runs(limit=10) returns at most 10 rows, newest-first."""
        get_config(db_session)
        db_session.flush()

        slot = add_slot(db_session, "20:06")
        db_session.flush()

        for _ in range(15):
            log_run(db_session, slot.id, "20:06", "success")
            db_session.flush()

        db_session.commit()

        runs = get_recent_runs(db_session, limit=10)
        assert len(runs) == 10

        # Ordered newest-first (fired_at descending)
        for i in range(len(runs) - 1):
            assert runs[i].fired_at >= runs[i + 1].fired_at
