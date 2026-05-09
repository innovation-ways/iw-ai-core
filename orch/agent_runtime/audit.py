"""Audit helpers for agent runtime overrides — DaemonEvent emission."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def emit_runtime_override_changed(
    session: Session,
    *,
    project_id: str,
    item_id: str,
    scope: str,  # "item" | "step" | "bulk"
    step_ids: list[str] | None,  # populated for step + bulk; None for item-only
    old_option_id: int | None,
    new_option_id: int | None,
    actor: str,
) -> None:
    """Emit exactly one DaemonEvent row for a runtime override change.

    Regardless of how many steps are affected (AC6), this helper emits
    exactly one row with event_type='runtime_override_changed'.

    Args:
        session: Active SQLAlchemy session.
        project_id: The project the item belongs to.
        item_id: The work item id (entity_id on the event).
        scope: One of "item", "step", "bulk".
        step_ids: List of affected step_ids. For "item" scope pass None.
                  For "bulk" pass the full list of affected step_ids (may be empty).
        old_option_id: The previous option id (or None if there was none).
        new_option_id: The new option id (or None to clear).
        actor: Who made the change (email or username).
    """
    from datetime import UTC, datetime

    from orch.db.models import DaemonEvent

    event = DaemonEvent(
        project_id=project_id,
        event_type="runtime_override_changed",
        entity_id=item_id,
        entity_type="work_item",
        message=f"Runtime override changed ({scope})",
        event_metadata={
            "item_id": item_id,
            "scope": scope,
            "step_ids": step_ids if step_ids is not None else None,
            "old_option_id": old_option_id,
            "new_option_id": new_option_id,
            "actor": actor,
        },
        created_at=datetime.now(UTC),
    )
    session.add(event)
    session.commit()
