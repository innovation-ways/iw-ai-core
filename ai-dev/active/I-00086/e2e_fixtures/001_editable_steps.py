"""Seed work items with editable/non-editable steps for browser verification.

Used by I-00086 S14 to verify runtime override UI interactions.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from orch.db.models import AgentRuntimeOption, StepStatus, StepType, WorkItem, WorkItemPhase, WorkItemStatus, WorkItemType, WorkflowStep

PROJECT_ID = "iw-ai-core"
EDITABLE_ITEM_ID = "I-99086"
ZERO_EDITABLE_ITEM_ID = "I-99087"


def _ensure_runtime_options(db: Session) -> tuple[int | None, int | None]:
    options = list(
        db.scalars(
            select(AgentRuntimeOption)
            .where(AgentRuntimeOption.enabled.is_(True))
            .order_by(AgentRuntimeOption.sort_order.asc(), AgentRuntimeOption.id.asc())
        )
    )
    if len(options) >= 2:
        return options[0].id, options[1].id

    first = options[0] if options else None
    if first is None:
        first = AgentRuntimeOption(
            cli_tool="opencode",
            model="gpt-5.3-codex",
            cli_label="OpenCode",
            model_label="GPT-5.3 Codex",
            display_name="OpenCode — GPT-5.3 Codex",
            is_default=True,
            enabled=True,
            sort_order=0,
        )
        db.add(first)
        db.flush()

    second = db.scalar(
        select(AgentRuntimeOption).where(
            AgentRuntimeOption.cli_tool == "claude",
            AgentRuntimeOption.model == "claude-sonnet-4",
        )
    )
    if second is None:
        second = AgentRuntimeOption(
            cli_tool="claude",
            model="claude-sonnet-4",
            cli_label="Claude",
            model_label="Claude Sonnet 4",
            display_name="Claude — Sonnet 4",
            is_default=False,
            enabled=True,
            sort_order=10,
        )
        db.add(second)
        db.flush()

    return first.id, second.id


def _ensure_item(
    db: Session,
    item_id: str,
    *,
    title: str,
    status: WorkItemStatus,
    phase: WorkItemPhase = WorkItemPhase.work,
) -> WorkItem:
    existing = db.get(WorkItem, (PROJECT_ID, item_id))
    if existing is not None:
        existing.title = title
        existing.status = status
        existing.phase = phase
        existing.design_doc_path = f"ai-dev/active/{item_id}/{item_id}_Issue_Design.md"
        return existing
    item = WorkItem(
        project_id=PROJECT_ID,
        id=item_id,
        type=WorkItemType.Issue,
        title=title,
        status=status,
        phase=phase,
        design_doc_path=f"ai-dev/active/{item_id}/{item_id}_Issue_Design.md",
    )
    db.add(item)
    db.flush()
    return item


def _ensure_step(
    db: Session,
    *,
    item_id: str,
    step_number: int,
    step_id: str,
    status: StepStatus,
    runtime_option_id: int | None,
) -> None:
    existing = db.scalar(
        select(WorkflowStep).where(
            WorkflowStep.project_id == PROJECT_ID,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.step_number == step_number,
        )
    )
    if existing is not None:
        existing.status = status
        existing.agent_runtime_option_id = runtime_option_id
        return
    db.add(
        WorkflowStep(
            project_id=PROJECT_ID,
            work_item_id=item_id,
            step_number=step_number,
            step_id=step_id,
            agent_label=f"Agent_{step_id}",
            opencode_agent="backend-impl",
            step_type=StepType.implementation,
            step_label=f"Step {step_id}",
            status=status,
            agent_runtime_option_id=runtime_option_id,
        )
    )


def seed(db: Session) -> None:
    opt_a, opt_b = _ensure_runtime_options(db)

    _ensure_item(
        db,
        EDITABLE_ITEM_ID,
        title="E2E fixture: editable runtime override rows",
        status=WorkItemStatus.approved,
    )
    _ensure_step(
        db,
        item_id=EDITABLE_ITEM_ID,
        step_number=1,
        step_id="S01",
        status=StepStatus.pending,
        runtime_option_id=opt_a,
    )
    _ensure_step(
        db,
        item_id=EDITABLE_ITEM_ID,
        step_number=2,
        step_id="S02",
        status=StepStatus.failed,
        runtime_option_id=opt_a,
    )
    _ensure_step(
        db,
        item_id=EDITABLE_ITEM_ID,
        step_number=3,
        step_id="S03",
        status=StepStatus.completed,
        runtime_option_id=opt_b,
    )

    _ensure_item(
        db,
        ZERO_EDITABLE_ITEM_ID,
        title="E2E fixture: zero editable rows",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.done,
    )
    _ensure_step(
        db,
        item_id=ZERO_EDITABLE_ITEM_ID,
        step_number=1,
        step_id="S01",
        status=StepStatus.completed,
        runtime_option_id=opt_a,
    )
    _ensure_step(
        db,
        item_id=ZERO_EDITABLE_ITEM_ID,
        step_number=2,
        step_id="S02",
        status=StepStatus.in_progress,
        runtime_option_id=opt_b,
    )
