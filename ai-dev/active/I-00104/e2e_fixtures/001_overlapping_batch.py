"""E2E fixture: batch with overlapping items for I-00104 browser verification.

Creates:
  - 2 approved WorkItems with overlapping impacted_paths
    (glob `dashboard/**` vs concrete `dashboard/static/foo.js`)
  - 1 Batch with max_parallel=5
  - 2 BatchItems

This lets V1/V2 verify the fixed overlap detection (Dependency Analysis shows
Overlap With populated) and V3 verify max_parallel consistency (header chip and
plan markdown both show 5).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def seed(db: Session) -> None:
    project_id = "iw-ai-core"

    # Check if already seeded
    existing = db.execute(
        __import__("sqlalchemy").select(Batch).where(Batch.id == "BATCH-I-00104-FIX")
    ).scalar_one_or_none()
    if existing is not None:
        return  # idempotent

    # Item A: broad glob
    item_a = WorkItem(
        project_id=project_id,
        id="I-00104-OVERLAP-A",
        type=WorkItemType.ChangeRequest,
        title="Dashboard UI feature (broad scope)",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=["dashboard/**"],
    )

    # Item B: concrete file under A's glob
    item_b = WorkItem(
        project_id=project_id,
        id="I-00104-OVERLAP-B",
        type=WorkItemType.Issue,
        title="Static asset fix (specific file)",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=["dashboard/static/foo.js"],
    )

    db.add(item_a)
    db.add(item_b)
    db.flush()  # ensure items are persisted before batch references them

    # Batch with max_parallel=5
    batch = Batch(
        project_id=project_id,
        id="BATCH-I-00104-FIX",
        status=BatchStatus.planning,
        max_parallel=5,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=True,
    )
    db.add(batch)
    db.flush()

    # Batch items — execution_group set based on overlap detection;
    # initially 0 for both; the fixed batch_planner will set
    # group=1 for B (depends on A via overlap) when plan is (re)generated.
    bi_a = BatchItem(
        project_id=project_id,
        batch_id="BATCH-I-00104-FIX",
        work_item_id="I-00104-OVERLAP-A",
        execution_group=0,
        status=BatchItemStatus.pending,
    )
    bi_b = BatchItem(
        project_id=project_id,
        batch_id="BATCH-I-00104-FIX",
        work_item_id="I-00104-OVERLAP-B",
        execution_group=0,
        status=BatchItemStatus.pending,
    )
    db.add(bi_a)
    db.add(bi_b)
    db.commit()