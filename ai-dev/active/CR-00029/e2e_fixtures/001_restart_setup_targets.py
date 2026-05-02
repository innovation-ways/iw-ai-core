"""E2E fixture for CR-00029 browser verification.

Seeds two items needed for the Restart Setup button verification:
- CR29-A: restartable (button should appear) - BatchItem failed with all steps pending
- CR29-B: not restartable (button should NOT appear) - at least one step completed

Both items share batch BATCH-CR29 (status=completed_with_errors).
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

PROJECT_ID = "iw-ai-core"
BATCH_ID = "BATCH-CR29"


def seed(db: Session) -> None:
    # --- Ensure batch exists ---
    batch = db.get(Batch, (PROJECT_ID, BATCH_ID))
    if batch is None:
        batch = Batch(
            project_id=PROJECT_ID,
            id=BATCH_ID,
            status=BatchStatus.completed_with_errors,
            max_parallel=4,
            cli_tool="opencode",
        )
        db.add(batch)
        db.flush()  # ensure Batch exists before BatchItem FK

    # --- Item CR29-A: restartable (failed, all steps pending) ---
    item_a = db.get(WorkItem, (PROJECT_ID, "CR29-A"))
    if item_a is None:
        item_a = WorkItem(
            project_id=PROJECT_ID,
            id="CR29-A",
            type=WorkItemType.ChangeRequest,
            title="CR-00029 fixture A (restartable)",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
        )
        db.add(item_a)
        db.flush()  # ensure WorkItem exists before BatchItem FK

    bi_a = db.execute(
        BatchItem.__table__.select()
        .where(
            BatchItem.project_id == PROJECT_ID,
            BatchItem.batch_id == BATCH_ID,
            BatchItem.work_item_id == "CR29-A",
        )
    ).mappings().fetchone()

    if bi_a is None:
        bi_a = BatchItem(
            project_id=PROJECT_ID,
            batch_id=BATCH_ID,
            work_item_id="CR29-A",
            status=BatchItemStatus.failed,  # cascade failure
            execution_group=0,
        )
        db.add(bi_a)
        db.flush()
        # Refresh to get PK
        bi_a = db.execute(
            BatchItem.__table__.select()
            .where(
                BatchItem.project_id == PROJECT_ID,
                BatchItem.batch_id == BATCH_ID,
                BatchItem.work_item_id == "CR29-A",
            )
        ).mappings().fetchone()
    else:
        # Update status to failed
        db.execute(
            BatchItem.__table__.update()
            .where(BatchItem.id == bi_a["id"])
            .values(status=BatchItemStatus.failed)
        )

    # WorkflowSteps for CR29-A: 3 steps, all pending
    existing_steps_a = db.execute(
        WorkflowStep.__table__.select()
        .where(
            WorkflowStep.project_id == PROJECT_ID,
            WorkflowStep.work_item_id == "CR29-A",
        )
    ).mappings().fetchall()

    if len(existing_steps_a) < 3:
        # Clear any existing
        if existing_steps_a:
            for s in existing_steps_a:
                db.execute(
                    WorkflowStep.__table__.delete()
                    .where(WorkflowStep.id == s["id"])
                )
        for i, (step_id, label) in enumerate(
            [("S01", "Implementation"), ("S02", "Code Review"), ("S03", "Frontend")], start=0
        ):
            ws = WorkflowStep(
                project_id=PROJECT_ID,
                work_item_id="CR29-A",
                step_number=i,
                step_id=step_id,
                agent_label=label,
                step_type=StepType.implementation,  # placeholder
                status=StepStatus.pending,
            )
            db.add(ws)

    # Ensure WorkItem status is failed
    db.execute(
        WorkItem.__table__.update()
        .where(WorkItem.project_id == PROJECT_ID, WorkItem.id == "CR29-A")
        .values(status=WorkItemStatus.failed)
    )

    # --- Item CR29-B: NOT restartable (completed, one step done) ---
    item_b = db.get(WorkItem, (PROJECT_ID, "CR29-B"))
    if item_b is None:
        item_b = WorkItem(
            project_id=PROJECT_ID,
            id="CR29-B",
            type=WorkItemType.ChangeRequest,
            title="CR-00029 fixture B (post-setup)",
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.done,
        )
        db.add(item_b)
        db.flush()  # ensure WorkItem exists before BatchItem FK

    bi_b = db.execute(
        BatchItem.__table__.select()
        .where(
            BatchItem.project_id == PROJECT_ID,
            BatchItem.batch_id == BATCH_ID,
            BatchItem.work_item_id == "CR29-B",
        )
    ).mappings().fetchone()

    if bi_b is None:
        bi_b = BatchItem(
            project_id=PROJECT_ID,
            batch_id=BATCH_ID,
            work_item_id="CR29-B",
            status=BatchItemStatus.completed,
            execution_group=0,
        )
        db.add(bi_b)
        db.flush()
        bi_b = db.execute(
            BatchItem.__table__.select()
            .where(
                BatchItem.project_id == PROJECT_ID,
                BatchItem.batch_id == BATCH_ID,
                BatchItem.work_item_id == "CR29-B",
            )
        ).mappings().fetchone()
    else:
        db.execute(
            BatchItem.__table__.update()
            .where(BatchItem.id == bi_b["id"])
            .values(status=BatchItemStatus.completed)
        )

    # WorkflowSteps for CR29-B: 3 steps, S01 completed
    existing_steps_b = db.execute(
        WorkflowStep.__table__.select()
        .where(
            WorkflowStep.project_id == PROJECT_ID,
            WorkflowStep.work_item_id == "CR29-B",
        )
    ).mappings().fetchall()

    if len(existing_steps_b) < 3:
        if existing_steps_b:
            for s in existing_steps_b:
                db.execute(
                    WorkflowStep.__table__.delete()
                    .where(WorkflowStep.id == s["id"])
                )
        now = datetime.now(UTC)
        steps_data = [
            ("S01", "Implementation", StepStatus.completed, now, now),
            ("S02", "Code Review", StepStatus.in_progress, now, None),
            ("S03", "Tests", StepStatus.pending, None, None),
        ]
        for i, (step_id, label, status, started, completed) in enumerate(steps_data):
            ws = WorkflowStep(
                project_id=PROJECT_ID,
                work_item_id="CR29-B",
                step_number=i,
                step_id=step_id,
                agent_label=label,
                step_type=StepType.implementation,
                status=status,
                started_at=started,
                completed_at=completed,
            )
            db.add(ws)

    db.execute(
        WorkItem.__table__.update()
        .where(WorkItem.project_id == PROJECT_ID, WorkItem.id == "CR29-B")
        .values(status=WorkItemStatus.completed)
    )

    db.commit()