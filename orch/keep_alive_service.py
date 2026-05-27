"""KeepAliveService — business logic for the Keep-Alive Scheduler.

All DB operations for KeepAliveConfig, KeepAliveSlot, and KeepAliveRun.
Subprocess fire logic and message randomisation are also here.
"""

from __future__ import annotations

import logging
import random
import subprocess
import time as time_mod
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session  # noqa: TC002  same pattern as rest of orch package

from orch.db.models import KeepAliveConfig, KeepAliveRun, KeepAliveSlot

logger = logging.getLogger(__name__)

# I-00112: minimum elapsed wall-clock time for a keep-alive fire to count as
# a real remote round-trip.
MIN_SUCCESS_ELAPSED_MS = 500


# ---------------------------------------------------------------------------
# FireResult — I-00112: replaces tuple[bool, str | None] returned by fire_claude
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FireResult:
    """Result of a single fire_claude subprocess invocation.

    Attributes
    ----------
    returncode : int
        Raw exit code from the claude CLI.
    stdout : str
        Captured stdout (may be empty string on no-op).
    stderr : str
        Captured stderr (usually empty; check when returncode != 0).
    elapsed_ms : int
        Wall-clock milliseconds between subprocess spawn and return,
        measured with time.perf_counter for sub-microsecond precision.

    The ``is_success`` property encodes the Keep-Alive Scheduler's success
    contract: the API call is considered to have landed only when the CLI
    exits 0 *and* stdout is non-empty *and* the round-trip took at least
    500 ms (below that floor is a local short-circuit, not a real call).

    Ref: I-00112
    """

    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: int

    @property
    def is_success(self) -> bool:
        """True only when the CLI confirmed a real API round-trip."""
        return (
            self.returncode == 0
            and self.stdout.strip() != ""
            and self.elapsed_ms >= MIN_SUCCESS_ELAPSED_MS
        )


# ---------------------------------------------------------------------------
# Message pool (hardcoded — not configurable via UI)
# ---------------------------------------------------------------------------

_MESSAGES = [
    "Hi! How are you doing today?",
    "Hello there! Anything interesting going on?",
    "Hey! Just checking in.",
    "Good to connect! What's new?",
    "Hi! Hope you're having a great day.",
    "Hello! Ready for some interesting work?",
    "Hey there! What shall we explore today?",
    "Greetings! How can I help?",
    "Hi! Everything going well?",
    "Hello! Just a quick hello from the scheduler.",
    "Hey! Keeping the connection warm.",
    "Hi! What's on your mind?",
    "Good to hear from you! All good here.",
    "Hello! Just popping in to say hi.",
    "Hey! The day is going well, I hope.",
]


def pick_message() -> str:
    return random.choice(_MESSAGES)  # noqa: S311


# ---------------------------------------------------------------------------
# Config CRUD
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_WINDOW_DURATION_HOURS = 5


def get_config(db: Session) -> KeepAliveConfig:
    """Return the singleton config row (id=1). Creates it with defaults if missing."""
    config = db.get(KeepAliveConfig, 1)
    if config is None:
        config = KeepAliveConfig(
            id=1,
            model=DEFAULT_MODEL,
            window_duration_hours=DEFAULT_WINDOW_DURATION_HOURS,
        )
        db.add(config)
        db.flush()
    return config


def upsert_config(db: Session, model: str, window_duration_hours: int) -> KeepAliveConfig:
    """Update the singleton (id=1). Uses INSERT … ON CONFLICT DO UPDATE."""
    config = get_config(db)
    config.model = model
    config.window_duration_hours = window_duration_hours
    db.flush()
    return config


# ---------------------------------------------------------------------------
# Slot CRUD
# ---------------------------------------------------------------------------


def list_slots(db: Session) -> list[KeepAliveSlot]:
    """Return all slots ordered by time_hhmm."""
    return db.query(KeepAliveSlot).order_by(KeepAliveSlot.time_hhmm).all()


def add_slot(db: Session, time_hhmm: str) -> KeepAliveSlot:
    """Add a new slot.

    Validates time_hhmm format ("HH:MM", 00:00–23:59).
    Raises ValueError on invalid format.
    Raises IntegrityError (from DB) on duplicate — let the router handle it.
    """
    _validate_time_hhmm(time_hhmm)
    slot = KeepAliveSlot(time_hhmm=time_hhmm, enabled=True, config_id=1)
    db.add(slot)
    db.flush()
    return slot


def delete_slot(db: Session, slot_id: int) -> bool:
    """Delete slot. Returns False if not found."""
    slot = db.get(KeepAliveSlot, slot_id)
    if slot is None:
        return False
    db.delete(slot)
    db.flush()
    return True


def toggle_slot(db: Session, slot_id: int) -> KeepAliveSlot | None:
    """Flip enabled. Returns updated slot or None if not found."""
    slot = db.get(KeepAliveSlot, slot_id)
    if slot is None:
        return None
    slot.enabled = not slot.enabled
    db.flush()
    return slot


# ---------------------------------------------------------------------------
# Due-slot detection
# ---------------------------------------------------------------------------


