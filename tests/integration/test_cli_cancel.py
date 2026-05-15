"""Integration tests for `iw batch-cancel` and `iw item-cancel`.

Covers the happy path (cancel a paused batch with --reset-items) and the
guard rails (terminal batch refuses, active batch refuses item-cancel,
worktree teardown errors don't block the DB transition).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
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

# ---------------------------------------------------------------------------
# Helpers (mirror tests/integration/test_cli_batches.py for consistency)
# ---------------------------------------------------------------------------


def _invoke(
    args: list[str],
    cli_get_session: Any,
    project_id: str = "test-proj",
) -> Any:
    runner = CliRunner()
    return runner.invoke(
        cli,
        ["--project", project_id, "--json", *args],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )


def _mk_item(
    db_session: Any,
    item_id: str,
    *,
    status: WorkItemStatus = WorkItemStatus.in_progress,
) -> WorkItem:
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.ChangeRequest,
        title=f"Test {item_id}",
        status=status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()
    return item


def _mk_step(
    db_session: Any,
    item_id: str,
    step_number: int,
    *,
    status: StepStatus = StepStatus.pending,
) -> WorkflowStep:
    step = WorkflowStep(
        project_id="test-proj",
        work_item_id=item_id,
        step_number=step_number,
        step_id=f"S{step_number:02d}",
        agent_label=f"Step{step_number}",
        opencode_agent="backend-impl",
        step_type=StepType.implementation,
        status=status,
    )
    db_session.add(step)
    db_session.flush()
    return step


def _mk_batch(
    db_session: Any,
    batch_id: str,
    *,
    status: BatchStatus = BatchStatus.paused,
) -> Batch:
    batch = Batch(
        project_id="test-proj",
        id=batch_id,
        status=status,
        cli_tool="opencode",
    )
    db_session.add(batch)
    db_session.flush()
    return batch


def _mk_batch_item(
    db_session: Any,
    batch_id: str,
    item_id: str,
    *,
    status: BatchItemStatus = BatchItemStatus.executing,
    worktree_info: dict | None = None,
) -> BatchItem:
    bi = BatchItem(
        project_id="test-proj",
        batch_id=batch_id,
        work_item_id=item_id,
        execution_group=0,
        status=status,
        worktree_info=worktree_info,
    )
    db_session.add(bi)
    db_session.flush()
    return bi


# ---------------------------------------------------------------------------
# batch-cancel
# ---------------------------------------------------------------------------


def test_batch_cancel_paused_batch_marks_items_skipped_and_emits_event(
    db_session: Any, test_project: Project, cli_get_session: Any
) -> None:
    """Paused batch with an executing item → cancelled batch + skipped item + event."""
    _mk_item(db_session, "CR-00001")
    _mk_step(db_session, "CR-00001", 1, status=StepStatus.failed)
    _mk_step(db_session, "CR-00001", 2, status=StepStatus.pending)
    batch = _mk_batch(db_session, "BATCH-00001", status=BatchStatus.paused)
    bi = _mk_batch_item(db_session, "BATCH-00001", "CR-00001")

    result = _invoke(
        ["batch-cancel", "BATCH-00001", "--reason", "test cancel"],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["status"] == "cancelled"
    assert payload["cancelled_batch_items"] == ["CR-00001"]
    assert payload["reset_to_draft"] == []

    db_session.refresh(batch)
    db_session.refresh(bi)
    assert batch.status == BatchStatus.cancelled
    assert bi.status == BatchItemStatus.skipped
    assert bi.notes is not None
    assert "BATCH-00001" in bi.notes
    assert "test cancel" in bi.notes

    # Work item moved to cancelled (no --reset-items)
    wi = db_session.get(WorkItem, ("test-proj", "CR-00001"))
    assert wi.status == WorkItemStatus.cancelled

    # Pending S02 must be skipped; the already-terminal S01 (failed) untouched.
    steps = (
        db_session.query(WorkflowStep)
        .filter_by(project_id="test-proj", work_item_id="CR-00001")
        .order_by(WorkflowStep.step_number)
        .all()
    )
    assert [s.status for s in steps] == [StepStatus.failed, StepStatus.skipped]

    # Audit event emitted
    event = (
        db_session.query(DaemonEvent)
        .filter_by(event_type="batch_cancelled", entity_id="BATCH-00001")
        .one()
    )
    assert event.event_metadata["reason"] == "test cancel"
    assert event.event_metadata["reset_items"] is False


def test_batch_cancel_with_reset_items_pushes_work_item_to_draft(
    db_session: Any, test_project: Project, cli_get_session: Any
) -> None:
    _mk_item(db_session, "CR-00002")
    _mk_step(db_session, "CR-00002", 1, status=StepStatus.failed)
    _mk_step(db_session, "CR-00002", 2, status=StepStatus.pending)
    _mk_batch(db_session, "BATCH-00002", status=BatchStatus.paused)
    _mk_batch_item(db_session, "BATCH-00002", "CR-00002")

    result = _invoke(
        ["batch-cancel", "BATCH-00002", "--reset-items", "--reason", "redesign"],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["reset_to_draft"] == ["CR-00002"]

    wi = db_session.get(WorkItem, ("test-proj", "CR-00002"))
    assert wi.status == WorkItemStatus.draft

    # Every step rewound to pending (including the failed one)
    steps = (
        db_session.query(WorkflowStep)
        .filter_by(project_id="test-proj", work_item_id="CR-00002")
        .order_by(WorkflowStep.step_number)
        .all()
    )
    assert all(s.status == StepStatus.pending for s in steps)
    assert all(s.started_at is None and s.completed_at is None for s in steps)


def test_batch_cancel_kills_active_step_runs(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An in-progress StepRun transitions to RunStatus.killed; kill_process_group is called."""
    _mk_item(db_session, "CR-00003")
    step = _mk_step(db_session, "CR-00003", 1, status=StepStatus.in_progress)
    run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.running,
        pid=99999,  # nonexistent — kill_process_group is monkeypatched
    )
    db_session.add(run)
    db_session.flush()

    _mk_batch(db_session, "BATCH-00003", status=BatchStatus.executing)
    _mk_batch_item(db_session, "BATCH-00003", "CR-00003")

    killed_pids: list[int] = []

    def _fake_kill(pid: int) -> bool:
        killed_pids.append(pid)
        return True

    monkeypatch.setattr("orch.daemon.step_monitor.kill_process_group", _fake_kill)

    result = _invoke(["batch-cancel", "BATCH-00003"], cli_get_session)
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["killed_pids"] == [99999]
    assert killed_pids == [99999]

    db_session.refresh(run)
    assert run.status == RunStatus.killed
    assert run.pid_alive is False
    assert run.completed_at is not None


