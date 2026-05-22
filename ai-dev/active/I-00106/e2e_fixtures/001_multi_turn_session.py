"""I-00106 fixture: a pi step with a multi-turn session log.

The log has TWO turns — oldest turn first, newest turn last —
so that newest-first ordering can be verified in the browser.
The marker strings make ordering assertions unambiguous.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
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


def seed(db: Session) -> None:
    # Check if the fixture already exists (idempotent)
    existing = db.query(WorkItem).filter(
        WorkItem.project_id == "iw-ai-core",
        WorkItem.id == "I-00106-fixture",
    ).first()
    if existing is not None:
        return

    # ---- Work item -------------------------------------------------------
    item = WorkItem(
        project_id="iw-ai-core",
        id="I-00106-fixture",
        type=WorkItemType.Issue,
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        title="Agent Session Log modal verification fixture",
    )
    db.add(item)

    # Flush so the WorkItem gets an ID before we reference it
    db.flush()

    # ---- Batch + BatchItem (required for work items) ----------------------
    batch = db.query(Batch).filter(Batch.id == "BATCH-I-00106-FIXTURE").first()
    if batch is None:
        batch = Batch(
            id="BATCH-I-00106-FIXTURE",
            project_id="iw-ai-core",
            status="completed",
        )
        db.add(batch)
        db.flush()

    bi = BatchItem(
        project_id="iw-ai-core",
        batch_id="BATCH-I-00106-FIXTURE",
        work_item_id="I-00106-fixture",
        status=BatchItemStatus.completed,
    )
    db.add(bi)

    # ---- Workflow step ---------------------------------------------------
    step = WorkflowStep(
        project_id="iw-ai-core",
        work_item_id="I-00106-fixture",
        step_id="S02",
        step_number=2,
        agent_label="backend-impl",
        step_type=StepType.implementation,
        status=StepStatus.completed,
    )
    db.add(step)
    db.flush()

    # ---- JSONL session log: TWO turns ------------------------------------
    # Turn 1 (OLDEST): a simple thinking + assistant reply
    # Turn 2 (NEWEST): thinking + tool_call + tool_result + assistant reply
    #
    # The "marker" strings let us assert ordering without guessing DOM indices.
    # After the fix, turn 2 appears at the top of the modal.
    log_lines = [
        # Turn 1
        '{"type":"thinking","text":"OLDEST_TURN_THOUGHT"}',
        '{"type":"message","message":{"role":"assistant","content":[{"type":"text","text":"OLDEST_TURN_MARKER"}]}}',
        # Turn 2
        '{"type":"thinking","text":"NEWEST_TURN_THOUGHT"}',
        '{"type":"tool_call","tool":"bash","args":{"command":"echo newest-turn-action"}}',
        '{"type":"tool_result","result":"newest-tool-output"}',
        '{"type":"message","message":{"role":"assistant","content":[{"type":"text","text":"NEWEST_TURN_MARKER"}]}}',
    ]
    log_content = "\n".join(log_lines)

    run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.completed,
        cli_tool="pi",
    )
    run.log_content = log_content
    db.add(run)

    db.commit()