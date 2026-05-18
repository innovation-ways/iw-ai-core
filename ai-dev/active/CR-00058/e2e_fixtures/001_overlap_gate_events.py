"""CR-00058 E2E fixture: scope-overlap gate events.

Creates a batch with two batch_items that have the required DaemonEvents:
- One item with `item_held_for_scope` event
- One item with `item_overlap_allowed_by_policy` event

Both events reference overlapping paths to simulate the scope-overlap gate behavior.
"""

from datetime import datetime, UTC

from sqlalchemy.orm import Session

from orch.db.models import Batch, BatchItem, DaemonEvent, WorkItem


def seed(db: Session) -> None:
    project_id = "iw-ai-core"

    # Find an existing work item to use as a base, or create minimal ones
    existing_items = db.query(WorkItem).filter(WorkItem.project_id == project_id).limit(3).all()
    if not existing_items:
        print("[fixture] No work items found in iw-ai-core project, skipping fixture")
        return

    work_item_ids = [wi.id for wi in existing_items]

    # Find an existing batch or create one
    batch = db.query(Batch).filter(Batch.project_id == project_id).first()
    if not batch:
        # Create a minimal batch
        batch_id = "BATCH-E2E-SCOPE-GATE"
        batch = Batch(
            project_id=project_id,
            id=batch_id,
            status="executing",
        )
        db.add(batch)
        db.flush()
    else:
        batch_id = batch.id

    # Ensure batch items exist for our work items
    for work_item_id in work_item_ids[:2]:
        existing_bi = db.query(BatchItem).filter(
            BatchItem.project_id == project_id,
            BatchItem.batch_id == batch_id,
            BatchItem.work_item_id == work_item_id,
        ).first()

        if not existing_bi:
            bi = BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=work_item_id,
                status="executing" if work_item_id == work_item_ids[0] else "pending",
            )
            db.add(bi)
            db.flush()
        else:
            bi = existing_bi

    db.flush()

    now = datetime.now(UTC)

    # Clean up any existing scope events for these items in the test window
    for work_item_id in work_item_ids[:2]:
        db.query(DaemonEvent).filter(
            DaemonEvent.project_id == project_id,
            DaemonEvent.entity_id == work_item_id,
            DaemonEvent.entity_type == "work_item",
            DaemonEvent.event_type.in_(
                ["item_held_for_scope", "item_overlap_allowed_by_policy"]
            ),
        ).delete()

    db.flush()

    # Event 1: item_held_for_scope for the first work item
    held_event = DaemonEvent(
        project_id=project_id,
        event_type="item_held_for_scope",
        entity_type="work_item",
        entity_id=work_item_ids[0],
        message=f"Held by scope overlap",
        event_metadata={
            "blocking_item_id": work_item_ids[1],
            "conflicting_globs": ["orch/daemon/batch_manager.py", "orch/daemon/scope_overlap.py"],
        },
        created_at=now,
    )
    db.add(held_event)

    # Event 2: item_overlap_allowed_by_policy for the second work item
    allowed_event = DaemonEvent(
        project_id=project_id,
        event_type="item_overlap_allowed_by_policy",
        entity_type="work_item",
        entity_id=work_item_ids[1],
        message="Released by allow pattern",
        event_metadata={
            "candidate_item_id": work_item_ids[1],
            "in_flight_item_ids": [work_item_ids[0]],
            "dropped_block_globs": ["tests/**", "test/**"],
            "matched_allow_patterns": ["tests/**", "test/**", "**/*conftest*", "**/*.test.*", "**/*.spec.*"],
        },
        created_at=now,
    )
    db.add(allowed_event)

    db.commit()
    print(f"[fixture] CR-00058 scope-overlap events seeded: held={work_item_ids[0]}, allowed={work_item_ids[1]}")