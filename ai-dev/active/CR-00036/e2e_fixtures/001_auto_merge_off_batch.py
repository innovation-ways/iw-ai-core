"""E2E fixture: auto_merge=false batch with items in awaiting_merge_approval state."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from orch.db.models import (
    Batch,
    BatchItem,
    RunStatus,
    StepRun,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)


def seed(db: Session) -> None:
    """
    Seed data for V5/V6 verification:
    - A batch with auto_merge=false and status=planning
    - One item in awaiting_merge_approval state

    If BATCH-D-0001 already exists with auto_merge=false and has CR-00001 in
    awaiting_merge_approval state, this fixture is idempotent and does nothing.
    """
    project_id = "iw-ai-core"
    batch_id = "BATCH-D-0001"
    item_id = "CR-00001"

    batch = db.query(Batch).filter(Batch.project_id == project_id, Batch.id == batch_id).first()
    if batch is None:
        batch = Batch(
            project_id=project_id,
            id=batch_id,
            status="planning",
            auto_merge=False,
            max_parallel=1,
        )
        db.add(batch)
        db.flush()

    item = (
        db.query(WorkItem).filter(WorkItem.project_id == project_id, WorkItem.id == item_id).first()
    )
    if item is None:
        item = WorkItem(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.ChangeRequest,
            title="Ollama stub integration for E2E testing",
            status=WorkItemStatus.APPROVED,
        )
        db.add(item)
        db.flush()

    existing_link = (
        db.query(BatchItem)
        .filter(
            BatchItem.project_id == project_id,
            BatchItem.batch_id == batch_id,
            BatchItem.work_item_id == item_id,
        )
        .first()
    )
    if existing_link is None:
        batch_item = BatchItem(
            project_id=project_id,
            batch_id=batch_id,
            work_item_id=item_id,
            status="awaiting_merge_approval",
        )
        db.add(batch_item)
        db.flush()
    else:
        existing_link.status = "awaiting_merge_approval"

    merge_step = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.step_id == "MERGE",
        )
        .first()
    )
    if merge_step is None:
        merge_step = WorkflowStep(
            project_id=project_id,
            work_item_id=item_id,
            step_number=99,
            step_id="MERGE",
            agent_label="Merge",
            step_type=StepType.quality_validation,
            step_label="Merge to main",
        )
        db.add(merge_step)
        db.flush()

    step_run = (
        db.query(StepRun).filter(StepRun.step_id == merge_step.id, StepRun.run_number == 1).first()
    )
    if step_run is None:
        step_run = StepRun(
            step_id=merge_step.id,
            run_number=1,
            status=RunStatus.running,
            started_at=datetime.now(UTC),
        )
        db.add(step_run)

    db.commit()
