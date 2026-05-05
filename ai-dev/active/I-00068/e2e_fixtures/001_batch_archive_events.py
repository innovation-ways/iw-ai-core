"""E2E fixture for I-00068: seed BATCH- events for browser verification.

Inserts:
- A Batch row with status=archived so the batch detail page returns 200 (not 404).
- Two DaemonEvent rows for the same batch:
  - entity_type=None  (legacy/buggy emission — the template fallback must route this to /batch/)
  - entity_type="batch" (correct emission — already routes to /batch/)
"""

from datetime import UTC, datetime

from sqlalchemy import select

from orch.db.models import Batch, BatchStatus, DaemonEvent


def seed(db) -> None:
    existing = db.get(Batch, ("iw-ai-core", "BATCH-99999"))
    if existing is not None:
        return

    now = datetime.now(UTC)

    existing_events = db.execute(
        select(DaemonEvent).where(
            DaemonEvent.project_id == "iw-ai-core",
            DaemonEvent.entity_id == "BATCH-99999",
        )
    ).scalars().all()
    if existing_events:
        return

    existing_batch = db.execute(
        select(Batch).where(
            Batch.project_id == "iw-ai-core",
            Batch.id == "BATCH-99999",
        )
    ).scalar_one_or_none()
    if existing_batch is None:
        batch = Batch(
            project_id="iw-ai-core",
            id="BATCH-99999",
            status=BatchStatus.archived,
            max_parallel=4,
            cli_tool="opencode",
            archived_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(batch)
        db.flush()

    row_none = DaemonEvent(
        project_id="iw-ai-core",
        event_type="batch_archived",
        entity_id="BATCH-99999",
        entity_type=None,
        message="Batch BATCH-99999 archived successfully",
        event_metadata={},
        created_at=now,
    )
    db.add(row_none)

    row_batch = DaemonEvent(
        project_id="iw-ai-core",
        event_type="batch_archiving_started",
        entity_id="BATCH-99999",
        entity_type="batch",
        message="Batch BATCH-99999 archiving started",
        event_metadata={},
        created_at=now,
    )
    db.add(row_batch)
    db.flush()