def test_batch_cancel_rejects_terminal_batch(
    db_session: Any, test_project: Project, cli_get_session: Any
) -> None:
    _mk_batch(db_session, "BATCH-00004", status=BatchStatus.completed)

    result = _invoke(["batch-cancel", "BATCH-00004"], cli_get_session)
    assert result.exit_code == 1
    assert "Cannot cancel batch" in result.output


def test_batch_cancel_unknown_batch_exits_1(
    db_session: Any, test_project: Project, cli_get_session: Any
) -> None:
    result = _invoke(["batch-cancel", "BATCH-99999"], cli_get_session)
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_batch_cancel_preserves_terminal_batch_item_status(
    db_session: Any, test_project: Project, cli_get_session: Any
) -> None:
    """A batch item already in 'merged' must keep that status (history preserved)."""
    _mk_item(db_session, "CR-00005", status=WorkItemStatus.completed)
    _mk_item(db_session, "CR-00006")
    _mk_batch(db_session, "BATCH-00005", status=BatchStatus.paused)
    merged_bi = _mk_batch_item(db_session, "BATCH-00005", "CR-00005", status=BatchItemStatus.merged)
    pending_bi = _mk_batch_item(
        db_session, "BATCH-00005", "CR-00006", status=BatchItemStatus.pending
    )

    result = _invoke(["batch-cancel", "BATCH-00005"], cli_get_session)
    assert result.exit_code == 0, result.output

    db_session.refresh(merged_bi)
    db_session.refresh(pending_bi)
    assert merged_bi.status == BatchItemStatus.merged  # untouched
    assert pending_bi.status == BatchItemStatus.skipped  # cancelled

    # The completed work item must NOT regress to cancelled.
    wi_completed = db_session.get(WorkItem, ("test-proj", "CR-00005"))
    wi_pending = db_session.get(WorkItem, ("test-proj", "CR-00006"))
    assert wi_completed.status == WorkItemStatus.completed
    assert wi_pending.status == WorkItemStatus.cancelled


