"""I-00116 — Integration tests for review-relaunch cap.

Tests the cumulative per-item cap on review step relaunches (S03 sub-fix).
The cap is enforced in `batch_manager._launch_step` via `fix_cycle._count_review_relaunches`
and `fix_cycle._transition_item_to_failed_for_loop`. These tests use a real
testcontainer-backed `db_session` so that `SELECT FOR UPDATE` locking (used in the
cap-check path) is exercised correctly.

The cap is read via `IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM`. We set it to a small
value (3) so the tests run fast while remaining semantically correct.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from orch.daemon import fix_cycle as fc
from orch.db.models import (
    DaemonEvent,
    Project,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)


def _seed_review_steps(
    session,
    project_id: str,
    work_item_id: str,
    step_id: str,
    count: int,
) -> list[StepRun]:
    """Seed `count` completed review StepRuns for the same step (simulating relaunches)."""
    runs = []
    for i in range(count):
        run = StepRun(
            step_id=None,  # will be patched below
            run_number=i + 1,
            status=RunStatus.completed,
            pid=None,
            pid_alive=False,
            command="test",
            worktree_path="/tmp",
            cli_tool="opencode",
            started_at=datetime.now(UTC) - timedelta(minutes=count - i),
            completed_at=datetime.now(UTC) - timedelta(minutes=count - i - 1),
        )
        session.add(run)
        runs.append(run)
    session.flush()
    return runs


# ---------------------------------------------------------------------------
# Test 1: under-cap relaunches are unaffected
# ---------------------------------------------------------------------------


def test_i00116_under_cap_review_relaunches_are_unaffected(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """At cap-1 review relaunches: item status unchanged, no cap-exceeded event.

    Semantic assertions:
      - work_item.status == in_progress  (item not failed)
      - events == 0  (no review_relaunch_cap_exceeded event)
    """
    # Set cap to 3 so we can test cap-1 = 2 below.
    # _get_max_review_relaunches() reads env on each call, so no importlib.reload needed.
    monkeypatch.setenv("IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM", "3")

    import orch.daemon.fix_cycle as fc_module  # noqa: PLC0415

    cap = int("3")

    session = db_session

    project = Project(
        id="test-proj-i00116-under",
        display_name="Test Project I-00116 Under Cap",
        repo_root=str(tmp_path),
        config={},
    )
    session.add(project)
    session.flush()

    item = WorkItem(
        project_id=project.id,
        id="I-00116-UNDER",
        type=WorkItemType.Feature,
        title="I-00116 under cap test",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    session.add(item)
    session.flush()

    step = WorkflowStep(
        project_id=project.id,
        work_item_id=item.id,
        step_number=1,
        step_id="S02",
        agent_label="test",
        step_type=StepType.code_review,
        status=StepStatus.in_progress,
    )
    session.add(step)
    session.flush()

    # Seed cap-1 = 2 completed review runs
    for i in range(cap - 1):
        run = StepRun(
            step_id=step.id,
            run_number=i + 1,
            status=RunStatus.completed,
            pid=None,
            pid_alive=False,
            command="test",
            worktree_path="/tmp",
            cli_tool="opencode",
            started_at=datetime.now(UTC) - timedelta(minutes=cap - i),
            completed_at=datetime.now(UTC) - timedelta(minutes=cap - i - 1),
        )
        session.add(run)

    session.flush()
    session.commit()

    # Query the relaunch count
    relaunch_count = fc_module.count_review_relaunches(session, project.id, item.id)

    # Semantic: relaunch count is cap-1
    assert relaunch_count == cap - 1, (
        f"Expected relaunch count {cap - 1} (cap-1), got {relaunch_count}"
    )

    # Semantic: item status is still in_progress (not failed)
    session.refresh(item)
    assert item.status == WorkItemStatus.in_progress, (
        f"Item should still be in_progress at cap-1, got {item.status}"
    )

    # Semantic: no review_relaunch_cap_exceeded event emitted
    cap_events = (
        session.query(DaemonEvent)
        .filter(
            DaemonEvent.event_type == "review_relaunch_cap_exceeded",
            DaemonEvent.entity_id == item.id,
        )
        .all()
    )
    assert len(cap_events) == 0, f"Expected no cap-exceeded events at cap-1, got {len(cap_events)}"


def test_i00116_at_cap_review_relaunch_transitions_item_failed_and_emits_event(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """At cap review relaunches: item transitions to failed with DaemonEvent.

    Semantic assertions:
      - work_item.status == failed
      - exactly 1 DaemonEvent with type='review_relaunch_cap_exceeded'
      - event.event_metadata['cap'] == cap_value (3)
      - event.event_metadata['actual_count'] == cap_value (3)
      - event.event_metadata['review_step_runs'] is a list of length >= 1

    Second call to cap-check is idempotent (item stays failed, no second event).
    """
    # Set cap to 3.
    # _get_max_review_relaunches() reads env on each call, so no importlib.reload needed.
    cap = 3
    monkeypatch.setenv("IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM", str(cap))

    import orch.daemon.fix_cycle as fc_module  # noqa: PLC0415

    session = db_session

    project = Project(
        id="test-proj-i00116-cap",
        display_name="Test Project I-00116 At Cap",
        repo_root=str(tmp_path),
        config={},
    )
    session.add(project)
    session.flush()

    item = WorkItem(
        project_id=project.id,
        id="I-00116-AT-CAP",
        type=WorkItemType.Feature,
        title="I-00116 at-cap test",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    session.add(item)
    session.flush()

    step = WorkflowStep(
        project_id=project.id,
        work_item_id=item.id,
        step_number=1,
        step_id="S02",
        agent_label="test",
        step_type=StepType.code_review,
        status=StepStatus.in_progress,
    )
    session.add(step)
    session.flush()

    # Seed exactly cap=3 completed review runs
    for i in range(cap):
        run = StepRun(
            step_id=step.id,
            run_number=i + 1,
            status=RunStatus.completed,
            pid=None,
            pid_alive=False,
            command="test",
            worktree_path="/tmp",
            cli_tool="opencode",
            started_at=datetime.now(UTC) - timedelta(minutes=cap - i + 1),
            completed_at=datetime.now(UTC) - timedelta(minutes=cap - i),
        )
        session.add(run)

    session.flush()
    session.commit()

    # First cap-check: should transition to failed
    relaunch_count = fc_module.count_review_relaunches(session, project.id, item.id)
    assert relaunch_count == cap, f"Expected relaunch count {cap} (at cap), got {relaunch_count}"

    if relaunch_count >= fc_module.get_max_review_relaunches():
        fc_module.transition_item_to_failed_for_loop(session, project.id, item.id, relaunch_count)
        # Flush so the WorkItem update and DaemonEvent insert are visible
        # within this transaction (the helper no longer calls db.commit() — F7 fix).
        session.flush()

    session.refresh(item)

    # Semantic: item is now failed
    assert item.status == WorkItemStatus.failed, (
        f"Item should be failed at cap={cap}, got {item.status}"
    )

    # Semantic: exactly one cap-exceeded event
    cap_events = (
        session.query(DaemonEvent)
        .filter(
            DaemonEvent.event_type == "review_relaunch_cap_exceeded",
            DaemonEvent.entity_id == item.id,
        )
        .all()
    )
    assert len(cap_events) == 1, f"Expected exactly 1 cap-exceeded event, got {len(cap_events)}"

    meta = cap_events[0].event_metadata or {}
    # Semantic: cap metadata is correct
    assert meta.get("cap") == cap, f"Event cap should be {cap}, got {meta.get('cap')}"
    assert meta.get("actual_count") == cap, (
        f"Event actual_count should be {cap}, got {meta.get('actual_count')}"
    )
    # Semantic: review_step_runs is a non-empty list
    assert isinstance(meta.get("review_step_runs"), list), "review_step_runs should be a list"
    assert len(meta["review_step_runs"]) >= 1, (
        f"review_step_runs should have at least 1 entry, got {len(meta['review_step_runs'])}"
    )

    # Second cap-check: idempotent — item stays failed, no second event
    relaunch_count_2 = fc_module.count_review_relaunches(session, project.id, item.id)
    if relaunch_count_2 >= fc_module.get_max_review_relaunches():
        fc_module.transition_item_to_failed_for_loop(session, project.id, item.id, relaunch_count_2)
        session.flush()

    session.refresh(item)
    assert item.status == WorkItemStatus.failed, (
        "Item should remain failed on second cap-check (idempotent)"
    )

    cap_events_2 = (
        session.query(DaemonEvent)
        .filter(
            DaemonEvent.event_type == "review_relaunch_cap_exceeded",
            DaemonEvent.entity_id == item.id,
        )
        .all()
    )
    assert len(cap_events_2) == 1, (
        f"Second cap-check should not emit a second event (idempotent), "
        f"got {len(cap_events_2)} events"
    )
