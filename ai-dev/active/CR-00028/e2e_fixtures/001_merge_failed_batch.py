"""E2E fixture: seed CR-00028 merge_failed state for S15 browser verification.

Creates:
  - WorkItem CR-00028-S15 (in_progress, active)
  - Batch BATCH-CR00028-S15 (executing)
  - BatchItem I1 (CR-00028-S15): merge_failed, execution_group=0
  - BatchItem I2 (CR-00028-S15-2): pending, execution_group=1  (cascade victim)
  - WorkItem CR-00028-S15-2 (pending, for I2)
  - Legacy Batch BATCH-CR29 (completed_with_errors) with CR29-A in failed (regression test)

Verifications V1..V6:
  V1: merge_failed badge is amber/warning (not red)
  V2: Retry Merge button exists on item overview (hx-get confirm-modal pattern)
  V3: Abandon button uses confirm-modal pattern (no hx-confirm)
  V4: Retry Merge transitions item out of merge_failed
  V5: Abandon triggers cascade (I2 becomes failed)
  V6: No regressions on batches list

The fixture is idempotent — skips if WorkItem already exists.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    WorkItem,
    WorkItemPhase,
    WorkItemType,
)

PROJECT_ID = "iw-ai-core"

# I1 — merge_failed item (group 0)
ITEM1_ID = "CR-00028-S15"
ITEM2_ID = "CR-00028-S15-2"
BATCH_ID = "BATCH-CR00028-S15"
BATCH_ITEM1_ID = None  # autoincrement
BATCH_ITEM2_ID = None  # autoincrement


def seed(db: Session) -> None:
    # Idempotency check
    existing = db.get(WorkItem, (PROJECT_ID, ITEM1_ID))
    if existing is not None:
        return

    now = datetime.now(UTC)

    # ---- WorkItems -------------------------------------------------------
    wi1 = WorkItem(
        project_id=PROJECT_ID,
        id=ITEM1_ID,
        type=WorkItemType.ChangeRequest,
        title="CR-00028 S15 merge_failed verification item",
        status="in_progress",
        phase=WorkItemPhase.active,
        design_doc_content=(
            "Synthetic work item for CR-00028 S15 browser verification. "
            "Tests: merge_failed badge renders distinctly from failed; "
            "Retry Merge and Abandon buttons use confirm-modal pattern; "
            "Retry Merge transitions item; Abandon triggers cascade."
        ),
        summary="S15 browser verification for merge_failed state",
        created_at=now,
    )
    db.add(wi1)

    wi2 = WorkItem(
        project_id=PROJECT_ID,
        id=ITEM2_ID,
        type=WorkItemType.ChangeRequest,
        title="CR-00028 S15 cascade victim item",
        status="approved",  # queued in batch (BatchItem is pending)
        phase=WorkItemPhase.active,
        design_doc_content="Synthetic cascade-victim item for V5 verification.",
        summary="Cascade victim for V5",
        created_at=now,
    )
    db.add(wi2)

    # ---- Batch -----------------------------------------------------------
    batch = Batch(
        project_id=PROJECT_ID,
        id=BATCH_ID,
        status=BatchStatus.executing,
        max_parallel=4,
        cli_tool="opencode",
        auto_publish=False,
        created_at=now,
    )
    db.add(batch)

    db.flush()

    # ---- BatchItems ------------------------------------------------------
    bi1 = BatchItem(
        project_id=PROJECT_ID,
        batch_id=BATCH_ID,
        work_item_id=ITEM1_ID,
        execution_group=0,
        status=BatchItemStatus.merge_failed,
        started_at=now,
        worktree_info={
            "path": "/app/worktrees/cr00028-s15",
            "branch": "worktree/cr00028-s15",
            "created_at": now.isoformat(),
        },
        notes="Synthetic merge_failed for S15 V1-V5 verification",
    )
    db.add(bi1)

    bi2 = BatchItem(
        project_id=PROJECT_ID,
        batch_id=BATCH_ID,
        work_item_id=ITEM2_ID,
        execution_group=1,
        status=BatchItemStatus.pending,
        started_at=None,
        worktree_info=None,
        notes=None,
    )
    db.add(bi2)

    db.flush()