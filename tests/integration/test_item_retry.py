"""Integration tests for `iw item-retry` — operator recovery path for dead-ended items.

Tests real DB state-machine rows (work_item / batch / batch_item / workflow_steps /
daemon_events) against a PostgreSQL testcontainer.

Scope (per I-00124 test plan):
  1. Reproduction: completed_with_errors batch / failed batch_item
  2. Regression: setup_failed path, idempotency, rejection of healthy states
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from sqlalchemy import select

from orch.cli.main import cli
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
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

    from orch.db.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_dead_ended_item(
    db_session: Session,
    project_id: str,
    item_id: str,
    batch_id: str,
    work_item_status: WorkItemStatus,
    batch_status: BatchStatus,
    batch_item_status: BatchItemStatus,
    steps: list[StepStatus],
) -> tuple[WorkItem, Batch, BatchItem, list[WorkflowStep]]:
    """Seed a complete dead-ended item: work_item + batch + batch_item + workflow_steps.

    Args:
        work_item_status:  status to set on the work_item
        batch_status:     status to set on the batch
        batch_item_status: status to set on the batch_item
        steps:            list of StepStatus values for the workflow_steps, in order
                         (first non-completed will be the first non-'completed' entry)
    """
    work_item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Issue,
        title=f"Dead-ended item {item_id}",
        status=work_item_status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(work_item)

    batch = Batch(
        project_id=project_id,
        id=batch_id,
        status=batch_status,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=False,
    )
    db_session.add(batch)

    batch_item = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=item_id,
        execution_group=0,
        status=batch_item_status,
    )
    db_session.add(batch_item)

    workflow_steps = []
    for idx, step_status in enumerate(steps, start=1):
        step = WorkflowStep(
            project_id=project_id,
            work_item_id=item_id,
            step_number=idx,
            step_id=f"S{idx:02d}",
            agent_label=f"Step {idx}",
            opencode_agent=f"step-{idx}-impl",
            step_type=StepType.implementation,
            status=step_status,
            started_at=datetime.now(UTC) if step_status == StepStatus.completed else None,
            completed_at=datetime.now(UTC) if step_status == StepStatus.completed else None,
        )
        db_session.add(step)
        workflow_steps.append(step)

    db_session.flush()
    return work_item, batch, batch_item, workflow_steps


def _invoke_item_retry(
    item_id: str,
    project_id: str,
    cli_get_session: Callable[..., contextmanager],
    json_output: bool = True,
) -> tuple:
    """Invoke `iw item-retry <item_id>` and return (exit_code, output_data)."""
    runner = CliRunner()
    # Pass project via context obj so resolve_project() finds it there
    # (bypasses the directory walk for .iw-orch.json which would find the
    # worktree's own config, not the test-project).  Also pass repo_root to
    # silence any fallbacks inside resolve_project.  Always include --json flag
    # so recovery commands output machine-readable JSON (not human text) so
    # assertions on data.get("retry") etc. can succeed.
    ctx_obj = {
        "get_session": cli_get_session,
        "project_id": project_id,
        "repo_root": "/repos/test",  # must match test_project's repo_root
        "json": True,
    }
    result = runner.invoke(
        cli,
        ["--json", "item-retry", item_id],
        obj=ctx_obj,
        catch_exceptions=True,
    )
    import contextlib

    data = None
    if result.output:
        with contextlib.suppress(json.JSONDecodeError):
            data = json.loads(result.output)
    return result.exit_code, data, result.output


# ---------------------------------------------------------------------------
# Test 1: Reproduction — completed_with_errors batch / failed batch_item
# AC1: the main recovery scenario from I-00124_Issue_Design.md
# ---------------------------------------------------------------------------


def test_item_retry_completed_with_errors_redrives_item(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """FAILS before the fix (no command / item stays terminal); PASSES after.

    Arrange: work_item + batch (completed_with_errors) + batch_item (failed) +
    workflow_steps: [completed, completed, failed, pending].

    Act: invoke `iw item-retry <item_id>`.

    Assert (semantic — I003 lesson: assert SPECIFIC VALUES, not shapes):
      - work_item.status == 'in_progress' (daemon can re-engage)
      - batch.status == 'executing' (daemon can re-engage)
      - batch_item.status == 'pending' (re-engageable)
      - step S03 (first non-completed) == 'pending' and S01/S02 (completed) unchanged
      - a DaemonEvent row with event_type='item_retry' exists
    """
    item_id = "I-00124-REPRO-01"

    # Arrange: seed the dead-ended state
    _seed_dead_ended_item(
        db_session=db_session,
        project_id=test_project.id,
        item_id=item_id,
        batch_id="BATCH-REPRO-01",
        # Use failed (not in_progress) so the idempotency guard does NOT trigger.
        # With work_item=failed + batch=completed_with_errors, the validation
        # falls through to "eligible" and recovery runs properly.
        work_item_status=WorkItemStatus.failed,
        batch_status=BatchStatus.completed_with_errors,
        batch_item_status=BatchItemStatus.failed,
        steps=[
            StepStatus.completed,
            StepStatus.completed,
            StepStatus.failed,
            StepStatus.pending,
        ],
    )
    # Capture pre-retry state as strings (safe against ORM staleness after flush)
    db_session.flush()
    # Re-fetch to ensure clean state after commit
    work_item_row = db_session.scalar(
        select(WorkItem).where(WorkItem.project_id == test_project.id, WorkItem.id == item_id)
    )
    batch_row = db_session.scalar(
        select(Batch).where(Batch.project_id == test_project.id, Batch.id == "BATCH-REPRO-01")
    )
    batch_item_row = db_session.scalar(
        select(BatchItem).where(
            BatchItem.project_id == test_project.id, BatchItem.work_item_id == item_id
        )
    )
    pre_retry_work_item_status = work_item_row.status.value
    pre_retry_batch_status = batch_row.status.value
    pre_retry_batch_item_status = batch_item_row.status.value

    # Act: invoke item-retry
    exit_code, data, output = _invoke_item_retry(item_id, test_project.id, cli_get_session)

    # Debug: show raw output
    assert exit_code == 0, f"Expected exit 0, got {exit_code}: {output}"

    # Assert: work_item.status is now 'in_progress' (daemon-reRunnable)
    work_item_after = db_session.scalar(select(WorkItem).where(WorkItem.id == item_id))
    assert work_item_after.status == WorkItemStatus.in_progress, (
        f"work_item.status should be 'in_progress', got '{work_item_after.status.value}'"
    )

    # Assert: batch.status is now 'executing'
    batch_after = db_session.scalar(select(Batch).where(Batch.id == "BATCH-REPRO-01"))
    assert batch_after.status == BatchStatus.executing, (
        f"batch.status should be 'executing', got '{batch_after.status.value}'"
    )

    # Assert: batch_item.status is now 'pending'
    batch_item_after = db_session.scalar(
        select(BatchItem).where(
            BatchItem.work_item_id == item_id, BatchItem.batch_id == "BATCH-REPRO-01"
        )
    )
    assert batch_item_after.status == BatchItemStatus.pending, (
        f"batch_item.status should be 'pending', got '{batch_item_after.status.value}'"
    )

    # Assert: the first non-completed step (S03) is now 'pending', completed steps unchanged
    db_session.flush()
    updated_steps = (
        db_session.execute(
            select(WorkflowStep)
            .where(
                WorkflowStep.project_id == test_project.id,
                WorkflowStep.work_item_id == item_id,
            )
            .order_by(WorkflowStep.step_number)
        )
        .scalars()
        .all()
    )

    # S01 and S02 were completed — must stay completed
    assert updated_steps[0].status == StepStatus.completed, (
        f"S01 should remain completed, got '{updated_steps[0].status.value}'"
    )
    assert updated_steps[1].status == StepStatus.completed, (
        f"S02 should remain completed, got '{updated_steps[1].status.value}'"
    )

    # S03 was the first non-completed (failed) — must now be pending
    assert updated_steps[2].status == StepStatus.pending, (
        f"S03 should be pending (first non-completed), got '{updated_steps[2].status.value}'"
    )

    # S04 was already pending — must still be pending
    assert updated_steps[3].status == StepStatus.pending, (
        f"S04 should remain pending, got '{updated_steps[3].status.value}'"
    )

    # Assert: DaemonEvent recording the retry exists
    event = db_session.scalar(
        select(DaemonEvent).where(
            DaemonEvent.project_id == test_project.id,
            DaemonEvent.event_type == "item_retry",
            DaemonEvent.entity_id == item_id,
        )
    )
    assert event is not None, "item_retry DaemonEvent should exist"
    assert event.entity_type == "work_item"
    assert "I-00124-REPRO-01" in event.message

    # Refresh to get post-action current state for metadata assertions
    work_item_after = db_session.scalar(select(WorkItem).where(WorkItem.id == item_id))
    batch_after = db_session.scalar(select(Batch).where(Batch.id == "BATCH-REPRO-01"))
    batch_item_after = db_session.scalar(
        select(BatchItem).where(
            BatchItem.work_item_id == item_id, BatchItem.batch_id == "BATCH-REPRO-01"
        )
    )

    # Assert: event_metadata captures the transition
    meta = event.event_metadata or {}
    assert meta.get("prior_work_item_status") == pre_retry_work_item_status
    assert meta.get("prior_batch_status") == pre_retry_batch_status
    assert meta.get("prior_batch_item_status") == pre_retry_batch_item_status
    assert meta.get("new_work_item_status") == work_item_after.status.value
    assert meta.get("new_batch_item_status") == batch_item_after.status.value
    assert meta.get("new_batch_status") == batch_after.status.value
    assert "S03" in meta.get("reset_step_ids", [])


# ---------------------------------------------------------------------------
# Test 2: Regression — setup_failed path
# ---------------------------------------------------------------------------


def test_item_retry_setup_failed_redrives_item(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """item-retry recovers an item whose batch_item is setup_failed.

    Assert:
      - batch_item.status == 'pending' (re-engageable)
      - work_item.status == 'in_progress'
      - a DaemonEvent exists
    """
    item_id = "I-00124-SETUP-01"

    _seed_dead_ended_item(
        db_session=db_session,
        project_id=test_project.id,
        item_id=item_id,
        batch_id="BATCH-SETUP-01",
        work_item_status=WorkItemStatus.failed,
        batch_status=BatchStatus.completed,
        batch_item_status=BatchItemStatus.setup_failed,
        steps=[StepStatus.completed],
    )
    db_session.commit()  # Ensure test data is committed and visible to CLI session

    exit_code, data, raw_output = _invoke_item_retry(item_id, test_project.id, cli_get_session)

    # Force flush + commit within test session so CLI command's DaemonEvent
    # (added to the SAME session) is visible to the test query.
    db_session.flush()
    db_session.commit()

    assert exit_code == 0, f"Expected exit 0, got {exit_code}: {raw_output}"

    # Reload the batch_item and work_item to check their updated statuses
    batch_item = db_session.scalar(
        select(BatchItem).where(
            BatchItem.project_id == test_project.id, BatchItem.work_item_id == item_id
        )
    )
    work_item = db_session.scalar(
        select(WorkItem).where(WorkItem.project_id == test_project.id, WorkItem.id == item_id)
    )

    assert batch_item.status == BatchItemStatus.pending, (
        f"batch_item.status should be 'pending', got '{batch_item.status.value}'"
    )
    assert work_item.status == WorkItemStatus.in_progress, (
        f"work_item.status should be 'in_progress', got '{work_item.status.value}'"
    )

    # DaemonEvent exists
    event = db_session.scalar(
        select(DaemonEvent).where(
            DaemonEvent.project_id == test_project.id,
            DaemonEvent.event_type == "item_retry",
            DaemonEvent.entity_id == item_id,
        )
    )
    assert event is not None


# ---------------------------------------------------------------------------
# Test 3: Regression — idempotency
# ---------------------------------------------------------------------------


def test_item_retry_idempotent_double_invocation(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """Invoking item-retry twice on the same stuck item succeeds both times (idempotent).

    No error is raised and no state changes occur on the second invocation.

    Assert:
      - First call: exit 0, changes applied (retry=True in response)
      - Second call: exit 0, no changes (retry=False in response)
      - All states stable (no double-reset)
    """
    item_id = "I-00124-IDEM-01"

    work_item, batch, batch_item, steps = _seed_dead_ended_item(
        db_session=db_session,
        project_id=test_project.id,
        item_id=item_id,
        batch_id="BATCH-IDEM-01",
        # Work item is failed so first invocation applies recovery (not idempotent no-op).
        # batch=completed_with_errors ensures eligibility even with failed work_item.
        work_item_status=WorkItemStatus.failed,
        batch_status=BatchStatus.completed_with_errors,
        batch_item_status=BatchItemStatus.failed,
        steps=[
            StepStatus.completed,
            StepStatus.failed,
        ],
    )
    db_session.commit()  # Ensure test data is committed and visible to CLI session

    # First invocation — should apply recovery (retry=True)
    exit_code_1, data_1, _ = _invoke_item_retry(item_id, test_project.id, cli_get_session)
    assert exit_code_1 == 0, f"First call should exit 0, got {exit_code_1}"
    assert data_1 is not None
    assert data_1.get("retry") is True, "First call should apply recovery (retry=True)"

    # Re-fetch to confirm first recovery took effect
    work_item = db_session.scalar(select(WorkItem).where(WorkItem.id == item_id))
    batch = db_session.scalar(select(Batch).where(Batch.id == "BATCH-IDEM-01"))
    batch_item = db_session.scalar(
        select(BatchItem).where(
            BatchItem.work_item_id == item_id, BatchItem.batch_id == "BATCH-IDEM-01"
        )
    )

    work_item_status_after_1 = work_item.status
    batch_status_after_1 = batch.status
    batch_item_status_after_1 = batch_item.status

    assert work_item_status_after_1 == WorkItemStatus.in_progress
    assert batch_status_after_1 == BatchStatus.executing
    assert batch_item_status_after_1 == BatchItemStatus.pending

    # Second invocation — idempotent no-op (retry=False)
    exit_code_2, data_2, _ = _invoke_item_retry(item_id, test_project.id, cli_get_session)
    assert exit_code_2 == 0, f"Idempotent second call should exit 0, got {exit_code_2}"
    assert data_2 is not None
    assert data_2.get("retry") is False, "Second call should be a no-op (retry=False)"
    assert "already recovered" in data_2.get("message", "").lower()

    # Re-fetch to verify stability (no double-reset)
    work_item_after = db_session.scalar(select(WorkItem).where(WorkItem.id == item_id))
    batch_after = db_session.scalar(select(Batch).where(Batch.id == "BATCH-IDEM-01"))
    batch_item_after = db_session.scalar(
        select(BatchItem).where(
            BatchItem.work_item_id == item_id, BatchItem.batch_id == "BATCH-IDEM-01"
        )
    )

    # All statuses unchanged (no double-reset)
    assert work_item_after.status == work_item_status_after_1, "work_item.status should be stable"
    assert batch_after.status == batch_status_after_1, "batch.status should be stable"
    assert batch_item_after.status == batch_item_status_after_1, (
        "batch_item.status should be stable"
    )


# ---------------------------------------------------------------------------
# Test 4: Regression — rejection of healthy / executing items
# ---------------------------------------------------------------------------


def test_item_retry_rejects_healthy_in_progress_item(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """item-retry on a healthy in_progress item is an idempotent no-op (exit 0).

    The item is not stuck — it's already in the target recovery state
    (in_progress + executing + pending). The validator's idempotency guard
    fires first and returns "already recovered" rather than a rejection.
    No changes are made and no DaemonEvent is emitted.
    """
    item_id = "I-00124-REJ-HEALTHY-01"

    _seed_dead_ended_item(
        db_session=db_session,
        project_id=test_project.id,
        item_id=item_id,
        batch_id="BATCH-REJ-HEALTHY-01",
        # Healthy: in_progress + executing + pending batch_item — the item is
        # already in the target recovery state. The validator's idempotency guard
        # fires first, returning "already recovered" with exit 0 (not exit 1).
        work_item_status=WorkItemStatus.in_progress,
        batch_status=BatchStatus.executing,
        batch_item_status=BatchItemStatus.pending,
        steps=[StepStatus.in_progress],
    )
    db_session.commit()  # Ensure test data is committed and visible to CLI session

    exit_code, data, output = _invoke_item_retry(item_id, test_project.id, cli_get_session)

    # Idempotent no-op: exit 0 (not exit 1), "already recovered" in response
    assert exit_code == 0, f"Expected exit 0 (idempotent no-op), got {exit_code}: {output}"
    # With --json flag (always set in _invoke_item_retry), output is JSON — no human text
    assert data is not None, f"Expected JSON output, got: {output}"
    assert data.get("retry") is False, "Idempotent no-op should have retry=False"
    assert "already recovered" in data.get("message", "").lower(), (
        f"Expected 'already recovered' in JSON message, got: {data.get('message')}"
    )

    # Verify the item state is unchanged (no double-reset)
    work_item = db_session.scalar(
        select(WorkItem).where(WorkItem.project_id == test_project.id, WorkItem.id == item_id)
    )
    batch = db_session.scalar(
        select(Batch).where(Batch.project_id == test_project.id, Batch.id == "BATCH-REJ-HEALTHY-01")
    )
    batch_item = db_session.scalar(
        select(BatchItem).where(
            BatchItem.project_id == test_project.id, BatchItem.work_item_id == item_id
        )
    )

    assert work_item.status == WorkItemStatus.in_progress, "work_item.status should be unchanged"
    assert batch.status == BatchStatus.executing, "batch.status should be unchanged"
    assert batch_item.status == BatchItemStatus.pending, "batch_item.status should be unchanged"

    # No DaemonEvent for idempotent no-op (nothing was recovered)
    event = db_session.scalar(
        select(DaemonEvent).where(
            DaemonEvent.project_id == test_project.id,
            DaemonEvent.event_type == "item_retry",
            DaemonEvent.entity_id == item_id,
        )
    )
    assert event is None, "No DaemonEvent for idempotent no-op"


def test_item_retry_rejects_draft_item(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """item-retry on a draft item is rejected — draft items have never been executed."""
    item_id = "I-00124-REJ-DRAFT-01"

    _seed_dead_ended_item(
        db_session=db_session,
        project_id=test_project.id,
        item_id=item_id,
        batch_id="BATCH-REJ-DRAFT-01",
        work_item_status=WorkItemStatus.draft,
        batch_status=BatchStatus.completed,
        batch_item_status=BatchItemStatus.pending,
        steps=[StepStatus.pending],
    )

    exit_code, _, output = _invoke_item_retry(item_id, test_project.id, cli_get_session)

    assert exit_code == 1, f"Expected exit 1 (rejection), got {exit_code}"
    assert "not stuck" in output.lower() or "not eligible" in output.lower()


def test_item_retry_rejects_approved_item_with_healthy_batch(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """item-retry on an approved item with a healthy batch is rejected."""
    item_id = "I-00124-REJ-APPROVED-01"

    _seed_dead_ended_item(
        db_session=db_session,
        project_id=test_project.id,
        item_id=item_id,
        batch_id="BATCH-REJ-APPROVED-01",
        work_item_status=WorkItemStatus.approved,
        batch_status=BatchStatus.approved,  # healthy
        batch_item_status=BatchItemStatus.pending,
        steps=[StepStatus.pending],
    )

    exit_code, _, output = _invoke_item_retry(item_id, test_project.id, cli_get_session)

    assert exit_code == 1, f"Expected exit 1 (rejection), got {exit_code}"
    assert "not stuck" in output.lower() or "not eligible" in output.lower()


def test_item_retry_not_found_item(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """item-retry on a non-existent item exits 1 with a not-found message."""
    exit_code, data, raw_output = _invoke_item_retry(
        "WI-DOES-NOT-EXIST-99999", test_project.id, cli_get_session
    )
    assert exit_code == 1, f"Expected exit 1, got {exit_code}: {raw_output!r}"
    # On non-JSON error, data is None — that's expected for a not-found error
    assert data is None or "not found" in str(data).lower()


# ---------------------------------------------------------------------------
# Test 5: Regression — stall / migration_rebase_failed / merge_failed paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "batch_item_status",
    [
        BatchItemStatus.stalled,
        BatchItemStatus.migration_rebase_failed,
        BatchItemStatus.merge_failed,
    ],
)
def test_item_retry_terminal_batch_item_statuses(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
    batch_item_status: BatchItemStatus,
) -> None:
    """item-retry accepts batch_items in stalled / migration_rebase_failed / merge_failed.

    All terminal sub-states that prevent the daemon from re-engaging are valid recovery targets.
    """
    item_id = f"I-00124-TERM-{batch_item_status.value}-01"

    _seed_dead_ended_item(
        db_session=db_session,
        project_id=test_project.id,
        item_id=item_id,
        batch_id=f"BATCH-TERM-{batch_item_status.value}",
        work_item_status=WorkItemStatus.failed,
        batch_status=BatchStatus.completed,
        batch_item_status=batch_item_status,
        steps=[StepStatus.completed],
    )

    exit_code, _, _ = _invoke_item_retry(item_id, test_project.id, cli_get_session)
    assert exit_code == 0, f"item-retry should accept batch_item_status={batch_item_status.value}"

    batch_item = db_session.scalar(
        select(BatchItem).where(
            BatchItem.project_id == test_project.id,
            BatchItem.work_item_id == item_id,
        )
    )
    assert batch_item.status == BatchItemStatus.pending, (
        f"batch_item.status should be 'pending', got '{batch_item.status.value}'"
    )


# ---------------------------------------------------------------------------
# Test 6: Regression — JSON output contract
# ---------------------------------------------------------------------------


def test_item_retry_json_output_contract(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """item-retry --json emits the documented payload fields."""
    item_id = "I-00124-JSON-01"

    _seed_dead_ended_item(
        db_session=db_session,
        project_id=test_project.id,
        item_id=item_id,
        batch_id="BATCH-JSON-01",
        work_item_status=WorkItemStatus.failed,
        batch_status=BatchStatus.completed_with_errors,
        batch_item_status=BatchItemStatus.failed,
        steps=[StepStatus.completed, StepStatus.failed],
    )
    db_session.commit()  # Ensure test data is committed and visible to CLI session

    exit_code, data, _ = _invoke_item_retry(item_id, test_project.id, cli_get_session)

    assert exit_code == 0
    assert data is not None
    assert data.get("project_id") == test_project.id
    assert data.get("id") == item_id
    assert data.get("status") == "in_progress"
    assert data.get("retry") is True
    assert "message" in data
    assert "step" in data.get("message", "").lower() or "reset" in data.get("message", "").lower()
