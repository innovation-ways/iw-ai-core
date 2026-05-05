"""Seed a short DaemonEvent for I-00067 V4 verification.

Short messages (≤100 chars) must render verbatim with no "..." suffix
and no click affordance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from orch.db.models import DaemonEvent


def seed(db: Session) -> None:
    # Check if we already have a short event
    existing = db.execute(
        db.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == "iw-ai-core",
            DaemonEvent.entity_id == "I-00067-short",
        )
        .statement
    ).first()
    if existing is not None:
        return

    short_message = "Step S02 (code-review-impl) passed review."

    db.add(
        DaemonEvent(
            project_id="iw-ai-core",
            event_type="step_completed",
            entity_id="I-00067-short",
            entity_type="work_item",
            message=short_message,
        )
    )
    db.flush()
