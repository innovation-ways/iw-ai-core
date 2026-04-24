"""Fixture: partial-step-completion batch for I-00037 browser verification.

Creates:
  - Work item I-TEST-37 with 10 WorkflowStep rows (steps 1-3 completed, 4-10 pending)
  - Batch BATCH-TEST37 with status=executing and one BatchItem linking to I-TEST-37
    with status=in_progress

Expected percentage when fix is applied: 3/10 = 30%
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    StepStatus,
    WorkflowStep,
    WorkItem,
    WorkItemType,
)


def seed(db) -> None:  # noqa: ARG001
    project_id = "iw-ai-core"

    existing_item = db.get(WorkItem, (project_id, "I-TEST-37"))
    if existing_item is not None:
        return

    now = datetime.now(UTC)

    item = WorkItem(
        project_id=project_id,
        id="I-TEST-37",
        type=WorkItemType.Issue,
        title="Test item for I-00037 verification",
        status="in_progress",
        phase="active",
        design_doc_content="Test work item with partial step completion for browser verification.",
        summary="Test item for I-00037",
        created_at=now,
    )
    db.add(item)
    db.flush()

    step_data = [
        ("S01", "Backend", "backend-impl", 1, StepStatus.completed),
        ("S02", "Frontend", "frontend-impl", 2, StepStatus.completed),
        ("S03", "Tests", "tests-impl", 3, StepStatus.completed),
        ("S04", "CodeReview", "code-review-impl", 4, StepStatus.pending),
        ("S05", "QVBrowser", "qv-browser", 5, StepStatus.pending),
        ("S06", "BackendReview", "backend-review", 6, StepStatus.pending),
        ("S07", "FrontendReview", "frontend-review", 7, StepStatus.pending),
        ("S08", "CodeReviewFinal", "code-review-final-impl", 8, StepStatus.pending),
        ("S09", "QualityGate", "qv-gate", 9, StepStatus.pending),
        ("S10", "Merge", "merge-impl", 10, StepStatus.pending),
    ]

    for step_id, agent_label, opencode_agent, step_number, status in step_data:
        db.add(
            WorkflowStep(
                project_id=project_id,
                work_item_id="I-TEST-37",
                step_id=step_id,
                step_number=step_number,
                agent_label=agent_label,
                opencode_agent=opencode_agent,
                step_type="implementation",
                status=status,
            )
        )

    existing_batch = db.get(Batch, (project_id, "BATCH-TEST37"))
    if existing_batch is None:
        db.add(
            Batch(
                project_id=project_id,
                id="BATCH-TEST37",
                status=BatchStatus.executing,
                max_parallel=4,
                cli_tool="opencode",
                auto_publish=False,
                created_at=now,
                updated_at=now,
            )
        )
        db.flush()

    existing_item_check = db.scalar(
        select(BatchItem).where(
            BatchItem.batch_id == "BATCH-TEST37",
            BatchItem.work_item_id == "I-TEST-37",
        )
    )
    if existing_item_check is None:
        db.add(
            BatchItem(
                project_id=project_id,
                batch_id="BATCH-TEST37",
                work_item_id="I-TEST-37",
                execution_group=0,
                status=BatchItemStatus.executing,
                started_at=now,
            )
        )
