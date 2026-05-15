"""orch.cancel — shared cancellation service layer for work items and batches.

Provides the canonical cancellation logic used by both the dashboard API
(routers/actions.py) and the CLI (iw batch-cancel / iw item-cancel).

Design contract (F-00082):
- cancel_work_item / cancel_batch are the ONLY entry points that manipulate
  WorkItemStatus / BatchStatus for cancellation — no other module does this.
- All status validation lives here; routers are thin parsers.
- teardown_errors are surfaced but never block the 2xx response.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session  # noqa: TC002  needed at runtime for type annotations

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    RunStatus,
    StepRun,
    StepStatus,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status sets
# ---------------------------------------------------------------------------

CANCELLABLE_WORK_ITEM_STATUSES: frozenset[WorkItemStatus] = frozenset(
    {
        WorkItemStatus.approved,
        WorkItemStatus.in_progress,
        WorkItemStatus.failed,
        WorkItemStatus.paused,
    }
)

CANCELLABLE_BATCH_STATUSES: frozenset[BatchStatus] = frozenset(
    {
        BatchStatus.planning,
        BatchStatus.approved,
        BatchStatus.executing,
        BatchStatus.paused,
        BatchStatus.blocked,
        BatchStatus.publish_failed,
    }
)

_ACTIVE_BATCH_STATUSES: frozenset[BatchStatus] = frozenset(
    {
        BatchStatus.planning,
        BatchStatus.approved,
        BatchStatus.executing,
        BatchStatus.paused,
        BatchStatus.blocked,
        BatchStatus.publishing,
        BatchStatus.publish_failed,
    }
)

_TERMINAL_BATCH_ITEM_STATUSES: frozenset[BatchItemStatus] = frozenset(
    {
        BatchItemStatus.completed,
        BatchItemStatus.merged,
        BatchItemStatus.failed,
        BatchItemStatus.stalled,
        BatchItemStatus.skipped,
        BatchItemStatus.merge_failed,
        BatchItemStatus.migration_invalid,
        BatchItemStatus.migration_rolled_back,
        BatchItemStatus.migration_rebase_failed,
        BatchItemStatus.setup_failed,
    }
)

# Step statuses that should be flipped to 'skipped' on cancel (terminal ones —
# completed/failed/skipped — are kept untouched so history is preserved).
_NON_TERMINAL_STEP_STATUSES: frozenset[StepStatus] = frozenset(
    {StepStatus.pending, StepStatus.in_progress, StepStatus.needs_fix}
)


# ---------------------------------------------------------------------------
# Pure validators (no DB) — used by both the service layer below and unit
# tests that need to lock the transition contract at unit-test speed.
# ---------------------------------------------------------------------------


def validate_batch_cancel_transition(status: BatchStatus) -> str | None:
    """Return None when a batch in ``status`` may be cancelled, else the error message.

    The message is the exact string surfaced to the operator by the CLI
    (``iw batch-cancel``) and the dashboard's HTTP 409 response.
    """
    if status not in CANCELLABLE_BATCH_STATUSES:
        return f"Cannot cancel batch: current status is '{status.value}'"
    return None


def validate_item_cancel_transition(
    status: WorkItemStatus,
    active_batch_id: str | None,
) -> str | None:
    """Return None when a work item may be cancelled, else the error message.

    The status guard runs *before* the active-batch guard so a draft item in
    an active batch reports the status error (which is the more actionable
    one) rather than the batch hint.

    When the item belongs to an active batch the message names the batch
    and prompts the operator to use ``iw batch-cancel`` — both substrings
    are part of the public contract checked by the CLI integration test.
    """
    if status not in CANCELLABLE_WORK_ITEM_STATUSES:
        return f"Cannot cancel work item: current status is '{status.value}'"
    if active_batch_id is not None:
        return (
            f"Cannot cancel work item: belongs to active batch {active_batch_id}. "
            f"Use 'iw batch-cancel {active_batch_id}' instead."
        )
    return None


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class CancelWorkItemResult:
    new_status: WorkItemStatus
    reason: str
    teardown_errors: list[str]


@dataclass
class CancelBatchResult:
    new_batch_status: BatchStatus
    cancelled_batch_items: list[str]
    reset_to_draft: list[str]
    killed_pids: list[int]
    teardown_errors: list[str]


# ---------------------------------------------------------------------------
# Work item cancellation
# ---------------------------------------------------------------------------


def cancel_work_item(
    db: Session,
    project_id: str,
    item_id: str,
    reason: str = "cancelled by operator",
    to_draft: bool = False,
) -> CancelWorkItemResult:
    """Cancel a single work item (optionally resetting to draft).

    Args:
        db: SQLAlchemy session.
        project_id: Project ID.
        item_id: Work item ID.
        reason: Cancellation reason (recorded in DaemonEvent).
        to_draft: If True, the item lands in 'draft' with all steps reset to 'pending'.

    Returns:
        CancelWorkItemResult with new status, reason, and any teardown errors.

    Raises:
        LookupError: Item not found.
        ValueError: Item status is not cancellable, or item is in an active batch
            (message contains "active batch").
    """
    item = db.execute(
        select(WorkItem).where(
            WorkItem.project_id == project_id,
            WorkItem.id == item_id,
        )
    ).scalar_one_or_none()

    if item is None:
        raise LookupError(f"Work item {item_id} not found in project {project_id}")

    # Status guard (runs before the active-batch lookup so the more
    # actionable error wins when both rules would fire).
    status_error = validate_item_cancel_transition(item.status, active_batch_id=None)
    if status_error is not None:
        raise ValueError(status_error)

    # Active-batch guard — block cancel if item belongs to a non-terminal batch
    active_batch_item = db.execute(
        select(BatchItem)
        .join(Batch, (BatchItem.project_id == Batch.project_id) & (BatchItem.batch_id == Batch.id))
        .where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
            Batch.status.in_(_ACTIVE_BATCH_STATUSES),
        )
    ).scalar_one_or_none()

    if active_batch_item is not None:
        batch_error = validate_item_cancel_transition(
            item.status,
            active_batch_id=active_batch_item.batch_id,
        )
        # batch_error is always non-None here: status has already been
        # validated above (cancellable) and active_batch_id is non-None,
        # so the validator's batch-membership branch must fire.
        raise ValueError(batch_error or "in active batch")

    # Determine target status
    new_status = WorkItemStatus.draft if to_draft else WorkItemStatus.cancelled

    # Reset steps to pending if going to draft
    teardown_errors: list[str] = []
    if to_draft:
        steps_to_reset = (
            db.execute(
                select(WorkflowStep).where(
                    WorkflowStep.project_id == project_id,
                    WorkflowStep.work_item_id == item_id,
                )
            )
            .scalars()
            .all()
        )
        for step in steps_to_reset:
            step.status = StepStatus.pending
            step.started_at = None
            step.completed_at = None

    # All non-terminal steps (pending / in_progress / needs_fix) are flipped to
    # 'skipped' so the work item's downstream pipeline doesn't try to run them
    # again. Already-terminal steps (completed / failed / skipped) are left
    # alone — the cancel must preserve history, not rewrite it.
    if not to_draft:
        non_terminal_steps = (
            db.execute(
                select(WorkflowStep).where(
                    WorkflowStep.project_id == project_id,
                    WorkflowStep.work_item_id == item_id,
                    WorkflowStep.status.in_(_NON_TERMINAL_STEP_STATUSES),
                )
            )
            .scalars()
            .all()
        )

        for step in non_terminal_steps:
            # If this step is currently running, kill its latest StepRun.
            if step.status == StepStatus.in_progress:
                run = db.execute(
                    select(StepRun)
                    .where(
                        StepRun.step_id == step.id,
                        StepRun.status == RunStatus.running,
                    )
                    .order_by(StepRun.run_number.desc())
                    .limit(1)
                ).scalar_one_or_none()

                if run is not None and run.pid is not None:
                    try:
                        os.kill(run.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass  # already dead
                    except OSError as exc:
                        teardown_errors.append(f"failed to kill PID {run.pid}: {exc}")

                    run.status = RunStatus.killed
                    run.completed_at = datetime.now(UTC)

            step.status = StepStatus.skipped

    # Teardown worktree via git worktree remove (best-effort)
    _teardown_item_worktree(db, project_id, item_id, teardown_errors)

    # Emit event
    _emit(
        db,
        "item_cancelled",
        project_id,
        item_id,
        "work_item",
        f"Item {item_id} cancelled by user"
        if not to_draft
        else f"Item {item_id} reset to draft by user",
        {"reason": reason, "to_draft": to_draft, "new_status": new_status.value},
    )

    item.status = new_status
    item.updated_at = datetime.now(UTC)
    db.commit()

    return CancelWorkItemResult(
        new_status=new_status,
        reason=reason,
        teardown_errors=teardown_errors,
    )


def _teardown_item_worktree(
    db: Session,
    project_id: str,
    item_id: str,
    teardown_errors: list[str],
) -> None:
    """Best-effort worktree teardown for a single item.

    Finds the most recent BatchItem for this item and attempts git worktree remove.
    """
    batch_item = db.execute(
        select(BatchItem)
        .where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
        )
        .order_by(BatchItem.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    if batch_item is None:
        return

    worktree_info = batch_item.worktree_info or {}
    worktree_path = worktree_info.get("path") if isinstance(worktree_info, dict) else None

    if not worktree_path:
        # Also check BatchItem.worktree_compose_path for compose stack teardown
        if batch_item.worktree_compose_path:
            _teardown_compose_stack(
                batch_item.id, batch_item.worktree_compose_path, teardown_errors
            )
        return

    try:
        subprocess.run(  # noqa: S603, S607
            ["git", "worktree", "remove", "--force", worktree_path],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        teardown_errors.append(f"git worktree remove timed out for {worktree_path}")
    except OSError as exc:
        teardown_errors.append(f"git worktree remove failed for {worktree_path}: {exc}")

    # Also teardown compose stack if present
    if batch_item.worktree_compose_path:
        _teardown_compose_stack(batch_item.id, batch_item.worktree_compose_path, teardown_errors)


def _teardown_compose_stack(
    _batch_item_id: int | None,
    compose_path: str | None,
    teardown_errors: list[str],
) -> None:
    """Best-effort compose stack teardown."""
    if not compose_path:
        return

    try:
        subprocess.run(  # noqa: S603, S607
            ["docker", "compose", "-f", compose_path, "down", "-v", "--remove-orphans"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        teardown_errors.append("compose down timed out")
    except OSError as exc:
        teardown_errors.append(f"compose down failed: {exc}")


# ---------------------------------------------------------------------------
# Batch cancellation
# ---------------------------------------------------------------------------


def cancel_batch(
    db: Session,
    project_id: str,
    batch_id: str,
    reason: str = "cancelled by operator",
    reset_items: bool = False,
) -> CancelBatchResult:
    """Cancel a batch and all its non-terminal member items.

    Args:
        db: SQLAlchemy session.
        project_id: Project ID.
        batch_id: Batch ID.
        reason: Cancellation reason.
        reset_items: If True, member items land in 'draft'; otherwise 'cancelled'.

    Returns:
        CancelBatchResult with summary of cancelled items, resets, killed PIDs,
        and any teardown errors.

    Raises:
        LookupError: Batch not found.
        ValueError: Batch status is not cancellable.
    """
    batch = db.execute(
        select(Batch).where(
            Batch.project_id == project_id,
            Batch.id == batch_id,
        )
    ).scalar_one_or_none()

    if batch is None:
        raise LookupError(f"Batch {batch_id} not found in project {project_id}")

    status_error = validate_batch_cancel_transition(batch.status)
    if status_error is not None:
        raise ValueError(status_error)

    cancelled_batch_items: list[str] = []
    reset_to_draft: list[str] = []
    killed_pids: list[int] = []
    teardown_errors: list[str] = []

    new_batch_status = BatchStatus.cancelled
    target_item_status = WorkItemStatus.draft if reset_items else WorkItemStatus.cancelled

    # Iterate over non-terminal batch items
    batch_items = (
        db.execute(
            select(BatchItem).where(
                BatchItem.project_id == project_id,
                BatchItem.batch_id == batch_id,
                BatchItem.status.notin_(_TERMINAL_BATCH_ITEM_STATUSES),
            )
        )
        .scalars()
        .all()
    )

    # Imported lazily so unit tests can monkeypatch
    # `orch.daemon.step_monitor.kill_process_group` without dragging the
    # full daemon package into the cancel module's import graph.
    from orch.daemon import step_monitor  # noqa: PLC0415

    for bi in batch_items:
        item_id = bi.work_item_id

        # Kill any running StepRuns owned by this work item — these are the
        # actual agent processes spawned by the daemon. We use
        # `kill_process_group` so the whole agent session (script -qec + the
        # inner CLI) receives SIGTERM, not just the shell wrapper.
        running_runs = (
            db.execute(
                select(StepRun)
                .join(WorkflowStep, StepRun.step_id == WorkflowStep.id)
                .where(
                    WorkflowStep.project_id == project_id,
                    WorkflowStep.work_item_id == item_id,
                    StepRun.status == RunStatus.running,
                )
            )
            .scalars()
            .all()
        )

        for run in running_runs:
            if run.pid is not None:
                try:
                    step_monitor.kill_process_group(run.pid)
                    killed_pids.append(run.pid)
                except OSError as exc:
                    teardown_errors.append(f"failed to kill PID {run.pid}: {exc}")
            run.status = RunStatus.killed
            run.pid_alive = False
            run.completed_at = datetime.now(UTC)

        # Back-compat: some early daemons recorded the launcher PID on the
        # BatchItem itself. Honour it when present so a re-run against an
        # older row still tears down cleanly.
        if bi.pid is not None:
            try:
                os.kill(bi.pid, signal.SIGTERM)
                killed_pids.append(bi.pid)
            except ProcessLookupError:
                pass
            except OSError as exc:
                teardown_errors.append(f"failed to kill PID {bi.pid}: {exc}")

        # Teardown compose stack
        if bi.worktree_compose_path:
            _teardown_compose_stack(bi.id, bi.worktree_compose_path, teardown_errors)

        # Teardown worktree (git worktree remove)
        worktree_path: str | None = None
        if bi.worktree_info and isinstance(bi.worktree_info, dict):
            worktree_path = bi.worktree_info.get("path")

        if worktree_path:
            try:
                subprocess.run(  # noqa: S603, S607
                    ["git", "worktree", "remove", "--force", worktree_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                teardown_errors.append(f"git worktree remove timed out for {worktree_path}")
            except OSError as exc:
                teardown_errors.append(f"git worktree remove failed for {worktree_path}: {exc}")

        # Update workflow step statuses. Already-terminal steps
        # (completed/failed/skipped) are left untouched.
        steps = (
            db.execute(
                select(WorkflowStep).where(
                    WorkflowStep.project_id == project_id,
                    WorkflowStep.work_item_id == item_id,
                )
            )
            .scalars()
            .all()
        )
        for step in steps:
            if reset_items:
                step.status = StepStatus.pending
                step.started_at = None
                step.completed_at = None
            elif step.status in _NON_TERMINAL_STEP_STATUSES:
                step.status = StepStatus.skipped

        # Update work item status
        item = db.execute(
            select(WorkItem).where(
                WorkItem.project_id == project_id,
                WorkItem.id == item_id,
            )
        ).scalar_one_or_none()

        # Don't regress a work item that already reached a happy terminal
        # state (e.g. a completed item still on the batch as a historical
        # row) — only flip items that are still in flight.
        if item is not None and item.status not in (
            WorkItemStatus.completed,
            WorkItemStatus.cancelled,
        ):
            item.status = target_item_status
            item.updated_at = datetime.now(UTC)
            if reset_items:
                reset_to_draft.append(item_id)
            else:
                cancelled_batch_items.append(item_id)

        # Mark batch item as skipped and record a cancellation breadcrumb in
        # notes so a reader scanning batch_items can tell *why* it stopped
        # without joining DaemonEvent.
        bi.status = BatchItemStatus.skipped
        bi.notes = f"Cancelled by batch-cancel of {batch_id}: {reason}"

    batch.status = new_batch_status
    batch.updated_at = datetime.now(UTC)

    # Emit the audit event *before* commit so it lands in the same
    # transaction as the status/item updates — a partial commit (status
    # changed but no event) would mask cancellations from the audit log.
    _emit(
        db,
        "batch_cancelled",
        project_id,
        batch_id,
        "batch",
        f"Batch {batch_id} cancelled by user",
        {
            "reason": reason,
            "reset_items": reset_items,
            "cancelled_batch_items": cancelled_batch_items,
            "reset_to_draft": reset_to_draft,
            "killed_pids": killed_pids,
        },
    )

    db.commit()

    return CancelBatchResult(
        new_batch_status=new_batch_status,
        cancelled_batch_items=cancelled_batch_items,
        reset_to_draft=reset_to_draft,
        killed_pids=killed_pids,
        teardown_errors=teardown_errors,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit(
    db: Session,
    event_type: str,
    project_id: str,
    entity_id: str,
    entity_type: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        DaemonEvent(
            project_id=project_id,
            event_type=event_type,
            entity_id=entity_id,
            entity_type=entity_type,
            message=message,
            event_metadata=metadata or {},
        )
    )
