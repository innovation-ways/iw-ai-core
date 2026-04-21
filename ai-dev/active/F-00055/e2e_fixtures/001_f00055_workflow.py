"""E2E fixture: seed F-00055 workflow steps, runs, and fix cycles for S18 browser verification.

The test `test_f00055_workflow_fixture` asserts:
- 18 steps total (S01–S18)
- S10×2, S11×2, S13×3, S16×2, S18×6 step runs
- S11×1, S13×2, S16×1, S18×2 fix cycles
- hotspots in execution_report

This fixture is idempotent and mirrors the retry/retry-chain data from
the F-00055 design doc (retry counts per step).
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
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


PROJECT_ID = "iw-ai-core"
WORK_ITEM_ID = "F-00055"
AGENT_LABEL = "opencode"


def seed(db: Session) -> None:
    existing = (
        db.execute(
            select(WorkflowStep).where(
                WorkflowStep.project_id == PROJECT_ID,
                WorkflowStep.work_item_id == WORK_ITEM_ID,
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        return

    now = datetime.now(UTC)

    batch = Batch(
        project_id=PROJECT_ID,
        id="BATCH-F00055",
        status=BatchStatus.completed,
        max_parallel=4,
        cli_tool="opencode",
        auto_publish=False,
    )
    db.add(batch)
    db.flush()

    batch_item = BatchItem(
        project_id=PROJECT_ID,
        batch_id=batch.id,
        work_item_id=WORK_ITEM_ID,
        execution_group=0,
        status=BatchItemStatus.merged,
    )
    db.add(batch_item)
    db.flush()

    step_defs = [
        ("S01", 1, StepType.implementation, StepStatus.completed),
        ("S02", 2, StepType.code_review, StepStatus.completed),
        ("S03", 3, StepType.quality_validation, StepStatus.completed),
        ("S04", 4, StepType.code_review, StepStatus.completed),
        ("S05", 5, StepType.quality_validation, StepStatus.completed),
        ("S06", 6, StepType.code_review, StepStatus.completed),
        ("S07", 7, StepType.quality_validation, StepStatus.completed),
        ("S08", 8, StepType.code_review, StepStatus.completed),
        ("S09", 9, StepType.quality_validation, StepStatus.completed),
        ("S10", 10, StepType.quality_validation, StepStatus.completed),
        ("S11", 11, StepType.code_review_final, StepStatus.completed),
        ("S12", 12, StepType.code_review_fix_final, StepStatus.completed),
        ("S13", 13, StepType.quality_validation, StepStatus.completed),
        ("S14", 14, StepType.quality_validation, StepStatus.completed),
        ("S15", 15, StepType.quality_validation, StepStatus.completed),
        ("S16", 16, StepType.quality_validation, StepStatus.completed),
        ("S17", 17, StepType.quality_validation, StepStatus.completed),
        ("S18", 18, StepType.browser_verification, StepStatus.completed),
    ]

    step_map: dict[str, WorkflowStep] = {}

    for step_id, step_number, step_type, status in step_defs:
        ws = WorkflowStep(
            project_id=PROJECT_ID,
            work_item_id=WORK_ITEM_ID,
            step_number=step_number,
            step_id=step_id,
            agent_label=AGENT_LABEL,
            step_type=step_type,
            status=status,
            started_at=now,
            completed_at=now,
        )
        db.add(ws)
        db.flush()
        step_map[step_id] = ws

    retry_runs: dict[str, int] = {
        "S10": 2,
        "S11": 2,
        "S13": 3,
        "S16": 2,
        "S18": 6,
    }

    for step_id, total_runs in retry_runs.items():
        step = step_map[step_id]
        for i in range(total_runs):
            run = StepRun(
                step_id=step.id,
                run_number=i + 1,
                status=RunStatus.completed,
                started_at=now,
                completed_at=now,
                cli_tool=AGENT_LABEL,
            )
            db.add(run)
        db.flush()

    retry_cycles: dict[str, int] = {
        "S11": 1,
        "S13": 2,
        "S16": 1,
        "S18": 2,
    }

    for step_id, cycle_count in retry_cycles.items():
        step = step_map[step_id]
        for i in range(cycle_count):
            cycle = FixCycle(
                step_id=step.id,
                cycle_number=i + 1,
                trigger_type=FixTrigger.quality_validation,
                status=FixStatus.completed,
                started_at=now,
                completed_at=now,
            )
            db.add(cycle)
        db.flush()
