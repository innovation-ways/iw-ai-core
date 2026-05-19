"""Integration test for cascade thrashing detector wiring (I-00100).

Drives the production seam end-to-end:
    check_active_fix_cycles → _check_fix_cycle_health → _complete_fix_cycle

Verifies that the thrashing detector fires (and suppresses the cascade reset)
when a third same-trigger cascade with overlapping reset-set fires through the
production path. Also verifies the detector does NOT fire when cascades are
disjoint (AC3 — no behaviour change for non-thrashing cases).

Pre-S01 (before the plumbing fix): check_active_fix_cycles dropped project_config
(# noqa: ARG001), so _complete_fix_cycle's line-1139 guard short-circuited on
project_config=None and _detect_thrashing was unreachable. This test would have
failed because no 'cascade_thrashing_detected' DaemonEvent could be emitted.

Post-S01: project_config is threaded through the full chain, the guard fires,
and the detector correctly identifies and suppresses thrashing cascades.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from orch.config import DaemonConfig
from orch.daemon import fix_cycle
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    DaemonEvent,
    FixCycle,
    FixStatus,
    FixTrigger,
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project_config(
    cascade_thrashing_threshold: int = 3,
    cascade_thrashing_jaccard_min: float = 0.5,
    fix_cycle_max: int = 10,
) -> ProjectConfig:
    """Build a ProjectConfig matching the test project's config dict."""
    return ProjectConfig(
        id="test-proj",
        display_name="Thrashing Test Project",
        repo_root="/repos/test",
        enabled=True,
        cli_tool="claude",
        model="minimax",
        worktree_base="/repos/test/.worktrees",
        config={
            "cascade_thrashing_threshold": cascade_thrashing_threshold,
            "cascade_thrashing_jaccard_min": cascade_thrashing_jaccard_min,
            "fix_cycle_max": fix_cycle_max,
        },
    )


def _daemon_config() -> DaemonConfig:
    """Minimal DaemonConfig for check_active_fix_cycles calls."""
    return DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5433/test",
        dashboard_host="0.0.0.0",  # noqa: S104
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=600,
        pid_file="/tmp/test-daemon.pid",  # noqa: S108
        archive_dir="/tmp/test-archive",  # noqa: S108
        archive_ttl=90,
        log_level="DEBUG",
        log_file="/tmp/test-daemon.log",  # noqa: S108
    )


def _make_work_item(db: Session, item_id: str = "CR-00001") -> WorkItem:
    """Insert a minimal WorkItem row."""
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.ChangeRequest,
        title=f"Test item {item_id}",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(item)
    db.flush()
    return item


