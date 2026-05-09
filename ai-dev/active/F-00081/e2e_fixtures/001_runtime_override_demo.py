"""E2E fixture: F-00081 V3/V5 — item with mixed step statuses for dropdown lock testing.

Creates F-00099 with completed steps (S01, S02) and pending steps (S03, S04).
step_runs entries for S01/S02 so those steps show read-only CLI/Model badges.
No item-level override so V7 default-placeholder is also verifiable on this item.

Run via: docker compose -p "$COMPOSE_PROJECT_NAME" exec app \
           uv run python scripts/e2e_seed.py
"""

from __future__ import annotations

from datetime import UTC, datetime

import sys

from sqlalchemy import select

from orch.db.models import (
    AgentRuntimeOption,
    Batch,
    BatchItem,
    BatchStatus,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkItem,
    WorkItemPhase,
    WorkItemType,
    WorkflowStep,
)


def seed(db) -> None:
    project_id = "iw-ai-core"
    now = datetime.now(UTC)

    # Bail if already seeded
    existing = db.scalars(
        select(WorkItem).where(WorkItem.project_id == project_id, WorkItem.id == "F-00099")
    ).first()
    if existing is not None:
        return

    # --- Work item ---
    from orch.db.models import WorkItemStatus
    item = WorkItem(
        project_id=project_id,
        id="F-00099",
        type=WorkItemType.Feature,
        title="F-00081 E2E verification — mixed step statuses",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.work,
        design_doc_content="E2E fixture for F-00081 V3/V5 dropdown lock semantics.",
        summary="E2E fixture for F-00081 V3/V5",
        created_at=now,
    )
    db.add(item)
    db.flush()  # get the PK before we reference it

    # --- Batch so the item appears in the batch items tab ---
    batch = db.scalars(
        select(Batch).where(Batch.project_id == project_id, Batch.id == "BATCH-D-0004")
    ).first()
    if batch is None:
        batch = Batch(
            project_id=project_id,
            id="BATCH-D-0004",
            status=BatchStatus.executing,
            max_parallel=1,
            auto_merge=False,
            created_at=now,
        )
        db.add(batch)
        db.flush()

    existing_bi = db.scalars(
        select(BatchItem).where(
            BatchItem.project_id == project_id,
            BatchItem.batch_id == "BATCH-D-0004",
            BatchItem.work_item_id == "F-00099",
        )
    ).first()
    if existing_bi is None:
        bi = BatchItem(
            project_id=project_id,
            batch_id="BATCH-D-0004",
            work_item_id="F-00099",
        )
        db.add(bi)
        db.flush()

    # --- Workflow steps ---
    steps = [
        WorkflowStep(
            project_id=project_id,
            work_item_id="F-00099",
            step_number=1,
            step_id="S01",
            step_type=StepType.implementation,
            agent_label="opencode",
            status=StepStatus.completed,  # locked — read-only badge
            description="Step S01 (completed)",
            started_at=now,
            completed_at=now,
        ),
        WorkflowStep(
            project_id=project_id,
            work_item_id="F-00099",
            step_number=2,
            step_id="S02",
            step_type=StepType.implementation,
            agent_label="opencode",
            status=StepStatus.completed,  # locked — read-only badge
            description="Step S02 (completed)",
            started_at=now,
            completed_at=now,
        ),
        WorkflowStep(
            project_id=project_id,
            work_item_id="F-00099",
            step_number=3,
            step_id="S03",
            step_type=StepType.implementation,
            agent_label="opencode",
            status=StepStatus.pending,  # editable — <select>
            description="Step S03 (pending)",
        ),
        WorkflowStep(
            project_id=project_id,
            work_item_id="F-00099",
            step_number=4,
            step_id="S04",
            step_type=StepType.implementation,
            agent_label="opencode",
            status=StepStatus.pending,  # editable — <select>
            description="Step S04 (pending)",
        ),
    ]
    for step in steps:
        db.add(step)
    db.flush()  # assign auto-PK ids to steps before we reference them in step_runs

    # --- step_runs for completed steps (so they show read-only badges) ---
    # Find a real runtime option id from the seed data
    default_opt = db.scalars(
        select(AgentRuntimeOption).where(AgentRuntimeOption.is_default.is_(True))
    ).first()
    fallback_opts = list(
        db.scalars(select(AgentRuntimeOption).where(AgentRuntimeOption.enabled.is_(True)).limit(1)).all()
    )
    opt_to_use = default_opt or fallback_opts[0] if fallback_opts else None

    if opt_to_use:
        for step in [s for s in steps if s.status == StepStatus.completed]:
            run = StepRun(
                step_id=step.id,  # auto PK of workflow_steps
                run_number=1,
                status=RunStatus.completed,
                agent_runtime_option_id=opt_to_use.id,
                started_at=now,
                completed_at=now,
            )
            db.add(run)
    else:
        # No options seeded yet — log and skip step_runs (batches page will still show badges)
        sys.stdout.write(
            "e2e_fixture: no agent_runtime_options rows found; skipping step_runs seed.\n"
        )

    db.commit()
    sys.stdout.write("e2e_fixture: seeded F-00099 with 4 steps (S01,S02 completed, S03,S04 pending)\n")