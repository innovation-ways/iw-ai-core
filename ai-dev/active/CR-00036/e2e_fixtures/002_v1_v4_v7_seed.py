"""E2E fixtures: additional seed data for V1/V4/V7 browser verification."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    StepRun,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)


def seed(db: Session) -> None:
    """
    Fix V1/V4/V7 fixture gaps:

    V1: Needs approved WorkItem NOT in any batch, so the Queue page renders
        the "Create batch from selection" form and toggle.
        We create CR-00002 (approved, not in any batch).

    V4: Needs a batch with status=executing and auto_merge=false, so the
        Plan tab's auto-merge toggle is visibly disabled.
        We create BATCH-D-0002 (executing, auto_merge=false) and link it
        to a work item CR-00003 (executing status) so the batch stays
        locked in executing state (daemon won't advance an executing item
        unless the agent completes it, which won't happen in the E2E stack).

    V7: Needs a completed item in an auto_merge=true batch so the MERGE row
        shows "completed" with no Merge button.
        We rely on the existing CR-00001/F-00055 items already seeded as
        completed work items — but we need them in an auto_merge=true batch.
        We create BATCH-D-0003 (completed, auto_merge=true) with CR-00002
        already moved to the merged state.
    """
    project_id = "iw-ai-core"

    # --- V1: Approved item NOT in any batch ---
    _seed_v1_approved_item(db, project_id)

    # --- V4: Executing batch with auto_merge=false ---
    _seed_v4_executing_batch(db, project_id)

    # --- V7: Completed item in auto_merge=true batch ---
    _seed_v7_completed_auto_merge_true(db, project_id)

    db.commit()


def _seed_v1_approved_item(db: Session, project_id: str) -> None:
    """Seed CR-00002: approved, not in any batch."""
    item = db.get(WorkItem, (project_id, "CR-00002"))
    if item is None:
        item = WorkItem(
            project_id=project_id,
            id="CR-00002",
            type=WorkItemType.ChangeRequest,
            title="E2E verification item for V1 (auto_merge toggle on create batch form)",
            status=WorkItemStatus.approved,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db.add(item)
        db.flush()
    else:
        item.status = WorkItemStatus.approved
        item.phase = WorkItemPhase.active

    # Ensure it has workflow steps so batch creation works
    steps = list(
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == "CR-00002",
        )
        .all()
    )
    if not steps:
        for i, step_id in enumerate(["S01", "S02", "MERGE"], start=1):
            s = WorkflowStep(
                project_id=project_id,
                work_item_id="CR-00002",
                step_id=step_id,
                step_number=i,
                step_label=f"Step {step_id}",
                agent_label="opencode",
                step_type=StepType.quality_validation,
            )
            db.add(s)
        db.flush()


def _seed_v4_executing_batch(db: Session, project_id: str) -> None:
    """Seed BATCH-D-0002: executing, auto_merge=false — for V4 toggle-disable check."""
    batch = db.get(Batch, (project_id, "BATCH-D-0002"))
    if batch is None:
        batch = Batch(
            project_id=project_id,
            id="BATCH-D-0002",
            status=BatchStatus.executing,
            auto_merge=False,
            max_parallel=1,
        )
        db.add(batch)
        db.flush()

    # Work item for this batch
    item = db.get(WorkItem, (project_id, "CR-00003"))
    if item is None:
        item = WorkItem(
            project_id=project_id,
            id="CR-00003",
            type=WorkItemType.ChangeRequest,
            title="E2E verification item for V4 (executing batch, auto_merge toggle disabled)",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db.add(item)
        db.flush()

    # Link item to batch
    bi = (
        db.query(BatchItem)
        .filter(
            BatchItem.project_id == project_id,
            BatchItem.batch_id == "BATCH-D-0002",
            BatchItem.work_item_id == "CR-00003",
        )
        .first()
    )
    if bi is None:
        bi = BatchItem(
            project_id=project_id,
            batch_id="BATCH-D-0002",
            work_item_id="CR-00003",
            status=BatchItemStatus.executing,
        )
        db.add(bi)
        db.flush()

    # Workflow steps for CR-00003
    steps = list(
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == "CR-00003",
        )
        .all()
    )
    if not steps:
        for i, step_id in enumerate(["S01", "S02", "MERGE"], start=1):
            s = WorkflowStep(
                project_id=project_id,
                work_item_id="CR-00003",
                step_id=step_id,
                step_number=i,
                step_label=f"Step {step_id}",
                agent_label="opencode",
                step_type=StepType.quality_validation,
            )
            db.add(s)
        db.flush()

    # Running step run so daemon doesn't auto-advance
    step = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == "CR-00003",
            WorkflowStep.step_id == "S01",
        )
        .first()
    )
    if step:
        run = (
            db.query(StepRun)
            .filter(
                StepRun.step_id == step.id,
                StepRun.run_number == 1,
            )
            .first()
        )
        if run is None:
            run = StepRun(
                step_id=step.id,
                run_number=1,
                status="running",
                started_at=datetime.now(UTC),
            )
            db.add(run)


def _seed_v7_completed_auto_merge_true(db: Session, project_id: str) -> None:
    """Seed BATCH-D-0003: completed, auto_merge=true, with a merged item for V7."""
    batch = db.get(Batch, (project_id, "BATCH-D-0003"))
    if batch is None:
        batch = Batch(
            project_id=project_id,
            id="BATCH-D-0003",
            status=BatchStatus.completed,
            auto_merge=True,
            max_parallel=1,
        )
        db.add(batch)
        db.flush()

    # Work item that was merged
    item = db.get(WorkItem, (project_id, "CR-00004"))
    if item is None:
        item = WorkItem(
            project_id=project_id,
            id="CR-00004",
            type=WorkItemType.ChangeRequest,
            title="E2E verification item for V7 (auto_merge=true, merged, no Merge button)",
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.done,
            config={},
            depends_on=[],
            blocks=[],
        )
        db.add(item)
        db.flush()

    # Link item to batch as merged
    bi = (
        db.query(BatchItem)
        .filter(
            BatchItem.project_id == project_id,
            BatchItem.batch_id == "BATCH-D-0003",
            BatchItem.work_item_id == "CR-00004",
        )
        .first()
    )
    if bi is None:
        bi = BatchItem(
            project_id=project_id,
            batch_id="BATCH-D-0003",
            work_item_id="CR-00004",
            status=BatchItemStatus.merged,
        )
        db.add(bi)
        db.flush()

    # MERGE step with completed status
    merge_step = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == "CR-00004",
            WorkflowStep.step_id == "MERGE",
        )
        .first()
    )
    if merge_step is None:
        merge_step = WorkflowStep(
            project_id=project_id,
            work_item_id="CR-00004",
            step_id="MERGE",
            step_number=99,
            step_label="Merge to main",
            agent_label="Merge",
            step_type=StepType.quality_validation,
        )
        db.add(merge_step)
        db.flush()