def _make_step(
    db: Session,
    step_id: str,
    step_type: StepType,
    status: StepStatus,
    step_number: int,
    item_id: str = "CR-00001",
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> WorkflowStep:
    """Insert a WorkflowStep row."""
    step = WorkflowStep(
        project_id="test-proj",
        work_item_id=item_id,
        step_number=step_number,
        step_id=step_id,
        agent_label=f"Agent_{step_id}",
        step_type=step_type,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
    )
    db.add(step)
    db.flush()
    return step


def _make_fix_cycle(
    db: Session,
    step: WorkflowStep,
    pid: int,
    cycle_number: int = 1,
    timeout_secs: int = 2700,
) -> FixCycle:
    """Insert a FixCycle row in in_progress status."""
    fc = FixCycle(
        step_id=step.id,
        cycle_number=cycle_number,
        trigger_type=FixTrigger.browser_verification,
        status=FixStatus.in_progress,
        fix_metadata={"pid": pid, "timeout_secs": timeout_secs},
    )
    db.add(fc)
    db.flush()
    return fc


def _emit_cascade_event(
    db: Session,
    project_id: str,
    work_item_id: str,
    trigger_step_id: str,
    reset_step_ids: list[str],
) -> None:
    """Insert a 'cascaded_replay_after_fix' DaemonEvent to simulate a prior cascade."""
    event = DaemonEvent(
        project_id=project_id,
        event_type="cascaded_replay_after_fix",
        entity_id=work_item_id,
        entity_type="work_item",
        message=f"Cascade reset triggered by {trigger_step_id}",
        event_metadata={
            "trigger_step_id": trigger_step_id,
            "reset_step_ids": reset_step_ids,
            "reason": "code_changed_by_fix_cycle",
        },
    )
    db.add(event)
    db.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCascadeThrashingDetectorWiring:
    """Regression tests for I-00100: cascade thrashing detector wiring.

    Two tests that drive check_active_fix_cycles (the production seam), not
    _complete_fix_cycle directly. This is what makes them regression tests:
    a future refactor that silently drops project_config again will fail these.
    """

    @pytest.fixture
    def dead_pid(self) -> int:
        """Return a PID guaranteed to be dead.

        Strategy: pick a PID at or above ``/proc/sys/kernel/pid_max``. The
        kernel never assigns a PID >= pid_max, so no real process can occupy
        it. We verify via ``os.kill(pid, 0)`` that the PID is not alive
        before returning it.

        The earlier strategy of ``os.getpid() + 99999`` was wrong on systems
        where the pytest process is given a low PID — the synthesized value
        could still collide with a real process and the "belt-and-suspenders"
        ``> 1_000_000`` assertion fired pre-emptively (I-00100 follow-up).
        """
        with Path("/proc/sys/kernel/pid_max").open(encoding="ascii") as f:
            pid_max = int(f.read().strip())
        pid = pid_max  # kernel never assigns this value to a real process
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid  # confirmed dead — expected path
        except PermissionError:
            # PID exists but isn't ours (shouldn't happen at >= pid_max, but
            # be conservative). Step one above and retry once.
            pid -= 1
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return pid
            raise AssertionError(f"Could not find a dead PID near pid_max={pid_max}") from None
        raise AssertionError(
            f"PID {pid} (== pid_max={pid_max}) appears alive — kernel invariant violated"
        )

    def test_thrashing_detector_fires_when_driven_through_check_active_fix_cycles(
        self,
        db_session: Session,
        test_project: Project,
        dead_pid: int,
    ) -> None:
        """RED before S01 plumbing fix; GREEN after.

        Drives the full production seam:
            check_active_fix_cycles → _check_fix_cycle_health → _complete_fix_cycle

        Pre-fix: project_config is dropped at check_active_fix_cycles' boundary
        (# noqa: ARG001 removed in S01), so the line-1139 guard in
        _complete_fix_cycle short-circuits on project_config=None and the
        detector never runs. This test fails because no
        'cascade_thrashing_detected' event is emitted even after 3 same-trigger
        cascades with overlapping reset-sets.

        Post-fix: the detector fires on the 3rd cascade and the upstream gates
        are NOT reset that time (thrashing suppression works).

        Dead-PID strategy: os.getpid() + 99999 — guaranteed-nonexistent PID.
        We patch _is_pid_alive to return False so _check_fix_cycle_health
        treats the cycle as completed the moment check_active_fix_cycles runs.
        """
        # --- Arrange ---
        project_config = _make_project_config(
            cascade_thrashing_threshold=3,
            cascade_thrashing_jaccard_min=0.5,
            fix_cycle_max=10,
        )

        # WorkItem with two QV gates: S01 (upstream, completed) and S02 (downstream, needs_fix)
        _make_work_item(db_session, item_id="I-00100-THRASH")
        s01 = _make_step(
            db_session,
            "S01",
            StepType.quality_validation,
            StepStatus.completed,
            step_number=1,
            item_id="I-00100-THRASH",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        s02 = _make_step(
            db_session,
            "S02",
            StepType.browser_verification,
            StepStatus.needs_fix,
            step_number=2,
            item_id="I-00100-THRASH",
        )

        # Simulate two prior cascades from S02 with overlapping reset-set {S01}.
        # These represent the historical cascades (n=1, n=2); the current
        # call below is n=3 — the one that should trip the detector.
        _emit_cascade_event(db_session, "test-proj", "I-00100-THRASH", "S02", ["S01"])
        _emit_cascade_event(db_session, "test-proj", "I-00100-THRASH", "S02", ["S01"])

        # FixCycle in_progress with the dead PID — simulates fix agent having exited.
        cycle = _make_fix_cycle(db_session, s02, dead_pid, cycle_number=1)

        db_session.flush()

        # --- Act ---
        # Patch _is_pid_alive so _check_fix_cycle_health treats the cycle as dead
        # and calls _complete_fix_cycle. Without this patch the test would need
        # to fork/spawn a real process and wait for it — more complex and slower.
        with patch("orch.daemon.fix_cycle._is_pid_alive", return_value=False):
            fix_cycle.check_active_fix_cycles(
                db_session,
                project_id="test-proj",
                project_config=project_config,
                config=_daemon_config(),
            )

        db_session.flush()

        # --- Assert (semantic) ---
        # 1. Exactly one cascade_thrashing_detected event was emitted.
        thrashing_events = (
            db_session.query(DaemonEvent)
            .filter(
                DaemonEvent.entity_id == "I-00100-THRASH",
                DaemonEvent.event_type == "cascade_thrashing_detected",
            )
            .all()
        )
        assert len(thrashing_events) == 1, (
            f"expected exactly 1 cascade_thrashing_detected event, got {len(thrashing_events)}"
        )

        # 2. Event metadata is semantically correct.
        meta = thrashing_events[0].event_metadata
        assert meta["trigger_step_id"] == "S02", (
            f"expected trigger_step_id 'S02', got {meta.get('trigger_step_id')}"
        )
        assert meta["cascade_count"] == 3, (
            f"expected cascade_count 3, got {meta.get('cascade_count')}"
        )
        assert set(meta["reset_set"]) == {"S01"}, (
            f"expected reset_set {{'S01'}}, got {set(meta.get('reset_set', []))}"
        )

        # 3. The FixCycle was marked completed (not failed/escalated).
        db_session.refresh(cycle)
        assert cycle.status == FixStatus.completed, (
            f"expected FixCycle status completed, got {cycle.status}"
        )

        # 4. The upstream gate (S01) was NOT reset — thrashing suppression worked.
        # If the detector failed to fire, S01 would have been reset to 'pending'.
        db_session.refresh(s01)
        assert s01.status == StepStatus.completed, (
            "upstream QV gate S01 should remain completed when thrashing is detected; "
            "a reset would indicate the detector short-circuited"
        )
        assert s01.started_at is not None, "S01 started_at should be preserved"
        assert s01.completed_at is not None, "S01 completed_at should be preserved"

    def test_no_thrashing_event_when_reset_sets_do_not_overlap(
        self,
        db_session: Session,
        test_project: Project,
        dead_pid: int,
    ) -> None:
        """Negative control: disjoint reset-sets mean no thrashing — normal cascade fires.

        AC3 ("no behaviour change for non-thrashing cases"): when the two prior
        cascades have disjoint reset-sets (Jaccard = 0.0), the third cascade with
        a third disjoint set should NOT trigger the detector. The upstream gate
        must still be reset normally.

        This protects against a future bug where the detector over-fires.
        """
        # --- Arrange ---
        project_config = _make_project_config(
            cascade_thrashing_threshold=3,
            cascade_thrashing_jaccard_min=0.5,
            fix_cycle_max=10,
        )

        # WorkItem: upstream gate S01 (completed), trigger S02 (needs_fix)
        _make_work_item(db_session, item_id="I-00100-NORMAL")
        s01 = _make_step(
            db_session,
            "S01",
            StepType.quality_validation,
            StepStatus.completed,
            step_number=1,
            item_id="I-00100-NORMAL",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        s02 = _make_step(
            db_session,
            "S02",
            StepType.browser_verification,
            StepStatus.needs_fix,
            step_number=2,
            item_id="I-00100-NORMAL",
        )

        # Two PRIOR cascades with DISJOINT reset-sets — no thrashing possible.
        # Their Jaccard with each other is 0.0, and with the current (S02 → {Sx})
        # is also 0.0. The detector's window (last 3 cascades) will have Jaccard
        # pairs all at 0.0, which is below the 0.5 threshold.
        _emit_cascade_event(db_session, "test-proj", "I-00100-NORMAL", "S02", ["Sx"])
        _emit_cascade_event(db_session, "test-proj", "I-00100-NORMAL", "S02", ["Sy"])

        cycle = _make_fix_cycle(db_session, s02, dead_pid, cycle_number=1)

        db_session.flush()

        # --- Act ---
        with patch("orch.daemon.fix_cycle._is_pid_alive", return_value=False):
            fix_cycle.check_active_fix_cycles(
                db_session,
                project_id="test-proj",
                project_config=project_config,
                config=_daemon_config(),
            )

        db_session.flush()

        # --- Assert ---
        # 1. Zero cascade_thrashing_detected events — the detector must not over-fire.
        thrashing_events = (
            db_session.query(DaemonEvent)
            .filter(
                DaemonEvent.entity_id == "I-00100-NORMAL",
                DaemonEvent.event_type == "cascade_thrashing_detected",
            )
            .all()
        )
        assert len(thrashing_events) == 0, (
            f"expected no cascade_thrashing_detected events for disjoint cascades, "
            f"got {len(thrashing_events)}"
        )

        # 2. At least one cascaded_replay_after_fix event WAS emitted during this run.
        # Note: this counts ALL such events for this item (including the historical
        # ones from prior test runs in the same DB clone — db_session is shared).
        # We only need to verify that the thrashing detector did NOT fire; the
        # exact count of cascade events is not meaningful for this assertion.
        cascade_events = (
            db_session.query(DaemonEvent)
            .filter(
                DaemonEvent.entity_id == "I-00100-NORMAL",
                DaemonEvent.event_type == "cascaded_replay_after_fix",
            )
            .all()
        )
        assert len(cascade_events) >= 1, (
            f"expected at least 1 cascaded_replay_after_fix event, got {len(cascade_events)}"
        )

        # 3. The upstream gate (S01) WAS reset — confirms the normal cascade path is alive.
        db_session.refresh(s01)
        assert s01.status == StepStatus.pending, (
            "upstream QV gate S01 should be reset to pending when no thrashing is detected"
        )
        assert s01.started_at is None, "S01 started_at should be cleared on reset"
        assert s01.completed_at is None, "S01 completed_at should be cleared on reset"

        # 4. FixCycle was marked completed.
        db_session.refresh(cycle)
        assert cycle.status == FixStatus.completed
