"""E2E fixture for I-00034 retry-history seed data.

Seeds two work items for the I-00034 browser verification:
  - I-00034-RETRY-DEMO  — incident with 2 step_runs + 1 fix_cycle → duration=10m30s
  - I-00034-HAPPY-DEMO  — incident with 1 step_run only           → duration=45s
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from orch.db.models import FixCycle, FixStatus, FixTrigger, RunStatus, StepRun, StepType, WorkflowStep, WorkItem, WorkItemType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"


def seed(db: Session) -> None:
    _seed_retry_demo(db)
    _seed_happy_demo(db)


def _seed_retry_demo(db: Session) -> None:
    existing = db.get(WorkItem, (PROJECT_ID, "I-00034-RETRY-DEMO"))
    if existing is not None:
        return

    now = datetime.now(UTC)

    wi = WorkItem(
        project_id=PROJECT_ID,
        id="I-00034-RETRY-DEMO",
        type=WorkItemType.Issue,
        title="I-00034 retry demo — step duration aggregation",
        status="completed",
        phase="done",
        created_at=now,
    )
    db.add(wi)
    db.flush()

    step = WorkflowStep(
        project_id=PROJECT_ID,
        work_item_id="I-00034-RETRY-DEMO",
        step_number=1,
        step_id="S01",
        agent_label="backend-impl",
        opencode_agent="backend-impl",
        step_type=StepType.implementation,
        status="completed",
        started_at=datetime(2026, 4, 22, 12, 10, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 22, 12, 10, 30, tzinfo=UTC),
    )
    db.add(step)
    db.flush()

    db.add(
        StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.failed,
            started_at=datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 2, 0, tzinfo=UTC),
        )
    )
    db.add(
        StepRun(
            step_id=step.id,
            run_number=2,
            status=RunStatus.completed,
            started_at=datetime(2026, 4, 22, 12, 10, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 10, 30, tzinfo=UTC),
        )
    )

    db.add(
        FixCycle(
            step_id=step.id,
            cycle_number=1,
            trigger_type=FixTrigger.code_review,
            status=FixStatus.completed,
            started_at=datetime(2026, 4, 22, 12, 3, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 12, 9, 0, tzinfo=UTC),
        )
    )


def _seed_happy_demo(db: Session) -> None:
    existing = db.get(WorkItem, (PROJECT_ID, "I-00034-HAPPY-DEMO"))
    if existing is not None:
        return

    now = datetime.now(UTC)

    wi = WorkItem(
        project_id=PROJECT_ID,
        id="I-00034-HAPPY-DEMO",
        type=WorkItemType.Issue,
        title="I-00034 happy path — single run, no fix cycles",
        status="completed",
        phase="done",
        created_at=now,
    )
    db.add(wi)
    db.flush()

    step = WorkflowStep(
        project_id=PROJECT_ID,
        work_item_id="I-00034-HAPPY-DEMO",
        step_number=1,
        step_id="S01",
        agent_label="backend-impl",
        opencode_agent="backend-impl",
        step_type=StepType.implementation,
        status="completed",
        started_at=datetime(2026, 4, 22, 14, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 22, 14, 0, 45, tzinfo=UTC),
    )
    db.add(step)
    db.flush()

    db.add(
        StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime(2026, 4, 22, 14, 0, 0, tzinfo=UTC),
            completed_at=datetime(2026, 4, 22, 14, 0, 45, tzinfo=UTC),
        )
    )
