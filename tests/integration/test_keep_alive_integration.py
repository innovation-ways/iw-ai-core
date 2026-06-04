"""Integration tests for KeepAliveService against a real PostgreSQL testcontainer.

All DB operations use the real database — no mocking.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from freezegun import freeze_time
from sqlalchemy import text
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

    @pytest.mark.parametrize(
        ("tz_offset_hours", "freeze_local_dt", "slot_hhmm", "expected_due"),
        [
            # UTC host: local date == UTC date always — no mismatch window.
            # Slot should be skipped (non-regression control — passes pre-fix too).
            pytest.param(0, datetime(2026, 5, 18, 0, 30), "00:15", False, id="UTC"),
            # +01:00 WEST: 00:30 local = 23:30 UTC prev day — the original failing case.
            pytest.param(1, datetime(2026, 5, 18, 0, 30), "00:15", False, id="WEST"),
            # +02:00 CEST: 00:30 local = 22:30 UTC prev day — wider mismatch window.
            pytest.param(2, datetime(2026, 5, 18, 0, 30), "00:15", False, id="CEST"),
            # -05:00 EST: local 00:30 = 05:30 UTC same day (no prev-day mismatch).
            # Test that the positive case still works — slot is correctly skipped.
            pytest.param(-5, datetime(2026, 5, 18, 0, 30), "00:15", False, id="EST"),
        ],
    )
    def test_get_due_slots_skips_already_run_slot_across_utc_midnight(
        self,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
        tz_offset_hours: int,
        freeze_local_dt: datetime,
        slot_hhmm: str,
        expected_due: bool,
    ) -> None:
        """Regression for I-00098: slot leaked through during local-midnight UTC mismatch.

        Pre-fix: get_due_slots returned the slot because func.date(fired_at) was UTC
        and today_date was local — they disagreed during the mismatch window and the
        successful-run filter didn't match.

        Post-fix: get_due_slots returns [] because fired_at (restamped to a
        yesterday-UTC instant) falls inside the tz-aware half-open range
        [today_start_local, tomorrow_start_local).
        """
        # Set the host's simulated local timezone so datetime.now().astimezone()
        # returns a tz with the desired offset. freezegun does not propagate its
        # fake time to astimezone() — we need to set TZ env var and call tzset().
        # Note: Etc/GMT naming is opposite of the standard UTC offset sign:
        #   Etc/GMT-1 == UTC+1 WEST, Etc/GMT-2 == UTC+2 CEST, Etc/GMT+5 == UTC-5 EST
        tz_name = f"Etc/GMT{'-' if tz_offset_hours > 0 else '+'}{abs(tz_offset_hours)}"
        monkeypatch.setenv("TZ", tz_name)
        time.tzset()

        # Freeze Python's clock to the local instant.
        # The tz-aware local time at offset_hours will compute the UTC equivalent.
        with freeze_time(freeze_local_dt):
            get_config(db_session)
            db_session.flush()
            slot = add_slot(db_session, slot_hhmm)
            db_session.flush()

            # Log a successful run via the production path (server-side func.now()
            # stamps fired_at). Then re-stamp fired_at to a deterministic instant
            # that lives in the previous UTC calendar day — this is what triggers
            # the bug pre-fix: func.date(fired_at) UTC != today_date local.
            run = log_run(db_session, slot.id, slot_hhmm, "success")
            db_session.flush()

            # Compute the UTC instant that corresponds to "30 minutes before the
            # frozen local time" — i.e. 00:00 local on a +01:00 host = 23:00 UTC prev
            # day. This becomes fired_at in the DB.
            offset_delta = timedelta(hours=tz_offset_hours)
            local_dt = freeze_local_dt.replace(tzinfo=None)  # naive version
            fired_at_utc = local_dt - offset_delta  # UTC equivalent of 00:30 local

            db_session.execute(
                text("UPDATE keep_alive_runs SET fired_at = :ts WHERE id = :id"),
                {"ts": fired_at_utc.replace(tzinfo=UTC), "id": run.id},
            )
            db_session.commit()

            due = get_due_slots(db_session)
            if expected_due:
                assert len(due) == 1, f"expected slot to be due; got {due}"
                assert due[0].id == slot.id
            else:
                assert due == [], f"expected slot to be skipped; got {due}"

    def test_get_due_slots_returns_slot_when_no_prior_run_exists(self, db_session: Session) -> None:
        """Slots with no prior successful run are returned regardless of TZ."""
        # Use UTC to keep things simple — this tests the positive path.
        with freeze_time(datetime(2026, 5, 18, 12, 0)):
            get_config(db_session)
            db_session.flush()
            slot = add_slot(db_session, "12:00")
            db_session.commit()

            due = get_due_slots(db_session)
            assert len(due) == 1
            assert due[0].id == slot.id


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
