"""E2E fixture: seed CR-99026 with draft status for oversize evidence test.

This fixture creates a synthetic work item CR-99026 with:
- status = 'draft' (not approved)
- No steps (just the work item in draft state)

Used to test V4: that iw approve hard-fails when an evidence file
exceeds IW_CORE_EVIDENCE_MAX_BYTES (default 5 MiB).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from orch.db.models import (
    WorkItem,
    WorkItemPhase,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


PROJECT_ID = "iw-ai-core"
WORK_ITEM_ID = "CR-99026"


def seed(db: Session) -> None:
    existing = db.get(WorkItem, (PROJECT_ID, WORK_ITEM_ID))
    if existing is not None:
        return

    now = datetime.now(UTC)

    work_item = WorkItem(
        project_id=PROJECT_ID,
        id=WORK_ITEM_ID,
        type=WorkItemType.ChangeRequest,
        title="E2E oversize evidence test (CR-99026)",
        status="draft",
        phase=WorkItemPhase.active,
        design_doc_content=(
            "Synthetic work item for CR-00025 S11 V4 verification. "
            "Tests that iw approve hard-fails when an evidence file "
            "exceeds IW_CORE_EVIDENCE_MAX_BYTES."
        ),
        summary="E2E test for oversize evidence rejection",
        created_at=now,
    )
    db.add(work_item)
    db.flush()
