"""Insert a merge_auto_resolved DaemonEvent with verdict for V3 browser verification."""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import DaemonEvent, MergeAutoVerdict

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def seed(db: Session) -> None:
    # Check if a merge_auto_resolved event already exists
    existing = db.query(DaemonEvent).filter(
        DaemonEvent.event_type == "merge_auto_resolved"
    ).first()
    if existing:
        return  # already seeded

    project_id = "iw-ai-core"

    event = DaemonEvent(
        project_id=project_id,
        event_type="merge_auto_resolved",
        entity_id="I-00001",
        entity_type="work_item",
        message="auto-merge completed for I-00001",
        event_metadata={
            "llm_calls": [
                {
                    "file_path": "README.md",
                    "proposed_content": "# Hello\n\nWorld",
                }
            ],
            "refuse_reason": None,
        },
    )
    db.add(event)
    db.flush()  # get the event.id before adding verdict

    verdict = MergeAutoVerdict(
        project_id=project_id,
        daemon_event_id=event.id,
        verdict="correct",
        verdict_notes="looked fine",
        verdicted_by="operator",
    )
    db.add(verdict)
    db.commit()