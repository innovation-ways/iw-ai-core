"""CR-00056 S22 E2E fixture — seed a work item with prompt_text StepRuns.

This fixture enables V1–V6 browser verifications without needing a
daemon-launched item. It creates:
  - WorkItem CR-00056-TEST (ChangeRequest)
  - WorkflowStep S04 with a non-synthetic step type
  - StepRun #1: prompt_text = "INITIAL PROMPT BODY — operator should see this in the modal."
  - StepRun #2: fix_prompt_text = "FIX-CYCLE PROMPT BODY — for cycle 1.",
                prompt_text = "INITIAL PROMPT BODY — operator should see this in the modal."
  - StepRun #3: prompt_text containing an XSS payload for V6

The steps table's has_prompt logic uses a window function (row_number desc)
that picks the latest run per step_id — so V4 needs at least one run with
fix_prompt_text set on a retry run.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    RunStatus,
    StepRun,
    StepType,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
    WorkflowStep,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"
ITEM_ID = "CR-00056-TEST"


def seed(db: Session) -> None:
    # --- WorkItem ---
    existing_item = db.get(WorkItem, (PROJECT_ID, ITEM_ID))
    now = datetime.now(UTC)
    if existing_item is None:
        wi = WorkItem(
            project_id=PROJECT_ID,
            id=ITEM_ID,
            type=WorkItemType.ChangeRequest,
            title="CR-00056 browser verification fixture",
            status=WorkItemStatus.completed,
            phase="done",
            design_doc_content="Fixture item for CR-00056 S22 browser verification.",
            summary="Fixture item",
            created_at=now,
        )
        db.add(wi)
        db.flush()  # ensure WI exists before we reference it
    else:
        wi = existing_item

    # --- Batch + BatchItem (WorkflowStep needs a parent BatchItem via work_item_id) ---
    batch_existing = db.get(Batch, (PROJECT_ID, "CR-00056-TEST-BATCH"))
    if batch_existing is None:
        batch = Batch(
            id="CR-00056-TEST-BATCH",
            project_id=PROJECT_ID,
            status=BatchStatus.completed,
            created_at=now,
        )
        db.add(batch)
        db.flush()
    else:
        batch = batch_existing

    bi_existing = db.execute(
        db.query(BatchItem).filter(
            BatchItem.project_id == PROJECT_ID,
            BatchItem.batch_id == "CR-00056-TEST-BATCH",
            BatchItem.work_item_id == ITEM_ID,
        )
    ).scalar_one_or_none()
    if bi_existing is None:
        bi = BatchItem(
            project_id=PROJECT_ID,
            batch_id="CR-00056-TEST-BATCH",
            work_item_id=ITEM_ID,
            status=BatchItemStatus.completed,
        )
        db.add(bi)
        db.flush()
    else:
        bi = bi_existing

    # --- WorkflowStep S04 ---
    step_existing = db.execute(
        db.query(WorkflowStep).filter(
            WorkflowStep.project_id == PROJECT_ID,
            WorkflowStep.work_item_id == ITEM_ID,
            WorkflowStep.step_id == "S04",
        )
    ).scalar_one_or_none()
    if step_existing is None:
        ws = WorkflowStep(
            project_id=PROJECT_ID,
            work_item_id=ITEM_ID,
            step_number=4,
            step_id="S04",
            agent_label="backend-impl",
            step_type=StepType.implementation,
            prompt_file="ai-dev/active/CR-00056-TEST/prompts/CR-00056-TEST_S04_Backend_prompt.md",
        )
        db.add(ws)
        db.flush()
    else:
        ws = step_existing

    step_db_id = ws.id

    # --- StepRun #1 (initial run with prompt_text) ---
    run1_existing = db.execute(
        db.query(StepRun).filter(
            StepRun.step_id == step_db_id,
            StepRun.run_number == 1,
        )
    ).scalar_one_or_none()
    if run1_existing is None:
        sr1 = StepRun(
            step_id=step_db_id,
            run_number=1,
            status=RunStatus.completed,
            prompt_text="INITIAL PROMPT BODY — operator should see this in the modal.",
            started_at=now,
            completed_at=now,
            duration_secs=1.0,
        )
        db.add(sr1)
        db.flush()
    else:
        run1_existing.prompt_text = "INITIAL PROMPT BODY — operator should see this in the modal."
        db.flush()

    # --- StepRun #2 (fix-cycle retry with fix_prompt_text) ---
    run2_existing = db.execute(
        db.query(StepRun).filter(
            StepRun.step_id == step_db_id,
            StepRun.run_number == 2,
        )
    ).scalar_one_or_none()
    if run2_existing is None:
        sr2 = StepRun(
            step_id=step_db_id,
            run_number=2,
            status=RunStatus.completed,
            prompt_text="INITIAL PROMPT BODY — operator should see this in the modal.",
            fix_prompt_text="FIX-CYCLE PROMPT BODY — for cycle 1.",
            started_at=now,
            completed_at=now,
            duration_secs=1.0,
        )
        db.add(sr2)
        db.flush()
    else:
        run2_existing.prompt_text = "INITIAL PROMPT BODY — operator should see this in the modal."
        run2_existing.fix_prompt_text = "FIX-CYCLE PROMPT BODY — for cycle 1."
        db.flush()

    # --- StepRun #3 (XSS payload for V6) ---
    run3_existing = db.execute(
        db.query(StepRun).filter(
            StepRun.step_id == step_db_id,
            StepRun.run_number == 3,
        )
    ).scalar_one_or_none()
    xss_payload = (
        "Prompt with XSS attempt: <script>alert(\"xss\")</script> — "
        "this should be escaped in the modal, not executed."
    )
    if run3_existing is None:
        sr3 = StepRun(
            step_id=step_db_id,
            run_number=3,
            status=RunStatus.completed,
            prompt_text=xss_payload,
            started_at=now,
            completed_at=now,
            duration_secs=1.0,
        )
        db.add(sr3)
        db.flush()
    else:
        run3_existing.prompt_text = xss_payload
        db.flush()
