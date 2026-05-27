from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.db.models import (
    FixCycle,
    FixStatus,
    FixTrigger,
    Project,
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
ITEM_ID = "I-00115-E2E-SCOPE"
STEP_ID = "S13"
VIOLATION_PATH = "dashboard/templates/components/scope_amend_modal.html"


def seed(db: Session) -> None:
    now = datetime.now(UTC)

    if db.get(Project, PROJECT_ID) is None:
        db.add(
            Project(
                id=PROJECT_ID,
                display_name="IW AI Core (E2E)",
                repo_root="/app",
                config={},
                enabled=True,
            )
        )
        db.flush()

    item = db.get(WorkItem, (PROJECT_ID, ITEM_ID))
    if item is None:
        item = WorkItem(
            project_id=PROJECT_ID,
            id=ITEM_ID,
            type=WorkItemType.Issue,
            title="I-00115 E2E scope-blocked fixture",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
            created_at=now,
        )
        db.add(item)
        db.flush()
    else:
        item.status = WorkItemStatus.in_progress
        item.phase = WorkItemPhase.active

    step = (
        db.execute(
            select(WorkflowStep).where(
                WorkflowStep.project_id == PROJECT_ID,
                WorkflowStep.work_item_id == ITEM_ID,
                WorkflowStep.step_id == STEP_ID,
            )
        )
        .scalars()
        .first()
    )

    if step is None:
        step = WorkflowStep(
            project_id=PROJECT_ID,
            work_item_id=ITEM_ID,
            step_number=13,
            step_id=STEP_ID,
            agent_label="qv-browser",
            step_type=StepType.browser_verification,
            gate="browser-verification",
        )
        db.add(step)
        db.flush()

    step.status = StepStatus.needs_fix
    step.started_at = None
    step.completed_at = None

    run = (
        db.execute(
            select(StepRun).where(StepRun.step_id == step.id).order_by(StepRun.run_number.desc())
        )
        .scalars()
        .first()
    )
    if run is None:
        db.add(
            StepRun(
                step_id=step.id,
                run_number=1,
                status=RunStatus.failed,
                worktree_path="/app",
                started_at=now,
                completed_at=now,
            )
        )
    else:
        run.status = RunStatus.failed
        run.started_at = now
        run.completed_at = now

    cycle = (
        db.execute(
            select(FixCycle)
            .where(FixCycle.step_id == step.id)
            .order_by(FixCycle.cycle_number.desc())
        )
        .scalars()
        .first()
    )
    if cycle is None:
        db.add(
            FixCycle(
                step_id=step.id,
                cycle_number=1,
                status=FixStatus.escalated,
                trigger_type=FixTrigger.quality_validation,
                fix_metadata={"scope_violations": [VIOLATION_PATH]},
                started_at=now,
                completed_at=now,
            )
        )
    else:
        cycle.status = FixStatus.escalated
        cycle.trigger_type = FixTrigger.quality_validation
        cycle.fix_metadata = {"scope_violations": [VIOLATION_PATH]}
        cycle.started_at = now
        cycle.completed_at = now

    db.flush()
