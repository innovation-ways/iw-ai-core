"""Batch item approval service — transitions awaiting items to the merge queue."""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import BatchItem, BatchItemStatus, DaemonEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def approve_merge(db: Session, project_id: str, item_id: str) -> BatchItem:
    """Transition a BatchItem from awaiting_merge_approval to completed.

    Used by both the dashboard route POST /actions/item/{item_id}/approve-merge
    and the CLI ``iw item approve-merge``. The next daemon poll cycle will pick
    the item up via the existing merge queue path.

    Raises
    ------
    ValueError
        If the item is not currently in awaiting_merge_approval.

    """
    # SELECT ... FOR UPDATE to match the pattern used by merge_queue._merge_item
    bi = (
        db.query(BatchItem)
        .filter(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
            BatchItem.status == BatchItemStatus.awaiting_merge_approval,
        )
        .with_for_update()
        .first()
    )

    if bi is None:
        # Fallback: check if the item exists at all and report its actual status
        actual_bi = (
            db.query(BatchItem)
            .filter(
                BatchItem.project_id == project_id,
                BatchItem.work_item_id == item_id,
            )
            .first()
        )
        if actual_bi is None:
            raise ValueError(f"BatchItem for work item {item_id} in project {project_id} not found")
        raise ValueError(
            f"BatchItem {item_id} is in {actual_bi.status.value} but must be "
            "awaiting_merge_approval to approve the merge"
        )

    bi.status = BatchItemStatus.completed

    event = DaemonEvent(
        project_id=project_id,
        event_type="merge_approved_by_operator",
        entity_id=item_id,
        entity_type="work_item",
        message=f"Operator approved merge for {item_id}",
        event_metadata={"batch_id": bi.batch_id, "work_item_id": item_id},
    )
    db.add(event)

    db.commit()
    db.refresh(bi)
    return bi
