"""Fixture for I-00031 browser verification: seed daemon_events for Recent Activity routing tests."""

from datetime import UTC, datetime

from sqlalchemy import select

from orch.db.models import Batch, BatchStatus, DaemonEvent, WorkItem

PROJECT_ID = "iw-ai-core"
BATCH_ID = "BATCH-E2E-00001"
WORK_ITEM_ID = "F-00055"
LEGACY_ENTITY_ID = "LEGACY-1"


def seed(db) -> None:
    now = datetime.now(UTC)

    batch = db.scalars(
        select(Batch).where(Batch.project_id == PROJECT_ID, Batch.id == BATCH_ID)
    ).first()
    if batch is None:
        batch = Batch(
            project_id=PROJECT_ID,
            id=BATCH_ID,
            status=BatchStatus.approved,
            max_parallel=4,
            cli_tool="opencode",
            auto_publish=False,
            created_at=now,
            updated_at=now,
        )
        db.add(batch)
        db.flush()

    work_item = db.get(WorkItem, (PROJECT_ID, WORK_ITEM_ID))
    if work_item is None:
        raise RuntimeError(f"WorkItem {WORK_ITEM_ID} not found in project {PROJECT_ID}")

    existing_batch_event = db.scalar(
        select(DaemonEvent).where(
            DaemonEvent.project_id == PROJECT_ID,
            DaemonEvent.entity_type == "batch",
            DaemonEvent.entity_id == BATCH_ID,
        )
    )
    if existing_batch_event is None:
        db.add(
            DaemonEvent(
                project_id=PROJECT_ID,
                event_type="batch_approved",
                entity_type="batch",
                entity_id=BATCH_ID,
                message="Batch approved",
                created_at=now,
            )
        )

    existing_wi_event = db.scalar(
        select(DaemonEvent).where(
            DaemonEvent.project_id == PROJECT_ID,
            DaemonEvent.entity_type == "work_item",
            DaemonEvent.entity_id == WORK_ITEM_ID,
        )
    )
    if existing_wi_event is None:
        db.add(
            DaemonEvent(
                project_id=PROJECT_ID,
                event_type="step_completed",
                entity_type="work_item",
                entity_id=WORK_ITEM_ID,
                message="Step completed",
                created_at=now,
            )
        )

    existing_legacy_event = db.scalar(
        select(DaemonEvent).where(
            DaemonEvent.project_id == PROJECT_ID,
            DaemonEvent.entity_type.is_(None),
            DaemonEvent.entity_id == LEGACY_ENTITY_ID,
        )
    )
    if existing_legacy_event is None:
        db.add(
            DaemonEvent(
                project_id=PROJECT_ID,
                event_type="daemon_poll",
                entity_type=None,
                entity_id=LEGACY_ENTITY_ID,
                message="Legacy poll event",
                created_at=now,
            )
        )
