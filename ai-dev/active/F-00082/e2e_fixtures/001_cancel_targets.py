"""E2E fixture for F-00082 — Dashboard Cancel Buttons browser verification.

Creates the minimum data required for V1..V6 verifications:

- V1: A batch in `executing` status with a BatchItem in `executing`
     and a WorkItem with steps in mixed states.
- V2: A standalone work item (not in any active batch) in `in_progress`.
- V3: A work item in `in_progress` that IS in an active (executing) batch.
- V4: A batch in `paused` status with at least one BatchItem.
- V5: A batch in `completed` status (terminal — no Cancel button).

Idempotent: re-running is safe. Uses db.flush() after parent rows to avoid
ForeignKeyViolation (BatchItem FKs reference Batch and WorkItem; SQLAlchemy
unit-of-work needs explicit flush ordering when no relationship() drives it).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    StepStatus,
    StepType,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
    WorkflowStep,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"

# Unique-ish suffix using timestamp to avoid collisions on re-run
_NOW = datetime.now(UTC)
_SUFFIX = _NOW.strftime("%m%d%H%M%S")


def _make_id(prefix: str) -> str:
    return f"{prefix}-{_SUFFIX}"


def seed(db: Session) -> None:
    # ── V5: Terminal batch ────────────────────────────────────────────────────
    # Must exist before V1's batch so we can query it when V1 is created.
    # V5 batch is `completed` (terminal) → no Cancel button rendered.
    completed_batch_id = _make_id("BATCH-V5")
    existing = db.get(Batch, (PROJECT_ID, completed_batch_id))
    if existing is None:
        completed_batch = Batch(
            project_id=PROJECT_ID,
            id=completed_batch_id,
            status=BatchStatus.completed,
            auto_merge=False,
        )
        db.add(completed_batch)
        db.flush()  # make batch_id available for BatchItem below

        completed_item = WorkItem(
            project_id=PROJECT_ID,
            id=_make_id("CR-V5"),
            type=WorkItemType.ChangeRequest,
            title="Completed-item for V5 terminal batch check",
            status=WorkItemStatus.completed,
            phase="done",
        )
        db.add(completed_item)
        db.flush()

        db.add(
            BatchItem(
                project_id=PROJECT_ID,
                batch_id=completed_batch_id,
                work_item_id=completed_item.id,
                execution_group=0,
                status=BatchItemStatus.completed,
            )
        )

    # ── V1 + V4: Executing/paused batch (cancellable) ─────────────────────────
    # V1 needs `executing` batch + BatchItem in `executing`
    # V4 needs a `paused` batch — we re-use the same batch if it can be both,
    # but since a batch has one status, we create two separate batches.
    executing_batch_id = _make_id("BATCH-V1")
    paused_batch_id = _make_id("BATCH-V4")

    # --- V1 batch (executing) ---
    existing_exec = db.get(Batch, (PROJECT_ID, executing_batch_id))
    if existing_exec is None:
        exec_batch = Batch(
            project_id=PROJECT_ID,
            id=executing_batch_id,
            status=BatchStatus.executing,
            auto_merge=False,
        )
        db.add(exec_batch)
        db.flush()

        exec_item = WorkItem(
            project_id=PROJECT_ID,
            id=_make_id("F-V1"),
            type=WorkItemType.Feature,
            title="V1 – executing batch feature item",
            status=WorkItemStatus.in_progress,
            phase="work",
        )
        db.add(exec_item)
        db.flush()

        exec_bi = BatchItem(
            project_id=PROJECT_ID,
            batch_id=executing_batch_id,
            work_item_id=exec_item.id,
            execution_group=0,
            status=BatchItemStatus.executing,
        )
        db.add(exec_bi)
        db.flush()

        # Steps in mixed states for V1 reset verification
        for step_number, step_status in [
            (1, StepStatus.in_progress),   # running step
            (2, StepStatus.pending),       # queued step
            (3, StepStatus.pending),       # queued step
        ]:
            db.add(
                WorkflowStep(
                    project_id=PROJECT_ID,
                    work_item_id=exec_item.id,
                    step_number=step_number,
                    step_id=f"S{step_number:02d}",
                    agent_label="test",
                    step_type=StepType.implementation,
                    status=step_status,
                )
            )

    # --- V4 batch (paused) ---
    existing_paused = db.get(Batch, (PROJECT_ID, paused_batch_id))
    if existing_paused is None:
        paused_batch = Batch(
            project_id=PROJECT_ID,
            id=paused_batch_id,
            status=BatchStatus.paused,
            auto_merge=False,
        )
        db.add(paused_batch)
        db.flush()

        paused_item = WorkItem(
            project_id=PROJECT_ID,
            id=_make_id("F-V4"),
            type=WorkItemType.Feature,
            title="V4 – paused batch feature item",
            status=WorkItemStatus.in_progress,
            phase="work",
        )
        db.add(paused_item)
        db.flush()

        db.add(
            BatchItem(
                project_id=PROJECT_ID,
                batch_id=paused_batch_id,
                work_item_id=paused_item.id,
                execution_group=0,
                status=BatchItemStatus.pending,
            )
        )

    # ── V2: Standalone in_progress work item (NOT in any active batch) ─────────
    standalone_item_id = _make_id("I-V2")
    existing_standalone = db.get(WorkItem, (PROJECT_ID, standalone_item_id))
    if existing_standalone is None:
        standalone_item = WorkItem(
            project_id=PROJECT_ID,
            id=standalone_item_id,
            type=WorkItemType.Issue,
            title="V2 – standalone in-progress item (not in active batch)",
            status=WorkItemStatus.in_progress,
            phase="work",
        )
        db.add(standalone_item)
        db.flush()

        for step_number in [1, 2]:
            db.add(
                WorkflowStep(
                    project_id=PROJECT_ID,
                    work_item_id=standalone_item_id,
                    step_number=step_number,
                    step_id=f"S{step_number:02d}",
                    agent_label="test",
                    step_type=StepType.implementation,
                    status=StepStatus.in_progress,
                )
            )

    # ── V3: In-progress item that IS in the executing batch ───────────────────
    # V3: cancel button should be disabled with hint "Belongs to active batch"
    # The item itself is `in_progress` with its parent batch in `executing`.
    # Use the same executing_batch_id as V1 — V3 just needs a different item in it.
    in_batch_item_id = _make_id("CR-V3")
    existing_in_batch = db.get(WorkItem, (PROJECT_ID, in_batch_item_id))
    if existing_in_batch is None:
        in_batch_item = WorkItem(
            project_id=PROJECT_ID,
            id=in_batch_item_id,
            type=WorkItemType.ChangeRequest,
            title="V3 – in active batch, cancel button disabled",
            status=WorkItemStatus.in_progress,
            phase="work",
        )
        db.add(in_batch_item)
        db.flush()

        db.add(
            BatchItem(
                project_id=PROJECT_ID,
                batch_id=executing_batch_id,
                work_item_id=in_batch_item_id,
                execution_group=1,  # different group from V1's item
                status=BatchItemStatus.pending,
            )
        )