"""CR-00066 S10 context tokens fixture — seeds context window usage data for browser verification.

Creates a work item with 3 steps:
  - S01: green bar (25% usage, 50K/200K)
  - S02: yellow bar (75% usage, 150K/200K)
  - S03: no data / dash (pending step, no step_runs)

The step_runs link to an AgentRuntimeOption (pi / minimax/MiniMax-M2.7,
context_window_tokens=200000). That row is resolved by its stable
(cli_tool, model) identity and created if absent, so the fixture works both
against a migration-seeded DB and a fresh ``create_all`` schema (the latter
is what tests/integration/test_e2e_seed.py exercises).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.db.models import (
    AgentRuntimeOption,
    Batch,
    BatchItem,
    BatchItemStatus,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


ITEM_ID = "CR-00066-S11-FIXTURE"
PROJECT_ID = "iw-ai-core"

# The runtime option the seeded step_runs reference. Identified by its stable
# (cli_tool, model) pair — never a hardcoded autoincrement id, which is only
# deterministic in a fully migration-seeded DB. context_window_tokens is what
# the progress bar divides the peak token count by to compute usage %.
_RUNTIME_CLI_TOOL = "pi"
_RUNTIME_MODEL = "minimax/MiniMax-M2.7"
_RUNTIME_CONTEXT_WINDOW = 200_000


def _get_or_create_runtime_option(db: Session) -> int:
    """Return the id of the pi/MiniMax runtime option, creating it if missing.

    A migration-seeded DB already has this row (seeded by 6d78323d0954, with
    context_window_tokens backfilled by 891343247f66); a fresh ``create_all``
    schema has an empty catalogue. Either way the step_runs need a valid FK
    target whose context_window_tokens is set.
    """
    option = db.scalar(
        select(AgentRuntimeOption).where(
            AgentRuntimeOption.cli_tool == _RUNTIME_CLI_TOOL,
            AgentRuntimeOption.model == _RUNTIME_MODEL,
        )
    )
    if option is None:
        option = AgentRuntimeOption(
            cli_tool=_RUNTIME_CLI_TOOL,
            model=_RUNTIME_MODEL,
            cli_label="Pi",
            model_label="MiniMax 2.7",
            display_name="Pi + MiniMax 2.7",
            is_default=False,
            enabled=True,
            sort_order=25,
            context_window_tokens=_RUNTIME_CONTEXT_WINDOW,
        )
        db.add(option)
        db.flush()  # assign option.id
    elif option.context_window_tokens is None:
        # Row exists but predates CR-00066's context-window backfill — set it
        # so the usage percentage is computable.
        option.context_window_tokens = _RUNTIME_CONTEXT_WINDOW
        db.flush()
    return option.id


def seed(db: Session) -> None:
    # Check if already seeded
    existing = db.get(WorkItem, (PROJECT_ID, ITEM_ID))
    if existing is not None:
        return  # idempotent

    runtime_option_id = _get_or_create_runtime_option(db)

    now = datetime.now(UTC)

    # WorkItem
    wi = WorkItem(
        project_id=PROJECT_ID,
        id=ITEM_ID,
        type=WorkItemType.ChangeRequest,
        title="CR-00066 S11 Fixture — Context Window Progress Bar",
        status="in_progress",
        phase="active",
        design_doc_content=(
            "Browser verification fixture for CR-00066 — Context Window "
            "Usage Progress Bar. Seeds green/yellow/no-data step variants."
        ),
        created_at=now,
    )
    db.add(wi)
    db.flush()  # get wi.id

    # Batch + BatchItem (required for setup/merge synthetic steps)
    batch = Batch(
        id="CR-00066-S11-BATCH",
        project_id=PROJECT_ID,
        status="approved",  # batch_status enum: planning/approved/executing/paused/completed/...
        created_at=now,
    )
    db.add(batch)
    db.flush()

    bi = BatchItem(
        project_id=PROJECT_ID,
        batch_id=batch.id,
        work_item_id=ITEM_ID,
        status=BatchItemStatus.executing,
        worktree_info={"path": f"/app/worktrees/{ITEM_ID}", "branch": "main"},
        started_at=now,
    )
    db.add(bi)
    db.flush()

    # S01: green bar — 50K peak / 200K window = 25%
    ws1 = WorkflowStep(
        project_id=PROJECT_ID,
        work_item_id=ITEM_ID,
        step_number=1,
        step_id="S01",
        agent_label="Green Zone Step",
        step_type=StepType.implementation,
        status=StepStatus.completed,
        started_at=now,
        completed_at=datetime(2026, 5, 21, 12, 10, tzinfo=UTC),
    )
    db.add(ws1)
    db.flush()

    sr1 = StepRun(
        step_id=ws1.id,
        run_number=1,
        status=RunStatus.completed,
        cli_tool="pi",
        agent_runtime_option_id=runtime_option_id,
        started_at=now,
        completed_at=datetime(2026, 5, 21, 12, 10, tzinfo=UTC),
        duration_secs=120.0,
        context_tokens_peak=50_000,
        context_tokens_last=50_000,
    )
    db.add(sr1)

    # S02: yellow bar — 150K peak / 200K window = 75%
    ws2 = WorkflowStep(
        project_id=PROJECT_ID,
        work_item_id=ITEM_ID,
        step_number=2,
        step_id="S02",
        agent_label="Yellow Zone Step",
        step_type=StepType.implementation,
        status=StepStatus.completed,
        started_at=datetime(2026, 5, 21, 12, 11, tzinfo=UTC),
        completed_at=datetime(2026, 5, 21, 12, 20, tzinfo=UTC),
    )
    db.add(ws2)
    db.flush()

    sr2 = StepRun(
        step_id=ws2.id,
        run_number=1,
        status=RunStatus.completed,
        cli_tool="pi",
        agent_runtime_option_id=runtime_option_id,
        started_at=datetime(2026, 5, 21, 12, 11, tzinfo=UTC),
        completed_at=datetime(2026, 5, 21, 12, 20, tzinfo=UTC),
        duration_secs=540.0,
        context_tokens_peak=150_000,
        context_tokens_last=150_000,
    )
    db.add(sr2)

    # S03: pending — no context data (dash)
    ws3 = WorkflowStep(
        project_id=PROJECT_ID,
        work_item_id=ITEM_ID,
        step_number=3,
        step_id="S03",
        agent_label="Pending Step",
        step_type=StepType.implementation,
        status=StepStatus.pending,
    )
    db.add(ws3)
    # No StepRun for S03 (pending/no-data)

    db.commit()