def get_due_slots(db: Session) -> list[KeepAliveSlot]:
    """Return enabled slots that should fire right now.

    A slot is due when ALL of:
    1. slot.enabled is True
    2. slot.time_hhmm parsed as today's local datetime falls within [now - 30min, now]
    3. No KeepAliveRun exists for today's local calendar day (as a tz-aware half-open
       range [today_start_local, tomorrow_start_local)) with this slot's time_hhmm
       AND status in ('success', 'retried_success')

    Uses datetime.now() (no timezone — local time, matching user's schedule intent).
    """
    now = datetime.now()  # noqa: DTZ005 local time per design intent
    today_date = now.date()
    local_tz = now.astimezone().tzinfo
    today_start_local = datetime.combine(today_date, time.min).replace(tzinfo=local_tz)
    tomorrow_start_local = today_start_local + timedelta(days=1)

    # Parse enabled slots and filter to those within the 30-min window
    enabled_slots = db.query(KeepAliveSlot).filter(KeepAliveSlot.enabled == True).all()  # noqa: E712

    due: list[KeepAliveSlot] = []
    for slot in enabled_slots:
        # Parse slot time as today's local datetime
        try:
            hour, minute = slot.time_hhmm.split(":")
            slot_dt = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
        except (ValueError, OverflowError):
            # Malformed time in DB — skip
            continue

        # Window: [now - 30min, now]
        window_start = now - timedelta(minutes=30)
        if slot_dt < window_start or slot_dt > now:
            continue

        # Check: no already-successful run today for this time_hhmm
        run_exists = (
            db.query(KeepAliveRun)
            .filter(
                KeepAliveRun.slot_time == slot.time_hhmm,
                KeepAliveRun.fired_at >= today_start_local,
                KeepAliveRun.fired_at < tomorrow_start_local,
                KeepAliveRun.status.in_(("success", "retried_success")),
            )
            .first()
        )
        if run_exists:
            continue

        due.append(slot)

    return due


# ---------------------------------------------------------------------------
# Run logging
# ---------------------------------------------------------------------------

VALID_RUN_STATUSES = ("success", "failed", "retried_success", "retried_failed")


def log_run(
    db: Session,
    slot_id: int | None,
    slot_time: str,
    status: str,
    error: str | None = None,
    stdout: str | None = None,
    stderr: str | None = None,
    elapsed_ms: int | None = None,
    returncode: int | None = None,
) -> KeepAliveRun:
    """Insert a KeepAliveRun row. status must be one of the four defined values.

    ``stdout``, ``stderr``, ``elapsed_ms``, and ``returncode`` are captured on
    every fire (success or failure) so the operator has post-hoc audit data.
    They are nullable so the model accepts pre-migration rows with NULL.

    Ref: I-00112
    """
    if status not in VALID_RUN_STATUSES:
        raise ValueError(f"Invalid status {status!r}; must be one of {VALID_RUN_STATUSES}")
    run = KeepAliveRun(
        slot_id=slot_id,
        slot_time=slot_time,
        status=status,
        error=error,
        stdout=stdout,
        stderr=stderr,
        elapsed_ms=elapsed_ms,
        returncode=returncode,
    )
    db.add(run)
    db.flush()
    return run


def get_recent_runs(db: Session, limit: int = 10) -> list[KeepAliveRun]:
    """Return most recent runs ordered by fired_at DESC, limit rows."""
    return db.query(KeepAliveRun).order_by(KeepAliveRun.fired_at.desc()).limit(limit).all()


# ---------------------------------------------------------------------------
# Subprocess fire
# ---------------------------------------------------------------------------


def fire_claude(message: str, model: str, timeout: int = 30) -> FireResult:
    """Spawn a claude CLI subprocess pinned to ``model``.

    Runs: ``claude --model <model> -p <message>`` with ``capture_output=True``,
    ``text=True``, and ``timeout=timeout``.

    ``model`` is required — the whole point of the Keep-Alive Scheduler is to
    anchor a usage window on a specific model (typically Sonnet), so we must
    never silently fall back to the user's default ``claude`` model.

    Returns a ``FireResult`` dataclass with ``returncode``, ``stdout``,
    ``stderr``, and ``elapsed_ms`` captured from every invocation.
    Callers MUST use ``result.is_success`` (which encodes the stricter
    contract: rc==0 AND non-empty stdout AND elapsed>=500 ms) — NOT
    ``result.returncode == 0`` — to determine success.

    Does NOT retry — retry logic is in the poller.
    subprocess.TimeoutExpired → returncode=-1, elapsed_ms measured up to the
    timeout boundary.

    Ref: I-00112
    """
    t0 = time_mod.perf_counter()
    try:
        result = subprocess.run(
            ["claude", "--model", model, "-p", message],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed_ms = int(round((time_mod.perf_counter() - t0) * 1000))
        return FireResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            elapsed_ms=elapsed_ms,
        )
    except subprocess.TimeoutExpired:
        elapsed_ms = int(round((time_mod.perf_counter() - t0) * 1000))
        return FireResult(
            returncode=-1,
            stdout="",
            stderr="subprocess timed out",
            elapsed_ms=elapsed_ms,
        )
    except FileNotFoundError:
        elapsed_ms = int(round((time_mod.perf_counter() - t0) * 1000))
        return FireResult(
            returncode=-2,
            stdout="",
            stderr="claude binary not found on PATH",
            elapsed_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = int(round((time_mod.perf_counter() - t0) * 1000))
        return FireResult(
            returncode=-9,
            stdout="",
            stderr=str(exc),
            elapsed_ms=elapsed_ms,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_time_hhmm(time_hhmm: str) -> None:
    """Raise ValueError if time_hhmm is not a valid HH:MM in 00:00–23:59."""
    if len(time_hhmm) != 5 or time_hhmm[2] != ":":
        raise ValueError(f"Invalid time format {time_hhmm!r}; expected HH:MM")
    try:
        h, m = int(time_hhmm[:2]), int(time_hhmm[3:])
    except ValueError:  # noqa: PERF203
        raise ValueError(f"Invalid time format {time_hhmm!r}; expected HH:MM") from None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Invalid time {time_hhmm!r}; hour must be 0–23, minute 0–59")