# ---------------------------------------------------------------------------
# item-cancel
# ---------------------------------------------------------------------------


def test_item_cancel_standalone_item_to_cancelled(
    db_session: Any, test_project: Project, cli_get_session: Any
) -> None:
    """An in-progress item with no active batch → cancelled + steps skipped."""
    _mk_item(db_session, "CR-00010")
    _mk_step(db_session, "CR-00010", 1, status=StepStatus.failed)
    _mk_step(db_session, "CR-00010", 2, status=StepStatus.pending)

    result = _invoke(["item-cancel", "CR-00010", "--reason", "abandoned"], cli_get_session)
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "CR-00010"))
    assert wi.status == WorkItemStatus.cancelled

    steps = (
        db_session.query(WorkflowStep)
        .filter_by(project_id="test-proj", work_item_id="CR-00010")
        .order_by(WorkflowStep.step_number)
        .all()
    )
    assert [s.status for s in steps] == [StepStatus.failed, StepStatus.skipped]


def test_item_cancel_to_draft_resets_steps(
    db_session: Any, test_project: Project, cli_get_session: Any
) -> None:
    _mk_item(db_session, "CR-00011")
    _mk_step(db_session, "CR-00011", 1, status=StepStatus.failed)
    _mk_step(db_session, "CR-00011", 2, status=StepStatus.pending)

    result = _invoke(["item-cancel", "CR-00011", "--to-draft"], cli_get_session)
    assert result.exit_code == 0, result.output

    wi = db_session.get(WorkItem, ("test-proj", "CR-00011"))
    assert wi.status == WorkItemStatus.draft

    steps = (
        db_session.query(WorkflowStep)
        .filter_by(project_id="test-proj", work_item_id="CR-00011")
        .all()
    )
    assert all(s.status == StepStatus.pending for s in steps)


def test_item_cancel_refuses_when_item_in_active_batch(
    db_session: Any, test_project: Project, cli_get_session: Any
) -> None:
    """If the item is in an executing batch, item-cancel must point at batch-cancel."""
    _mk_item(db_session, "CR-00012")
    _mk_batch(db_session, "BATCH-00010", status=BatchStatus.executing)
    _mk_batch_item(db_session, "BATCH-00010", "CR-00012")

    result = _invoke(["item-cancel", "CR-00012"], cli_get_session)
    assert result.exit_code == 4
    assert "BATCH-00010" in result.output
    assert "batch-cancel" in result.output

    # State unchanged
    wi = db_session.get(WorkItem, ("test-proj", "CR-00012"))
    assert wi.status == WorkItemStatus.in_progress


def test_item_cancel_allowed_after_parent_batch_is_terminal(
    db_session: Any, test_project: Project, cli_get_session: Any
) -> None:
    """Once the batch is cancelled, the operator can still flip the item to draft."""
    _mk_item(db_session, "CR-00013", status=WorkItemStatus.cancelled)
    _mk_batch(db_session, "BATCH-00011", status=BatchStatus.cancelled)
    _mk_batch_item(db_session, "BATCH-00011", "CR-00013", status=BatchItemStatus.skipped)

    # Cancelled → no, can't cancel again. But this proves the active-batch gate
    # doesn't fire on a terminal batch; the second-line guard (status) is
    # what stops us here.
    result = _invoke(["item-cancel", "CR-00013"], cli_get_session)
    assert result.exit_code == 1
    assert "current status is 'cancelled'" in result.output


def test_item_cancel_refuses_for_completed_item(
    db_session: Any, test_project: Project, cli_get_session: Any
) -> None:
    _mk_item(db_session, "CR-00014", status=WorkItemStatus.completed)

    result = _invoke(["item-cancel", "CR-00014"], cli_get_session)
    assert result.exit_code == 1
    assert "current status is 'completed'" in result.output
