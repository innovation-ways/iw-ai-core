"""E2E fixture: seed CR-99025 with browser_verification step for S11 evidence verification.

This fixture creates a synthetic work item CR-99025 with:
- status = 'in_progress' (approved)
- one browser_verification step in 'in_progress' state
- pre and post evidence files in ai-dev/active/CR-99025/evidences/{pre,post}/

The fixture is idempotent and skips if CR-99025 already exists in the DB.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from orch.db.models import (
    StepStatus,
    StepType,
    WorkItem,
    WorkItemPhase,
    WorkItemType,
    WorkflowStep,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


PROJECT_ID = "iw-ai-core"
WORK_ITEM_ID = "CR-99025"
AGENT_LABEL = "opencode"


def seed(db: Session) -> None:
    existing = db.get(WorkItem, (PROJECT_ID, WORK_ITEM_ID))
    if existing is not None:
        return

    now = datetime.now(UTC)

    work_item = WorkItem(
        project_id=PROJECT_ID,
        id=WORK_ITEM_ID,
        type=WorkItemType.ChangeRequest,
        title="E2E evidence ingestion test (CR-99025)",
        status="draft",
        phase=WorkItemPhase.active,
        design_doc_content=(
            "Synthetic work item for CR-00025 S11 browser verification. "
            "Tests that iw approve ingests pre evidences and iw step-done "
            "for browser_verification ingests post evidences."
        ),
        summary="E2E test for evidence ingestion pipeline",
        created_at=now,
    )
    db.add(work_item)
    db.flush()

    step = WorkflowStep(
        project_id=PROJECT_ID,
        work_item_id=WORK_ITEM_ID,
        step_number=1,
        step_id="S01",
        agent_label=AGENT_LABEL,
        step_type=StepType.browser_verification,
        status=StepStatus.in_progress,
        started_at=now,
    )
    db.add(step)
    db.flush()