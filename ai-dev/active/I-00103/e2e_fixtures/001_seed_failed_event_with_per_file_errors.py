from sqlalchemy.orm import Session
from orch.db.models import DaemonEvent

PROJECT_ID = "iw-ai-core"
SENTINEL_ITEM_ID = "I-00103-fixture"

def seed(db: Session) -> None:
    existing = db.execute(
        # idempotent: only insert if not already present for this sentinel
        db.query(DaemonEvent).filter(
            DaemonEvent.entity_id == SENTINEL_ITEM_ID
        )
    ).scalar_one_or_none()
    if existing:
        return
    db.add(DaemonEvent(
        project_id=PROJECT_ID,
        event_type="merge_auto_resolution_failed",
        entity_type="work_item",
        entity_id=SENTINEL_ITEM_ID,
        message="Auto-merge resolution incomplete: 0 abstained, 1 errored",
        event_metadata={
            "phase": 1,
            "abstained_files": [],
            "error_files": ["tests/dashboard/test_auto_merge_routes.py"],
            "proposed_files": [],
            "runtime_option_id": 7,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "per_file_errors": [
                {
                    "file_path": "tests/dashboard/test_auto_merge_routes.py",
                    "error": "LLM call timed out after 600s: subprocess.TimeoutExpired(...)",
                    "cli_tool": "pi",
                    "model": "minimax/MiniMax-M2.7",
                },
            ],
        },
    ))
    db.commit()