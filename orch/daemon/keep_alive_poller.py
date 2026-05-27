"""KeepAlivePoller — daemon component for the Keep-Alive Scheduler.

Polls for due slots every ~60 seconds and fires the claude CLI subprocess.
Follows the DocJobPoller pattern: stateless, fresh session per poll().
"""

from __future__ import annotations

import logging

from orch.db.session import SessionLocal
from orch.keep_alive_service import (
    MIN_SUCCESS_ELAPSED_MS,
    FireResult,
    fire_claude,
    get_config,
    get_due_slots,
    log_run,
    pick_message,
)

logger = logging.getLogger("orch.keep_alive")

# I-00112 — keep this alias local so call-site docs still point reviewers here
# while the single source of truth lives in orch.keep_alive_service.
_MIN_SUCCESS_ELAPSED_MS = MIN_SUCCESS_ELAPSED_MS


class KeepAlivePoller:
    """Polls due keep-alive slots and fires the claude CLI."""

    def __init__(self) -> None:
        """Stateless — session opened per poll call."""

    def poll(self) -> None:
        """Single poll cycle.

        For each due slot:
          1. Pick a random message.
          2. Call fire_claude(message, model) using the model configured in KeepAliveConfig.
          3. If success: log_run(status='success').
          4. If failure: retry once with a new random message.
             - Retry success → log_run(status='retried_success').
             - Retry failure → log_run(status='retried_failed', error=combined_errors).
        Each slot is processed independently; one slot's failure does NOT stop others.

        Slots are snapshotted to primitive (id, time_hhmm) tuples while their
        session is still open. Passing the ORM instance forward would detach it
        when the session closes — and SessionLocal's default expire_on_commit=True
        means any subsequent attribute access triggers a refresh that fails with
        DetachedInstanceError, masking every fire_claude success as an "unexpected
        error" and preventing the run from ever being logged.

        The configured ``model`` is read once per poll cycle and threaded into
        ``fire_claude`` so the subprocess actually runs against the model the
        scheduler is anchoring a usage window on (typically Sonnet). Before
        2026-05-19 the model field was stored but never passed to the CLI,
        so every keep-alive ran against the user's default model (Opus).
        """
        with SessionLocal() as db:
            due_slots = get_due_slots(db)
            slot_snapshots = [(slot.id, slot.time_hhmm) for slot in due_slots]
            model = get_config(db).model
            db.commit()

        for slot_id, slot_time in slot_snapshots:
            try:
                self._fire_slot(slot_id, slot_time, model)
            except Exception:
                logger.exception("Unexpected error processing keep-alive slot %s", slot_id)

    def _fire_slot(self, slot_id: int, slot_time: str, model: str) -> None:
        """Fire a single slot: attempt + optional retry, then log result.

        Uses FireResult.is_success (I-00112 strict contract: rc==0 AND
        non-empty stdout AND elapsed>=_MIN_SUCCESS_ELAPSED_MS) rather than
        returncode==0 alone. Retry logic is preserved; the retry also requires
        is_success to be True, not just rc==0.
        """
        message_1 = pick_message()
        result_1: FireResult = fire_claude(message_1, model)

        if result_1.is_success:
            self._log_run(
                slot_id,
                slot_time,
                status="success",
                stdout=result_1.stdout,
                stderr=result_1.stderr,
                elapsed_ms=result_1.elapsed_ms,
                returncode=result_1.returncode,
            )
            return

        # Retry once with a new message
        message_2 = pick_message()
        result_2: FireResult = fire_claude(message_2, model)

        if result_2.is_success:
            self._log_run(
                slot_id,
                slot_time,
                status="retried_success",
                stdout=result_2.stdout,
                stderr=result_2.stderr,
                elapsed_ms=result_2.elapsed_ms,
                returncode=result_2.returncode,
            )
        else:
            combined_error = (
                f"rc={result_1.returncode} elapsed={result_1.elapsed_ms}ms; "
                f"retry rc={result_2.returncode} elapsed={result_2.elapsed_ms}ms"
            )
            self._log_run(
                slot_id,
                slot_time,
                status="retried_failed",
                error=combined_error,
                stdout=result_1.stdout,
                stderr=result_1.stderr,
                elapsed_ms=result_1.elapsed_ms,
                returncode=result_1.returncode,
            )

    def _log_run(
        self,
        slot_id: int,
        slot_time: str,
        status: str,
        error: str | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        elapsed_ms: int | None = None,
        returncode: int | None = None,
    ) -> None:
        """Log a run record within a fresh session.

        All four diagnostic fields (stdout, stderr, elapsed_ms, returncode)
        are persisted on every run so the operator can audit post-hoc even for
        failed attempts. Ref: I-00112.
        """
        with SessionLocal() as db:
            log_run(
                db,
                slot_id=slot_id,
                slot_time=slot_time,
                status=status,
                error=error,
                stdout=stdout,
                stderr=stderr,
                elapsed_ms=elapsed_ms,
                returncode=returncode,
            )
            db.commit()
        logger.info(
            "KeepAlive slot=%s time=%s status=%s error=%s stdout=%r elapsed_ms=%s returncode=%s",
            slot_id,
            slot_time,
            status,
            error,
            stdout[:80] if stdout else stdout,
            elapsed_ms,
            returncode,
        )
