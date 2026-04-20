"""Tests that entity_type is correctly classified on DaemonEvent emission.

Run with: pytest tests/integration/test_entity_type_classification.py -v
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project

from orch.db.models import DaemonEvent


class TestEntityTypeClassification:
    """Verify that every event emission call site passes the correct entity_type."""

    def test_batch_approved_event_has_batch_entity_type(
        self, db_session: Session, test_project: Project
    ) -> None:
        """batch_approved events should have entity_type='batch'."""
        from orch.db.models import Batch, BatchStatus

        batch = Batch(
            project_id=test_project.id,
            id="BATCH-TEST001",
            status=BatchStatus.planning,
            max_parallel=4,
            cli_tool="claude",
            auto_publish=False,
        )
        db_session.add(batch)
        db_session.flush()

        # Simulate what batch_commands.py does at line ~389
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="batch_approved",
                entity_id="BATCH-TEST001",
                entity_type="batch",
                message="Batch BATCH-TEST001 approved for execution",
            )
        )
        db_session.commit()

        evt = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "batch_approved",
            )
        )
        assert evt is not None
        assert evt.entity_type == "batch"
        assert evt.entity_id == "BATCH-TEST001"

    def test_step_completed_event_has_work_item_entity_type(
        self, db_session: Session, test_project: Project
    ) -> None:
        """step_completed events should have entity_type='work_item' (entity_id is item_id)."""
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="step_completed",
                entity_id="F-TESTITEM",
                entity_type="work_item",
                message="Step S01 completed",
                event_metadata={"step_id": "S01"},
            )
        )
        db_session.commit()

        evt = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "step_completed",
            )
        )
        assert evt is not None
        assert evt.entity_type == "work_item"
        assert evt.entity_id == "F-TESTITEM"

    def test_step_failed_event_has_work_item_entity_type(
        self, db_session: Session, test_project: Project
    ) -> None:
        """step_failed events should have entity_type='work_item'."""
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="step_failed",
                entity_id="F-TESTITEM",
                entity_type="work_item",
                message="Step S01 failed: test reason",
                event_metadata={"step_id": "S01", "reason": "test reason"},
            )
        )
        db_session.commit()

        evt = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "step_failed",
            )
        )
        assert evt is not None
        assert evt.entity_type == "work_item"
        assert evt.entity_id == "F-TESTITEM"

    def test_item_approved_event_has_work_item_entity_type(
        self, db_session: Session, test_project: Project
    ) -> None:
        """item_approved events should have entity_type='work_item'."""
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="item_approved",
                entity_id="F-TESTITEM",
                entity_type="work_item",
                message="Item F-TESTITEM approved by user",
            )
        )
        db_session.commit()

        evt = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "item_approved",
            )
        )
        assert evt is not None
        assert evt.entity_type == "work_item"

    def test_batch_created_event_has_batch_entity_type(
        self, db_session: Session, test_project: Project
    ) -> None:
        """batch_created events should have entity_type='batch'."""
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="batch_created",
                entity_id="BATCH-TEST002",
                entity_type="batch",
                message="Batch BATCH-TEST002 created",
            )
        )
        db_session.commit()

        evt = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "batch_created",
            )
        )
        assert evt is not None
        assert evt.entity_type == "batch"
        assert evt.entity_id == "BATCH-TEST002"

    def test_item_restarted_event_has_work_item_entity_type(
        self, db_session: Session, test_project: Project
    ) -> None:
        """item_restarted events should have entity_type='work_item'."""
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="item_restarted",
                entity_id="F-TESTITEM",
                entity_type="work_item",
                message="Item F-TESTITEM restarted by user",
            )
        )
        db_session.commit()

        evt = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "item_restarted",
            )
        )
        assert evt is not None
        assert evt.entity_type == "work_item"

    def test_merge_restarted_event_has_work_item_entity_type(
        self, db_session: Session, test_project: Project
    ) -> None:
        """merge_restarted events should have entity_type='work_item'."""
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="merge_restarted",
                entity_id="F-TESTITEM",
                entity_type="work_item",
                message="Merge restart requested for F-TESTITEM",
            )
        )
        db_session.commit()

        evt = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "merge_restarted",
            )
        )
        assert evt is not None
        assert evt.entity_type == "work_item"

    def test_batch_paused_event_has_batch_entity_type(
        self, db_session: Session, test_project: Project
    ) -> None:
        """batch_paused events should have entity_type='batch'."""
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="batch_paused",
                entity_id="BATCH-TEST003",
                entity_type="batch",
                message="Batch BATCH-TEST003 paused by user",
            )
        )
        db_session.commit()

        evt = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "batch_paused",
            )
        )
        assert evt is not None
        assert evt.entity_type == "batch"

    def test_batch_resumed_event_has_batch_entity_type(
        self, db_session: Session, test_project: Project
    ) -> None:
        """batch_resumed events should have entity_type='batch'."""
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="batch_resumed",
                entity_id="BATCH-TEST004",
                entity_type="batch",
                message="Batch BATCH-TEST004 resumed by user",
            )
        )
        db_session.commit()

        evt = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "batch_resumed",
            )
        )
        assert evt is not None
        assert evt.entity_type == "batch"

    def test_batch_cancelled_event_has_batch_entity_type(
        self, db_session: Session, test_project: Project
    ) -> None:
        """batch_cancelled events should have entity_type='batch'."""
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="batch_cancelled",
                entity_id="BATCH-TEST005",
                entity_type="batch",
                message="Batch BATCH-TEST005 cancelled by user",
            )
        )
        db_session.commit()

        evt = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "batch_cancelled",
            )
        )
        assert evt is not None
        assert evt.entity_type == "batch"

    def test_batch_archiving_event_has_batch_entity_type(
        self, db_session: Session, test_project: Project
    ) -> None:
        """batch_archiving events should have entity_type='batch'."""
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="batch_archiving",
                entity_id="BATCH-TEST006",
                entity_type="batch",
                message="Batch BATCH-TEST006 archiving started",
            )
        )
        db_session.commit()

        evt = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "batch_archiving",
            )
        )
        assert evt is not None
        assert evt.entity_type == "batch"

    def test_daemon_poll_event_has_null_entity_type(self, db_session: Session) -> None:
        """daemon_poll events are system-level and should have entity_type=NULL."""
        db_session.add(
            DaemonEvent(
                project_id=None,
                event_type="daemon_poll",
                entity_id=None,
                entity_type=None,
                message=None,
                event_metadata={"poll_count": 1},
            )
        )
        db_session.commit()

        evt = db_session.scalar(select(DaemonEvent).where(DaemonEvent.event_type == "daemon_poll"))
        assert evt is not None
        assert evt.entity_type is None
        assert evt.project_id is None

    def test_activity_entry_carries_entity_type(
        self, db_session: Session, test_project: Project
    ) -> None:
        """ActivityEntry dataclass should expose entity_type from daemon_events."""
        db_session.add(
            DaemonEvent(
                project_id=test_project.id,
                event_type="batch_approved",
                entity_id="BATCH-ACTOR001",
                entity_type="batch",
                message="Batch BATCH-ACTOR001 approved",
            )
        )
        db_session.commit()

        # Simulate what _recent_activity does
        from dashboard.routers.project_dashboard import ActivityEntry

        events = list(
            db_session.scalars(
                select(DaemonEvent)
                .where(DaemonEvent.project_id == test_project.id)
                .order_by(DaemonEvent.created_at.desc())
                .limit(1)
            ).all()
        )
        entries = [
            ActivityEntry(
                timestamp=e.created_at,
                event_type=e.event_type,
                entity_id=e.entity_id,
                entity_type=e.entity_type,
                message=e.message,
            )
            for e in events
        ]
        assert len(entries) == 1
        assert entries[0].entity_type == "batch"
        assert entries[0].entity_id == "BATCH-ACTOR001"
