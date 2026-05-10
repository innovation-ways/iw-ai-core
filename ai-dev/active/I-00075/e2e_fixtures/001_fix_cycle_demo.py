"""I-00075 fix-cycle demo fixture.

Seeds a synthetic completed item (I-99001) with 3 workflow steps and 2 fix
cycles on S02 so qv-browser can render the amber ↺SXX pill branch in
dashboard/templates/components/step_pipeline.html:33-41.

Idempotent: re-running the fixture on an already-seeded DB is a no-op.

Work item: I-99001 (outside the live iw next-id allocation range).

See ai-dev/active/I-00075/I-00075_Issue_Design.md for the full root-cause
analysis and acceptance criteria.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    FixCycle,
    FixStatus,
    FixTrigger,
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
WORK_ITEM_ID = "I-99001"
AGENT_LABEL = "opencode"


def seed(db: Session) -> None:
    # Idempotency guard — short-circuit if WorkflowStep rows already exist.
    existing = db.execute(
        select(WorkflowStep).where(
            WorkflowStep.project_id == PROJECT_ID,
            WorkflowStep.work_item_id == WORK_ITEM_ID,
        )
    ).scalars().first()
    if existing is not None:
        return

    now = datetime.now(UTC)

    # 1. Batch
    batch = Batch(
        project_id=PROJECT_ID,
        id="BATCH-I00075DEMO",
        status=BatchStatus.completed,
        max_parallel=4,
        cli_tool="opencode",
        auto_publish=False,
    )
    db.add(batch)
    db.flush()

    # 2. WorkItem (must be flushed before BatchItem due to FK constraint)
    work_item = WorkItem(
        project_id=PROJECT_ID,
        id=WORK_ITEM_ID,
        type=WorkItemType.Issue,
        title="Fix-cycle demo (I-00075 fixture)",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.done,
        summary=(
            "Synthetic item seeded by I-00075 fixture so qv-browser can render "
            "fix-cycle amber pills."
        ),
        design_doc_content=(
            "Synthetic demo item created by "
            "ai-dev/active/I-00075/e2e_fixtures/001_fix_cycle_demo.py for "
            "fix-cycle UI verification. See I-00075_Issue_Design.md."
        ),
        created_at=now,
    )
    db.add(work_item)
    db.flush()

    # 3. BatchItem (WorkItem must be flushed first due to FK constraint)
    batch_item = BatchItem(
        project_id=PROJECT_ID,
        batch_id="BATCH-I00075DEMO",
        work_item_id=WORK_ITEM_ID,
        execution_group=0,
        status=BatchItemStatus.merged,
    )
    db.add(batch_item)
    db.flush()

    # 4. WorkflowSteps: S01 (implementation), S02 (code_review), S03 (quality_validation)
    steps_data = [
        ("S01", 1, StepType.implementation),
        ("S02", 2, StepType.code_review),
        ("S03", 3, StepType.quality_validation),
    ]
    steps: dict[str, WorkflowStep] = {}
    for step_id_str, step_number, step_type in steps_data:
        step = WorkflowStep(
            project_id=PROJECT_ID,
            work_item_id=WORK_ITEM_ID,
            step_id=step_id_str,
            step_number=step_number,
            agent_label=AGENT_LABEL,
            step_type=step_type,
            status=StepStatus.completed,
            started_at=now,
            completed_at=now,
        )
        db.add(step)
        db.flush()
        steps[step_id_str] = step

    # 5. StepRuns: 1 run for S01, 3 runs for S02, 1 run for S03
    runs_data = [
        ("S01", 1),
        ("S02", 1),
        ("S02", 2),
        ("S02", 3),
        ("S03", 1),
    ]
    for step_id_str, run_number in runs_data:
        run = StepRun(
            step_id=steps[step_id_str].id,
            run_number=run_number,
            status=RunStatus.completed,
            cli_tool="opencode",
            started_at=now,
            completed_at=now,
        )
        db.add(run)
    db.flush()

    # 6. FixCycles: 2 cycles on S02 only (this is what triggers the amber pills)
    for cycle_number in (1, 2):
        cycle = FixCycle(
            step_id=steps["S02"].id,
            cycle_number=cycle_number,
            trigger_type=FixTrigger.code_review,
            status=FixStatus.completed,
            started_at=now,
            completed_at=now,
        )
        db.add(cycle)
    db.flush()
