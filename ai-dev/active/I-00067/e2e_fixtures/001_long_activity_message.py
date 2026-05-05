"""Seed a long DaemonEvent for I-00067 browser verification.

Triggers the truncation UI path (>100 chars) so qv-browser can verify
V1..V4 against the isolated E2E stack.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from orch.db.models import DaemonEvent


def seed(db: Session) -> None:
    # Check if we already have one for this item
    existing = db.execute(
        db.query(DaemonEvent).filter(
            DaemonEvent.project_id == "iw-ai-core",
            DaemonEvent.entity_id == "I-00067",
        ).statement
    ).first()
    if existing is not None:
        return  # already seeded

    long_message = (
        "Step S01 (frontend-impl) failed: template truncation logic produced "
        "unexpected output. Expected 100 chars + '...' suffix but received "
        "truncated content with incorrect ellipsis placement. Traceback:\n"
        "  File '/app/orch/daemon/step_monitor.py', line 142, in run_step\n"
        "    raise RuntimeError('Template render failed for activity card')\n"
        "RuntimeError: Template render failed for activity card"
    )

    db.add(
        DaemonEvent(
            project_id="iw-ai-core",
            event_type="step_failed",
            entity_id="I-00067",
            entity_type="work_item",
            message=long_message,
        )
    )
    db.flush()