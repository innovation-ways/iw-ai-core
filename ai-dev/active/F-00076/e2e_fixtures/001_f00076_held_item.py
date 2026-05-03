"""E2E fixture: seed F-00076 S21 browser verification data.

Creates:
- Two Feature WorkItems with impacted_paths (one 'executing', one 'pending' with hold)
- A 'item_held_for_scope' DaemonEvent for the pending item
- A Batch + BatchItem for each work item
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


PROJECT_ID = "iw-ai-core"


def seed(db: Session) -> None:
    now = datetime.now(UTC)

    # Ensure project exists
    project = db.get(Project, PROJECT_ID)
    if project is None:
        project = Project(
            id=PROJECT_ID,
            display_name="IW AI Core (E2E)",
            repo_root="/app",
            config={},
            enabled=True,
        )
        db.add(project)

    # --- V1/V2: Feature with 'declared' scope_extraction ---
    wi_declared_id = "F-00076-S21-DECLARED"
    wi_declared = db.get(WorkItem, (PROJECT_ID, wi_declared_id))
    if wi_declared is None:
        wi_declared = WorkItem(
            project_id=PROJECT_ID,
            id=wi_declared_id,
            type=WorkItemType.Feature,
            title="Cross-batch file-conflict gate (E2E declared)",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={
                "scope_extraction": {
                    "source": "declared",
                }
            },
            depends_on=[],
            blocks=[],
            impacted_paths=["orch/daemon/**", "orch/batch_planner.py", "dashboard/**/*.py"],
            design_doc_content=(
                "## Impacted Paths\n- orch/daemon/**\n"
                "- orch/batch_planner.py\n- dashboard/**/*.py\n"
            ),
            created_at=now,
        )
        db.add(wi_declared)

    # --- V1/V2: Feature with 'regex_fallback' scope_extraction ---
    wi_auto_id = "F-00076-S21-AUTO"
    wi_auto = db.get(WorkItem, (PROJECT_ID, wi_auto_id))
    if wi_auto is None:
        wi_auto = WorkItem(
            project_id=PROJECT_ID,
            id=wi_auto_id,
            type=WorkItemType.Feature,
            title="Cross-batch file-conflict gate (E2E auto)",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={
                "scope_extraction": {
                    "source": "regex_fallback",
                    "warned_at": now.isoformat(),
                }
            },
            depends_on=[],
            blocks=[],
            impacted_paths=["orch/cli/*.py", "executor/*.sh"],
            design_doc_content=(
                "This feature modifies the CLI module and executor scripts. "
                "Impacted paths are auto-extracted via regex fallback."
            ),
            created_at=now,
        )
        db.add(wi_auto)

    # --- V3: Two batches with overlapping items (executing + held) ---
    # Batch A: item in 'executing' with overlapping paths
    batch_a_id = "BATCH-E2E-A"
    batch_a = db.get(Batch, (PROJECT_ID, batch_a_id))
    if batch_a is None:
        batch_a = Batch(
            project_id=PROJECT_ID,
            id=batch_a_id,
            status=BatchStatus.executing,
            created_at=now,
        )
        db.add(batch_a)

    wi_blocker_id = "F-00076-S21-BLOCKER"
    wi_blocker = db.get(WorkItem, (PROJECT_ID, wi_blocker_id))
    if wi_blocker is None:
        wi_blocker = WorkItem(
            project_id=PROJECT_ID,
            id=wi_blocker_id,
            type=WorkItemType.Feature,
            title="Blocker item for E2E held test",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={
                "scope_extraction": {
                    "source": "declared",
                }
            },
            depends_on=[],
            blocks=[],
            impacted_paths=["orch/daemon/**"],
            created_at=now,
        )
        db.add(wi_blocker)

    bi_blocker = db.execute(
        select(BatchItem).where(
            BatchItem.project_id == PROJECT_ID,
            BatchItem.batch_id == batch_a_id,
            BatchItem.work_item_id == wi_blocker_id,
        )
    ).scalar_one_or_none()
    if bi_blocker is None:
        bi_blocker = BatchItem(
            project_id=PROJECT_ID,
            batch_id=batch_a_id,
            work_item_id=wi_blocker_id,
            status=BatchItemStatus.executing,
            execution_group=0,
            started_at=now,
        )
        db.add(bi_blocker)

    # Batch B: item in 'pending' with overlapping paths and hold event
    batch_b_id = "BATCH-E2E-B"
    batch_b = db.get(Batch, (PROJECT_ID, batch_b_id))
    if batch_b is None:
        batch_b = Batch(
            project_id=PROJECT_ID,
            id=batch_b_id,
            status=BatchStatus.executing,
            created_at=now,
        )
        db.add(batch_b)

    wi_held_id = "F-00076-S21-HELD"
    wi_held = db.get(WorkItem, (PROJECT_ID, wi_held_id))
    if wi_held is None:
        wi_held = WorkItem(
            project_id=PROJECT_ID,
            id=wi_held_id,
            type=WorkItemType.Feature,
            title="Held item for E2E overlap test",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={
                "scope_extraction": {
                    "source": "declared",
                }
            },
            depends_on=[],
            blocks=[],
            impacted_paths=["orch/daemon/batch_manager.py"],  # overlaps with blocker
            created_at=now,
        )
        db.add(wi_held)

    bi_held = db.execute(
        select(BatchItem).where(
            BatchItem.project_id == PROJECT_ID,
            BatchItem.batch_id == batch_b_id,
            BatchItem.work_item_id == wi_held_id,
        )
    ).scalar_one_or_none()
    if bi_held is None:
        bi_held = BatchItem(
            project_id=PROJECT_ID,
            batch_id=batch_b_id,
            work_item_id=wi_held_id,
            status=BatchItemStatus.pending,
            execution_group=0,
        )
        db.add(bi_held)

    # DaemonEvent: item_held_for_scope for wi_held
    ev = db.execute(
        select(DaemonEvent).where(
            DaemonEvent.project_id == PROJECT_ID,
            DaemonEvent.event_type == "item_held_for_scope",
            DaemonEvent.entity_id == wi_held_id,
        )
    ).scalar_one_or_none()
    if ev is None:
        ev = DaemonEvent(
            project_id=PROJECT_ID,
            event_type="item_held_for_scope",
            entity_id=wi_held_id,
            entity_type="work_item",
            message=f"Held: overlaps with {wi_blocker_id} on `orch/daemon/batch_manager.py`",
            event_metadata={
                "candidate": wi_held_id,
                "blocking": wi_blocker_id,
                "conflicting_globs": ["orch/daemon/batch_manager.py"],
            },
            created_at=now,
        )
        db.add(ev)

    db.flush()
