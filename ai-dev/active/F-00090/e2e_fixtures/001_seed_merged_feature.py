from __future__ import annotations

from datetime import UTC, datetime

from orch.db.models import WorkItem, WorkItemPhase, WorkItemStatus, WorkItemType

PROJECT_ID = "iw-ai-core"
FEATURE_ID = "F-00990"


def seed(db) -> None:
    now = datetime.now(UTC)
    existing = db.get(WorkItem, (PROJECT_ID, FEATURE_ID))
    if existing is None:
        db.add(
            WorkItem(
                project_id=PROJECT_ID,
                id=FEATURE_ID,
                type=WorkItemType.Feature,
                title="Seed merged feature for regression badge verification",
                status=WorkItemStatus.completed,
                phase=WorkItemPhase.done,
                summary="Fixture row for F-00090 browser verification",
                completed_at=now,
                created_at=now,
            )
        )
        return

    existing.type = WorkItemType.Feature
    existing.status = WorkItemStatus.completed
    existing.phase = WorkItemPhase.done
    existing.completed_at = now
    if not existing.title:
        existing.title = "Seed merged feature for regression badge verification"
