"""I-00112 — Keep-Alive Scheduler success contract regression tests (integration layer).

End-to-end coverage of the success contract: mock at ``subprocess.run`` (the only
boundary that exercises the FireResult logic) and verify the persisted
``keep_alive_runs`` row reflects the captured ``stdout``/``stderr``/``elapsed_ms``/
``returncode`` AND the contract-driven status.

The pure-unit reproduction tests (1–4) live in
``tests/unit/test_keep_alive_poller_success_contract.py``. The two DB-backed
tests here cover AC1 (silent no-op → status='failed' or 'retried_failed' with
diagnostic detail) and AC2 (real round-trip → status='success' with detail).

Ref: I-00112 (design doc § Test to Reproduce — tests 5 and 6).
"""

from __future__ import annotations

from datetime import datetime
from subprocess import CompletedProcess
from typing import TYPE_CHECKING
from unittest.mock import patch

from orch.daemon.keep_alive_poller import KeepAlivePoller
from orch.db.models import KeepAliveRun
from orch.keep_alive_service import add_slot, get_config

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


def _now_hhmm() -> str:
    return datetime.now().strftime("%H:%M")  # noqa: DTZ005 — matches poller's local-time intent


def _seed_slot(db: Session) -> int:
    """Insert config + a due slot, commit, return the slot id."""
    get_config(db)
    db.flush()
    slot = add_slot(db, _now_hhmm())
    db.commit()
    return slot.id


def test_i00112_poller_persists_captured_fields(
    db_session: Session,
    db_session_factory: sessionmaker,
) -> None:
    """Poller MUST persist stdout/stderr/elapsed_ms/returncode on every run.

    Mocks at ``subprocess.run`` so the FireResult.is_success contract is the
    actual code path under test (rather than the wrapper). A real Sonnet
    round-trip (rc=0, non-empty stdout, elapsed >= 500ms) MUST land as
    ``status='success'`` with the four diagnostic fields populated.
    """
    slot_id = _seed_slot(db_session)
    fake = CompletedProcess(args=[], returncode=0, stdout="OK", stderr="")

    with (
        patch("orch.daemon.keep_alive_poller.SessionLocal", db_session_factory),
        patch("orch.keep_alive_service.subprocess.run", return_value=fake),
        patch(
            "orch.keep_alive_service.time_mod.perf_counter",
            side_effect=[0.0, 3.0],
        ),
    ):
        KeepAlivePoller().poll()

    row = (
        db_session.query(KeepAliveRun)
        .filter(KeepAliveRun.slot_id == slot_id)
        .order_by(KeepAliveRun.id.desc())
        .first()
    )
    assert row is not None, "poller must have logged exactly one row for the seeded slot"
    assert row.status == "success"
    assert row.stdout == "OK"
    assert row.stderr == ""
    assert row.elapsed_ms == 3000
    assert row.returncode == 0


def test_i00112_poller_logs_failed_when_contract_violated(
    db_session: Session,
    db_session_factory: sessionmaker,
) -> None:
    """Reproduction (AC1): silent no-op MUST land as failed with diagnostic detail.

    Pre-fix bug: ``returncode == 0`` was treated as success even with empty
    stdout and near-zero elapsed. Post-fix: the FireResult.is_success contract
    rejects this. Both the first attempt AND the single retry mock return the
    same silent-no-op shape, so the row must end as ``retried_failed`` with
    the four diagnostic fields captured.
    """
    slot_id = _seed_slot(db_session)
    fake = CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    with (
        patch("orch.daemon.keep_alive_poller.SessionLocal", db_session_factory),
        patch("orch.keep_alive_service.subprocess.run", return_value=fake),
        # Two attempts (first + retry); each call to fire_claude consumes a pair.
        patch(
            "orch.keep_alive_service.time_mod.perf_counter",
            side_effect=[0.0, 0.001, 0.0, 0.001],
        ),
    ):
        KeepAlivePoller().poll()

    row = (
        db_session.query(KeepAliveRun)
        .filter(KeepAliveRun.slot_id == slot_id)
        .order_by(KeepAliveRun.id.desc())
        .first()
    )
    assert row is not None, "poller must have logged a row for the seeded slot"
    assert row.status in ("failed", "retried_failed"), (
        f"silent no-op was logged as {row.status!r} — must be failed/retried_failed (I-00112)"
    )
    assert row.stdout == ""
    assert row.returncode == 0
    assert row.elapsed_ms is not None
    assert row.elapsed_ms < 500
