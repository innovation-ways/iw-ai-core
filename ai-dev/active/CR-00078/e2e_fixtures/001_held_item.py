"""CR-00078 browser-verification seed: held item with fresh scope-hold events.

The _get_scope_statuses uses a 5-minute (300s) window from now.
Daemon events must be within this window to show as "Held".
We always update timestamps to be within the last 60s so the browser
always sees a held item regardless of when the fixture last ran.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
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

    # Use timestamps within the last 60 seconds — well within the 300s window
    recent = now - timedelta(seconds=30)  # 30s ago

    # ── 1. Blocker WorkItem (already executing) ─────────────────────────────
    blocker_id = "F-00077"
    blocker = db.get(WorkItem, (PROJECT_ID, blocker_id))
    if blocker is None:
        blocker = WorkItem(
            project_id=PROJECT_ID,
            id=blocker_id,
            type=WorkItemType.Feature,
            title="CR-00077 scope enforcement gate",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.work,
            design_doc_content="Feature blocker for CR-00078 overlap tests.",
            summary="CR-00077 feature",
            created_at=now,
        )
        db.add(blocker)

    # ── 2. Batch (executing) ─────────────────────────────────────────────────
    batch_id = "BATCH-CR00078"
    batch = db.get(Batch, (PROJECT_ID, batch_id))
    if batch is None:
        batch = Batch(
            project_id=PROJECT_ID,
            id=batch_id,
            status=BatchStatus.executing,
            created_at=now,
        )
        db.add(batch)

    db.flush()  # ensure FK ordering

    # ── 3. Blocker BatchItem (executing) ────────────────────────────────────
    blocker_ci = (
        db.query(BatchItem)
        .filter_by(project_id=PROJECT_ID, batch_id=batch_id, work_item_id=blocker_id)
        .first()
    )
    if blocker_ci is None:
        blocker_ci = BatchItem(
            project_id=PROJECT_ID,
            batch_id=batch_id,
            work_item_id=blocker_id,
            status=BatchItemStatus.executing,
            execution_group=1,
        )
        db.add(blocker_ci)

    # ── 4. Held WorkItem ─────────────────────────────────────────────────────
    held_id = "CR-00078"
    held = db.get(WorkItem, (PROJECT_ID, held_id))
    if held is None:
        held = WorkItem(
            project_id=PROJECT_ID,
            id=held_id,
            type=WorkItemType.ChangeRequest,
            title="Per-batch ignore overlap & force-start (CR-00078)",
            status=WorkItemStatus.approved,
            phase=WorkItemPhase.active,
            design_doc_content="CR-00078 overlap ignore feature.",
            summary="CR-00078 overlap ignore",
            created_at=now,
        )
        db.add(held)

    db.flush()  # ensure WorkItem exists before BatchItem FK

    # ── 5. Held BatchItem ───────────────────────────────────────────────────
    held_ci = (
        db.query(BatchItem)
        .filter_by(project_id=PROJECT_ID, batch_id=batch_id, work_item_id=held_id)
        .first()
    )
    if held_ci is None:
        held_ci = BatchItem(
            project_id=PROJECT_ID,
            batch_id=batch_id,
            work_item_id=held_id,
            status=BatchItemStatus.pending,
            execution_group=2,
        )
        db.add(held_ci)

    # ── 6. Two DaemonEvent rows: item_held_for_scope ─────────────────────────
    ev1_meta = {
        "conflicting_globs": [
            "orch/**/*.py",
            "dashboard/**/*.py",
            "tests/**/*.py",
            "docs/**/*.md",
        ],
        "blocker_item_id": blocker_id,
        "blocker_title": "CR-00077 scope enforcement gate",
        "execution_groups": [1, 2],
    }
    ev2_meta = {
        "conflicting_globs": [
            "templates/**/*.html",
            "static/**/*.css",
            "scripts/**/*.py",
        ],
        "blocker_item_id": blocker_id,
        "blocker_title": "CR-00077 scope enforcement gate",
        "execution_groups": [1, 2],
    }

    # Always touch (update) existing events so timestamps stay fresh.
    # Delete and recreate to keep IDs clean while ensuring recent timestamps.
    db.query(DaemonEvent).filter_by(
        project_id=PROJECT_ID,
        entity_id=held_id,
        event_type="item_held_for_scope",
    ).delete()
    db.flush()

    ev1_time = recent - timedelta(seconds=30)  # 60s ago
    ev2_time = recent  # 30s ago

    ev1 = DaemonEvent(
        project_id=PROJECT_ID,
        entity_id=held_id,
        entity_type="work_item",
        event_type="item_held_for_scope",
        message=f"Item {held_id} held: 4 overlapping files with {blocker_id}",
        event_metadata=ev1_meta,
        created_at=ev1_time,
    )
    db.add(ev1)
    db.flush()

    ev2 = DaemonEvent(
        project_id=PROJECT_ID,
        entity_id=held_id,
        entity_type="work_item",
        event_type="item_held_for_scope",
        message=f"Item {held_id} re-held: 3 more overlapping files with {blocker_id}",
        event_metadata=ev2_meta,
        created_at=ev2_time,
    )
    db.add(ev2)