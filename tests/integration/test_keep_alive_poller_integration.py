"""Integration tests for KeepAlivePoller against a real PostgreSQL testcontainer.

The poller's only DB pathway is via ``orch.db.session.SessionLocal``, so each
test patches that name (in the poller's module) to a sessionmaker bound to the
per-test clone. ``fire_claude`` is patched at the module level to avoid actually
shelling out to the ``claude`` CLI.

Regression coverage: a DetachedInstanceError bug lived in production from
2026-05-01 through 2026-05-17 because the poller passed ORM instances forward
across session boundaries. ``SessionLocal``'s default ``expire_on_commit=True``
expired every attribute on those instances at commit; the session then closed
and accessing ``slot.id`` from ``_log_run`` raised DetachedInstanceError. Every
fire_claude success was masked as an "unexpected error" and ``keep_alive_runs``
stayed empty for 17 days. The first test below — ``test_poll_logs_success_run``
— exercises that exact path with a real DB and would have failed on the old
implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from freezegun import freeze_time

from orch.daemon.keep_alive_poller import KeepAlivePoller
from orch.db.models import KeepAliveRun, KeepAliveSlot
from orch.keep_alive_service import add_slot, get_config

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


def _now_hhmm() -> str:
    return datetime.now().strftime("%H:%M")  # noqa: DTZ005 — matches poller's local-time intent


def _seed_slot(db: Session, time_hhmm: str | None = None) -> KeepAliveSlot:
    """Insert config + slot inside the test session and commit."""
    get_config(db)
    db.flush()
    slot = add_slot(db, time_hhmm or _now_hhmm())
    db.commit()
    return slot


class TestKeepAlivePollerEndToEnd:
    """End-to-end poll() cycle against a real DB."""

    def test_poll_logs_success_run(
        self,
        db_session: Session,
        db_session_factory: sessionmaker,
    ) -> None:
        """fire_claude succeeds → exactly one KeepAliveRun(status='success') is persisted.

        Regression: on the pre-fix poller this raised DetachedInstanceError in
        ``_log_run`` (the ORM instance was detached + expired after the loader
        session closed) and no run was ever written.
        """
        slot = _seed_slot(db_session)
        slot_id = slot.id

        with (
            patch("orch.daemon.keep_alive_poller.SessionLocal", db_session_factory),
            patch(
                "orch.daemon.keep_alive_poller.fire_claude",
                return_value=(True, None),
            ) as mock_fire,
        ):
            KeepAlivePoller().poll()

        # The subprocess was invoked exactly once (no retry on success).
        assert mock_fire.call_count == 1

        # The run is in the DB with the right shape.
        runs = (
            db_session.query(KeepAliveRun)
            .filter(KeepAliveRun.slot_id == slot_id)
            .order_by(KeepAliveRun.fired_at.desc())
            .all()
        )
        assert len(runs) == 1, (
            "Expected exactly one logged run after a successful poll. "
            "An empty list means the poller silently swallowed an exception "
            "(DetachedInstanceError on the slot ORM instance) — the exact "
            "regression this test guards against."
        )
        assert runs[0].status == "success"
        assert runs[0].slot_time == slot.time_hhmm
        assert runs[0].error is None

    def test_poll_retry_success_logs_retried_success(
        self,
        db_session: Session,
        db_session_factory: sessionmaker,
    ) -> None:
        """First fire_claude fails → second succeeds → one run with status='retried_success'."""
        slot = _seed_slot(db_session)
        slot_id = slot.id

        with (
            patch("orch.daemon.keep_alive_poller.SessionLocal", db_session_factory),
            patch(
                "orch.daemon.keep_alive_poller.fire_claude",
                side_effect=[(False, "boom"), (True, None)],
            ) as mock_fire,
        ):
            KeepAlivePoller().poll()

        assert mock_fire.call_count == 2

        runs = db_session.query(KeepAliveRun).filter(KeepAliveRun.slot_id == slot_id).all()
        assert len(runs) == 1
        assert runs[0].status == "retried_success"
        assert runs[0].error is None

    def test_poll_double_failure_logs_retried_failed_with_combined_error(
        self,
        db_session: Session,
        db_session_factory: sessionmaker,
    ) -> None:
        """Both fires fail → one run with status='retried_failed' and both errors captured."""
        slot = _seed_slot(db_session)
        slot_id = slot.id

        with (
            patch("orch.daemon.keep_alive_poller.SessionLocal", db_session_factory),
            patch(
                "orch.daemon.keep_alive_poller.fire_claude",
                side_effect=[(False, "first-err"), (False, "second-err")],
            ) as mock_fire,
        ):
            KeepAlivePoller().poll()

        assert mock_fire.call_count == 2

        runs = db_session.query(KeepAliveRun).filter(KeepAliveRun.slot_id == slot_id).all()
        assert len(runs) == 1
        assert runs[0].status == "retried_failed"
        assert runs[0].error is not None
        assert "first-err" in runs[0].error
        assert "second-err" in runs[0].error

    def test_poll_skips_slot_already_run_today(
        self,
        db_session: Session,
        db_session_factory: sessionmaker,
    ) -> None:
        """A slot with a prior success today is NOT re-fired.

        Indirectly proves run logging closes the loop: with the bug, runs never
        landed, so get_due_slots kept returning the same slot every cycle.

        Time is frozen at local-noon and ``fired_at`` is stamped at the same
        instant in UTC so the test is wall-clock independent. The previous
        version relied on the server default (``fired_at = now()`` in UTC) and
        compared it against ``today_date`` from naïve ``datetime.now()`` in
        local time. Around UTC midnight (e.g., 00:35 WEST CI run on
        2026-05-18) the two dates differ by one day, ``func.date(fired_at)``
        in ``get_due_slots`` misses the seeded run, and the slot appears due.
        """
        frozen_now = datetime(2026, 5, 18, 12, 0, 0)  # noqa: DTZ001 — frozen local-time anchor
        with freeze_time(frozen_now):
            slot = _seed_slot(db_session)
            run = KeepAliveRun(
                slot_id=slot.id,
                slot_time=slot.time_hhmm,
                status="success",
                fired_at=frozen_now.replace(tzinfo=UTC),
            )
            db_session.add(run)
            db_session.commit()

            with (
                patch("orch.daemon.keep_alive_poller.SessionLocal", db_session_factory),
                patch(
                    "orch.daemon.keep_alive_poller.fire_claude",
                    return_value=(False, None),
                ) as mock_fire,
            ):
                KeepAlivePoller().poll()

        mock_fire.assert_not_called()

        runs = db_session.query(KeepAliveRun).filter(KeepAliveRun.slot_id == slot.id).all()
        assert len(runs) == 1  # only the pre-seeded one

    def test_poll_processes_multiple_slots_independently(
        self,
        db_session: Session,
        db_session_factory: sessionmaker,
    ) -> None:
        """Two due slots → both processed and logged regardless of iteration order.

        Slots are processed via snapshotted ``(id, time_hhmm)`` tuples; on the
        pre-fix code the first iteration would raise DetachedInstanceError
        inside ``_log_run`` and the loop's bare ``except`` would catch and move
        on — but the second iteration would suffer the same crash, so neither
        run would ever land in the DB. Two recorded runs is the goal.

        ``get_due_slots`` does not ``ORDER BY`` so iteration order is unspecified;
        keep this assertion order-agnostic.
        """
        now = datetime.now()  # noqa: DTZ005 — match poller's local-time semantics
        # Two distinct minutes inside the 30-min lookback window.
        t1 = now.strftime("%H:%M")
        t2 = (now - timedelta(minutes=5)).strftime("%H:%M")
        if t1 == t2:  # exactly on the 5-minute mark; nudge further back
            t2 = (now - timedelta(minutes=10)).strftime("%H:%M")

        get_config(db_session)
        db_session.flush()
        slot_a = add_slot(db_session, t1)
        slot_b = add_slot(db_session, t2)
        db_session.commit()
        slot_a_id, slot_b_id = slot_a.id, slot_b.id

        with (
            patch("orch.daemon.keep_alive_poller.SessionLocal", db_session_factory),
            patch(
                "orch.daemon.keep_alive_poller.fire_claude",
                return_value=(True, None),
            ) as mock_fire,
        ):
            KeepAlivePoller().poll()

        # One call per slot (no retries on success).
        assert mock_fire.call_count == 2

        run_a = db_session.query(KeepAliveRun).filter(KeepAliveRun.slot_id == slot_a_id).one()
        run_b = db_session.query(KeepAliveRun).filter(KeepAliveRun.slot_id == slot_b_id).one()
        assert run_a.status == "success"
        assert run_b.status == "success"
        assert {run_a.slot_time, run_b.slot_time} == {t1, t2}

    def test_poll_threads_configured_model_into_fire_claude(
        self,
        db_session: Session,
        db_session_factory: sessionmaker,
    ) -> None:
        """The model stored in KeepAliveConfig MUST reach fire_claude.

        Regression: from F-00074 (2026-05-15) through 2026-05-19 the poller
        called ``fire_claude(message)`` with no model argument, and
        ``fire_claude`` ran ``claude -p <msg>`` with no ``--model`` flag — so
        every keep-alive fired against the user's default CLI model (Opus on
        the dev host) instead of the Sonnet model the user configured. The
        scheduler exists to anchor a 5-hour usage window on a specific model,
        so silently running the wrong model defeats the feature entirely.
        """
        get_config(db_session)
        cfg = get_config(db_session)
        cfg.model = "claude-sonnet-4-6"
        db_session.flush()
        _seed_slot(db_session)

        with (
            patch("orch.daemon.keep_alive_poller.SessionLocal", db_session_factory),
            patch(
                "orch.daemon.keep_alive_poller.fire_claude",
                return_value=(True, None),
            ) as mock_fire,
        ):
            KeepAlivePoller().poll()

        assert mock_fire.call_count == 1
        # Accept either positional (message, model) or keyword passing.
        args, kwargs = mock_fire.call_args
        model_arg = args[1] if len(args) >= 2 else kwargs.get("model")
        assert model_arg == "claude-sonnet-4-6", (
            f"Expected configured model to be threaded into fire_claude; "
            f"got args={args!r} kwargs={kwargs!r}"
        )
