"""KeepAlivePoller — daemon component for the Keep-Alive Scheduler.

Polls for due slots every ~60 seconds and fires the claude CLI subprocess.
Follows the DocJobPoller pattern: stateless, fresh session per poll().
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from orch.db.session import SessionLocal
from orch.keep_alive_service import (
    fire_claude,
    get_due_slots,
    log_run,
    pick_message,
)

if TYPE_CHECKING:
    from orch.db.models import KeepAliveSlot

logger = logging.getLogger("orch.keep_alive")


class KeepAlivePoller:
    """Polls due keep-alive slots and fires the claude CLI."""

    def __init__(self) -> None:
        """Stateless — session opened per poll call."""

    def poll(self) -> None:
        """Single poll cycle.

        For each due slot:
          1. Pick a random message.
          2. Call fire_claude(message).
          3. If success: log_run(status='success').
          4. If failure: retry once with a new random message.
             - Retry success → log_run(status='retried_success').
             - Retry failure → log_run(status='retried_failed', error=combined_errors).
        Each slot is processed independently; one slot's failure does NOT stop others.
        Open a fresh DB session per poll() call (use SessionLocal() context manager).
        Log outcomes via stdlib logging (logger name: 'orch.keep_alive').
        """
        with SessionLocal() as db:
            due_slots = get_due_slots(db)
            db.commit()

        for slot in due_slots:
            try:
                self._fire_slot(slot)
            except Exception:
                logger.exception("Unexpected error processing keep-alive slot %s", slot.id)

    def _fire_slot(self, slot: KeepAliveSlot) -> None:
        """Fire a single slot: attempt + optional retry, then log result."""
        message_1 = pick_message()
        success_1, error_1 = fire_claude(message_1)

        if success_1:
            self._log_run(slot, status="success")
            return

        # Retry once with a new message
        message_2 = pick_message()
        success_2, error_2 = fire_claude(message_2)

        if success_2:
            self._log_run(slot, status="retried_success")
        else:
            combined_error = f"{error_1 or 'unknown'}; retry error: {error_2 or 'unknown'}"
            self._log_run(slot, status="retried_failed", error=combined_error)

    def _log_run(
        self,
        slot: KeepAliveSlot,
        status: str,
        error: str | None = None,
    ) -> None:
        """Log a run record within a fresh session."""
        with SessionLocal() as db:
            log_run(
                db,
                slot_id=slot.id,
                slot_time=slot.time_hhmm,
                status=status,
                error=error,
            )
            db.commit()
        logger.info(
            "KeepAlive slot=%s time=%s status=%s error=%s",
            slot.id,
            slot.time_hhmm,
            status,
            error,
        )
