"""E2E fixture: seed a historical merge_auto_resolved event for regression checks."""
from sqlalchemy.orm import Session
from orch.db.models import DaemonEvent

PROJECT_ID = "iw-ai-core"
SENTINEL_ID = 80528  # matches production daemon_event.id for I-00097


def seed(db: Session) -> None:
    existing = db.query(DaemonEvent).filter(
        DaemonEvent.id == SENTINEL_ID
    ).first()
    if existing:
        return
    db.add(DaemonEvent(
        id=SENTINEL_ID,
        project_id=PROJECT_ID,
        event_type="merge_auto_resolved",
        entity_type="work_item",
        entity_id="I-00097",
        message="Auto-merge resolution complete: 3 abstained, 0 errored",
        event_metadata={
            "phase": 1,
            "abstained_files": ["orch/rag/__init__.py", "dashboard/routers/docs.py", "orch/doc_service.py"],
            "error_files": [],
            "proposed_files": [],
            "runtime_option_id": 7,
            "total_input_tokens": 1234,
            "total_output_tokens": 5678,
        },
    ))
    db.commit()