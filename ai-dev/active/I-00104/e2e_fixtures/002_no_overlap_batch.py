"""E2E fixture: batch with non-overlapping items for I-00104 V4 regression check.

Creates:
  - 2 approved WorkItems with DISJOINT impacted_paths
  - 1 Batch with max_parallel=5
  - 2 BatchItems

This lets V4 verify that batches WITHOUT overlaps still correctly show:
- "None — all items are independent" in Warnings
- Max Parallel matching the header
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def seed(db: Session) -> None:
    project_id = "iw-ai-core"

    existing = db.execute(
        __import__("sqlalchemy").select(Batch).where(Batch.id == "BATCH-I-00104-NO-OVERLAP")
    ).scalar_one_or_none()
    if existing is not None:
        return  # idempotent

    # Item A: foo scope
    item_a = WorkItem(
        project_id=project_id,
        id="I-00104-NO-OV-A",
        type=WorkItemType.Issue,
        title="Foo scope item",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=["foo/a.py", "foo/b.py"],
    )

    # Item B: bar scope — completely disjoint from A
    item_b = WorkItem(
        project_id=project_id,
        id="I-00104-NO-OV-B",
        type=WorkItemType.Issue,
        title="Bar scope item",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=["bar/c.py", "bar/d.py"],
    )

    db.add(item_a)
    db.add(item_b)
    db.flush()

    batch = Batch(
        project_id=project_id,
        id="BATCH-I-00104-NO-OVERLAP",
        status=BatchStatus.planning,
        max_parallel=5,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=True,
    )
    db.add(batch)
    db.flush()

    bi_a = BatchItem(
        project_id=project_id,
        batch_id="BATCH-I-00104-NO-OVERLAP",
        work_item_id="I-00104-NO-OV-A",
        execution_group=0,
        status=BatchItemStatus.pending,
    )
    bi_b = BatchItem(
        project_id=project_id,
        batch_id="BATCH-I-00104-NO-OVERLAP",
        work_item_id="I-00104-NO-OV-B",
        execution_group=0,
        status=BatchItemStatus.pending,
    )
    db.add(bi_a)
    db.add(bi_b)
    db.commit()