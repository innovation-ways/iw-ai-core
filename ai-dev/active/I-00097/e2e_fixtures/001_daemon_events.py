"""I-00097 S12 browser verification fixtures — DaemonEvent rows for auto-merge entity_id checks.

Seeds three event types needed by the S12 browser verification:
- V2: step_launched with entity_id = "CR-00057" (work-item ID → must linkify)
- V3: auto_merge_config_updated with entity_id = "iw-ai-core" (project_id → must NOT linkify)
- V4: auto_merge_health_probe with entity_id = NULL (→ must render as —)
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from orch.db.models import DaemonEvent

PROJECT_ID = "iw-ai-core"


def seed(db) -> None:
    now = datetime.now(UTC)

    # V2: step_launched with work-item ID entity_id → should linkify to /item/CR-00057
    v2 = db.scalar(
        select(DaemonEvent).where(
            DaemonEvent.project_id == PROJECT_ID,
            DaemonEvent.event_type == "step_launched",
            DaemonEvent.entity_id == "CR-00057",
        )
    )
    if v2 is None:
        db.add(
            DaemonEvent(
                project_id=PROJECT_ID,
                event_type="step_launched",
                entity_id="CR-00057",
                message="step launched for CR-00057",
                created_at=now,
            )
        )

    # V3: auto_merge_config_updated with project_id as entity_id → must stay plain text
    v3 = db.scalar(
        select(DaemonEvent).where(
            DaemonEvent.project_id == PROJECT_ID,
            DaemonEvent.event_type == "auto_merge_config_updated",
            DaemonEvent.entity_id == "iw-ai-core",
        )
    )
    if v3 is None:
        db.add(
            DaemonEvent(
                project_id=PROJECT_ID,
                event_type="auto_merge_config_updated",
                entity_id="iw-ai-core",
                message="config updated for iw-ai-core",
                created_at=now,
            )
        )

    # V4: auto_merge_health_probe with NULL entity_id → must render as em-dash
    v4 = db.scalar(
        select(DaemonEvent).where(
            DaemonEvent.project_id == PROJECT_ID,
            DaemonEvent.event_type == "auto_merge_health_probe",
            DaemonEvent.entity_id.is_(None),
        )
    )
    if v4 is None:
        db.add(
            DaemonEvent(
                project_id=PROJECT_ID,
                event_type="auto_merge_health_probe",
                entity_id=None,
                message="health probe ok",
                created_at=now,
            )
        )