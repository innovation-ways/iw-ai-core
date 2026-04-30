from sqlalchemy.orm import Session
from orch.db.models import KeepAliveConfig, KeepAliveSlot, KeepAliveRun
from datetime import datetime

def seed(db: Session) -> None:
    # Ensure config
    config = db.get(KeepAliveConfig, 1)
    if not config:
        config = KeepAliveConfig(id=1, model="claude-sonnet-4-6", window_duration_hours=5)
        db.add(config)
        db.flush()

    # Ensure one slot
    existing = db.query(KeepAliveSlot).filter_by(time_hhmm="10:02").first()
    if not existing:
        slot = KeepAliveSlot(time_hhmm="10:02", enabled=True, config_id=1)
        db.add(slot)
        db.flush()
        existing = slot

    # Ensure one run
    run_exists = db.query(KeepAliveRun).filter_by(slot_time="10:02").first()
    if not run_exists:
        db.add(KeepAliveRun(
            slot_id=existing.id,
            slot_time="10:02",
            fired_at=datetime(2026, 4, 30, 10, 2, 0),
            status="success",
        ))
    db.commit()