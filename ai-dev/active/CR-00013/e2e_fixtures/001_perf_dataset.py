"""E2E fixture for CR-00013 — seed ≥5 projects, a batch with ≥10 items, and
≥10 workflow steps per item so the V4/V5 bounded-query verifications have
meaningful data to exercise.

The S15 qv-browser agent flagged V4 (project selector) and V5 (batch/item
detail) as ENV_DATA_MISSING because the baseline E2E seed only ships the
single `iw-ai-core` project. This fixture adds five synthetic projects with
realistic batch/item/step topology.

Idempotent: re-running the fixture is a no-op once the perf batch exists.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
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


PROJECTS: list[tuple[str, str]] = [
    ("perf-innoforge", "Perf InnoForge"),
    ("perf-cv", "Perf CV"),
    ("perf-docs", "Perf Docs"),
    ("perf-website", "Perf Website"),
    ("perf-api", "Perf API"),
]

ITEMS_PER_BATCH = 12
STEPS_PER_ITEM = 12
PERF_BATCH_ID = "BATCH-PERF-00001"
PERF_BATCH_PROJECT = "perf-innoforge"
AGENT_LABEL = "opencode"


def _seed_projects(db: Session, now: datetime) -> None:
    for project_id, display_name in PROJECTS:
        if db.get(Project, project_id) is not None:
            continue
        db.add(
            Project(
                id=project_id,
                display_name=display_name,
                repo_root=f"/tmp/perf/{project_id}",  # noqa: S108
                config={},
                enabled=True,
            )
        )
    db.flush()


def _seed_work_items(db: Session, project_id: str, now: datetime) -> list[str]:
    item_ids: list[str] = []
    for i in range(ITEMS_PER_BATCH):
        item_id = f"{project_id.upper()}-PERF-{i + 1:03d}"
        item_ids.append(item_id)
        if db.get(WorkItem, (project_id, item_id)) is not None:
            continue
        db.add(
            WorkItem(
                project_id=project_id,
                id=item_id,
                type=WorkItemType.Feature,
                title=f"Perf item {i + 1} for {project_id}",
                status=WorkItemStatus.in_progress,
                phase=WorkItemPhase.work,
                created_at=now - timedelta(minutes=(ITEMS_PER_BATCH - i) * 5),
            )
        )
    db.flush()
    return item_ids


def _seed_workflow_steps(db: Session, project_id: str, item_id: str, now: datetime) -> None:
    existing = db.execute(
        select(WorkflowStep.id)
        .where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
        )
        .limit(1)
    ).first()
    if existing is not None:
        return
    for n in range(STEPS_PER_ITEM):
        step_number = n + 1
        if n < STEPS_PER_ITEM - 2:
            status = StepStatus.completed
            started = now - timedelta(minutes=(STEPS_PER_ITEM - n) * 2)
            completed = started + timedelta(minutes=1)
        elif n == STEPS_PER_ITEM - 2:
            status = StepStatus.in_progress
            started = now - timedelta(minutes=1)
            completed = None
        else:
            status = StepStatus.pending
            started = None
            completed = None
        db.add(
            WorkflowStep(
                project_id=project_id,
                work_item_id=item_id,
                step_number=step_number,
                step_id=f"S{step_number:02d}",
                agent_label=AGENT_LABEL,
                step_type=StepType.implementation,
                status=status,
                started_at=started,
                completed_at=completed,
            )
        )
    db.flush()


def _seed_perf_batch(db: Session, item_ids: list[str], now: datetime) -> None:
    if db.get(Batch, (PERF_BATCH_PROJECT, PERF_BATCH_ID)) is not None:
        return
    db.add(
        Batch(
            project_id=PERF_BATCH_PROJECT,
            id=PERF_BATCH_ID,
            status=BatchStatus.executing,
            max_parallel=4,
            cli_tool="opencode",
            auto_publish=False,
            created_at=now - timedelta(hours=2),
        )
    )
    db.flush()
    for idx, item_id in enumerate(item_ids):
        db.add(
            BatchItem(
                project_id=PERF_BATCH_PROJECT,
                batch_id=PERF_BATCH_ID,
                work_item_id=item_id,
                execution_group=idx // 4,
                status=BatchItemStatus.executing if idx < 4 else BatchItemStatus.pending,
                started_at=now - timedelta(minutes=30) if idx < 4 else None,
            )
        )
    db.flush()


def _seed_step_runs(db: Session, project_id: str, item_id: str, now: datetime) -> None:
    existing = db.execute(
        select(StepRun.id)
        .join(WorkflowStep, WorkflowStep.id == StepRun.step_id)
        .where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
        )
        .limit(1)
    ).first()
    if existing is not None:
        return
    steps = (
        db.execute(
            select(WorkflowStep).where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
                WorkflowStep.status.in_((StepStatus.completed, StepStatus.in_progress)),
            )
        )
        .scalars()
        .all()
    )
    for step in steps:
        status = RunStatus.completed if step.status == StepStatus.completed else RunStatus.running
        db.add(
            StepRun(
                step_id=step.id,
                run_number=1,
                status=status,
                started_at=step.started_at or now,
                completed_at=step.completed_at,
                cli_tool=AGENT_LABEL,
            )
        )
    db.flush()


def seed(db: Session) -> None:
    now = datetime.now(UTC)
    _seed_projects(db, now)
    for project_id, _ in PROJECTS:
        item_ids = _seed_work_items(db, project_id, now)
        for item_id in item_ids:
            _seed_workflow_steps(db, project_id, item_id, now)
            _seed_step_runs(db, project_id, item_id, now)
        if project_id == PERF_BATCH_PROJECT:
            _seed_perf_batch(db, item_ids, now)
