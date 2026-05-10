"""I-00076 E2E fixture: synthetic item I-99003 with a failed step for runtime-override verification.

This fixture enables V1-V4 browser verification of the per-step CLI <select> fix
(I-00076) in an isolated E2E stack that has no pending/failed steps in its seed data.

The item is synthetic (not from a real design) so it does not interfere with any
other verification or production data.
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import TYPE_CHECKING

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
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

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"
ITEM_ID = "I-99003"


def seed(db: Session) -> None:
    """Create I-99003 with one failed step (S01) so the runtime-override <select> is editable."""
    # Check if already seeded (idempotent)
    existing_item = db.get(WorkItem, (PROJECT_ID, ITEM_ID))
    if existing_item is not None:
        # Ensure it has a failed step
        existing_step = db.execute(
            db.query(WorkflowStep)
            .filter(
                WorkflowStep.project_id == PROJECT_ID,
                WorkflowStep.work_item_id == ITEM_ID,
                WorkflowStep.step_id == "S01",
            )
            .statement
        ).scalar_one_or_none()
        if existing_step is None:
            _add_step(db, ITEM_ID)
        return

    # Create the work item (no commit — let the seed script commit after all fixtures)
    now = datetime.now(UTC)
    item = WorkItem(
        project_id=PROJECT_ID,
        id=ITEM_ID,
        type=WorkItemType.Issue,
        title="I-00076 runtime-override verification fixture",
        status=WorkItemStatus.approved,  # Item must be approved to be on the queue/overview
        phase=WorkItemPhase.active,
        created_at=now,
    )
    db.add(item)
    db.flush()  # Get the item inserted before the FK step

    # Add a minimal batch so the item is reachable in the UI
    batch = Batch(project_id=PROJECT_ID, id="e2e-I-00076", status=BatchStatus.executing, created_at=now)
    db.add(batch)
    db.flush()

    batch_item = BatchItem(
        project_id=PROJECT_ID,
        batch_id="e2e-I-00076",
        work_item_id=ITEM_ID,
        status=BatchItemStatus.executing,
    )
    db.add(batch_item)
    db.flush()

    _add_step(db, ITEM_ID)


def _add_step(db: Session, item_id: str) -> WorkflowStep:
    step = WorkflowStep(
        project_id=PROJECT_ID,
        work_item_id=item_id,
        step_number=1,
        step_id="S01",
        agent_label="tests-impl",
        step_type=StepType.implementation,
        description="Failed step for runtime override verification",
        status=StepStatus.failed,
    )
    db.add(step)
    db.flush()  # Get the numeric id before StepRun INSERT

    run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.failed,
        cli_tool="opencode",
    )
    db.add(run)

    return step