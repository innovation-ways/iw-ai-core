"""E2E fixture: seed a historical merge_auto_resolution_failed event WITHOUT per_file_errors.

This exercises AC4 (backward compat): the frontend must not render a
"Per-file errors" section when the key is absent in event_metadata.
"""
from sqlalchemy.orm import Session
from orch.db.models import DaemonEvent

PROJECT_ID = "iw-ai-core"
SENTINEL_ID = 80689  # matches production daemon_event.id for I-00091


def seed(db: Session) -> None:
    existing = db.query(DaemonEvent).filter(
        DaemonEvent.id == SENTINEL_ID
    ).first()
    if existing:
        return
    db.add(DaemonEvent(
        id=SENTINEL_ID,
        project_id=PROJECT_ID,
        event_type="merge_auto_resolution_failed",
        entity_type="work_item",
        entity_id="I-00091",
        message="Auto-merge resolution incomplete: 0 abstained, 2 errored",
        event_metadata={
            "phase": 1,
            "abstained_files": [],
            "error_files": ["orch/db/models.py", "orch/cli/commands.py"],
            "proposed_files": [],
            "runtime_option_id": 7,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            # NO per_file_errors key — this is the pre-fix historical shape
        },
    ))
    db.commit()