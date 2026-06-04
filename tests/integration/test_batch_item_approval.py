"""Integration tests for the approve_merge service (CR-00036)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)
from orch.services import approve_merge

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def work_item(db_session: Session, test_project: Project) -> WorkItem:
    item = WorkItem(
        project_id="test-proj",
        id="F-00001",
        type=WorkItemType.Feature,
        title="Test Item for approve_merge",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()
    return item


@pytest.fixture
def batch_with_auto_merge_false(db_session: Session, test_project: Project) -> Batch:
    batch = Batch(
        project_id="test-proj",
        id="B001",
        status=BatchStatus.executing,
        max_parallel=4,
        cli_tool="opencode",
        auto_publish=False,
        auto_merge=False,
    )
    db_session.add(batch)
    db_session.flush()
    return batch


@pytest.fixture
def batch_item_awaiting_approval(
    db_session: Session, work_item: WorkItem, batch_with_auto_merge_false: Batch
) -> BatchItem:
    item = BatchItem(
        project_id="test-proj",
        batch_id="B001",
        work_item_id="F-00001",
        execution_group=0,
        status=BatchItemStatus.awaiting_merge_approval,
    )
    db_session.add(item)
    db_session.flush()
    return item


# ---------------------------------------------------------------------------
# approve_merge — happy path
# ---------------------------------------------------------------------------


class TestApproveMergeHappyPath:
    def test_approves_item_and_transitions_to_completed(
        self,
        db_session: Session,
        work_item: WorkItem,
        batch_item_awaiting_approval: BatchItem,
    ):
        """approve_merge transitions awaiting_merge_approval → completed."""
        result = approve_merge(db_session, "test-proj", "F-00001")

        db_session.refresh(result)
        assert result.status == BatchItemStatus.completed

    def test_emits_merge_approved_by_operator_event(
        self,
        db_session: Session,
        work_item: WorkItem,
        batch_item_awaiting_approval: BatchItem,
    ):
        """A DaemonEvent with event_type='merge_approved_by_operator' is emitted."""
        approve_merge(db_session, "test-proj", "F-00001")

        event = (
            db_session.query(DaemonEvent)
            .filter(
                DaemonEvent.project_id == "test-proj",
                DaemonEvent.event_type == "merge_approved_by_operator",
                DaemonEvent.entity_id == "F-00001",
            )
            .first()
        )
        assert event is not None
        assert event.event_metadata["batch_id"] == "B001"
        assert event.event_metadata["work_item_id"] == "F-00001"

    def test_returns_batch_item(
        self,
        db_session: Session,
        work_item: WorkItem,
        batch_item_awaiting_approval: BatchItem,
    ):
        """approve_merge returns the BatchItem object."""
        result = approve_merge(db_session, "test-proj", "F-00001")

        assert result.batch_id == "B001"
        assert result.work_item_id == "F-00001"


# ---------------------------------------------------------------------------
# approve_merge — rejection on wrong status
# ---------------------------------------------------------------------------


class TestApproveMergeRejection:
    def test_raises_if_item_not_found(self, db_session: Session, test_project):
        """ValueError when the BatchItem does not exist."""
        with pytest.raises(ValueError, match="not found"):
            approve_merge(db_session, "test-proj", "NONEXISTENT")

    def test_raises_if_item_is_completed(
        self,
        db_session: Session,
        work_item: WorkItem,
        batch_with_auto_merge_false: Batch,
    ):
        """ValueError when the item is already completed."""
        # Item is in completed status
        bi = BatchItem(
            project_id="test-proj",
            batch_id="B001",
            work_item_id="F-00001",
            execution_group=0,
            status=BatchItemStatus.completed,
        )
        db_session.add(bi)
        db_session.flush()

        with pytest.raises(ValueError, match="completed"):
            approve_merge(db_session, "test-proj", "F-00001")

    def test_raises_if_item_is_merged(
        self,
        db_session: Session,
        work_item: WorkItem,
        batch_with_auto_merge_false: Batch,
    ):
        """ValueError when the item is already merged."""
        bi = BatchItem(
            project_id="test-proj",
            batch_id="B001",
            work_item_id="F-00001",
            execution_group=0,
            status=BatchItemStatus.merged,
        )
        db_session.add(bi)
        db_session.flush()

        with pytest.raises(ValueError, match="merged"):
            approve_merge(db_session, "test-proj", "F-00001")

    def test_error_message_includes_actual_status(
        self,
        db_session: Session,
        work_item: WorkItem,
        batch_with_auto_merge_false: Batch,
    ):
        """ValueError message names the actual status of the item."""
        bi = BatchItem(
            project_id="test-proj",
            batch_id="B001",
            work_item_id="F-00001",
            execution_group=0,
            status=BatchItemStatus.executing,
        )
        db_session.add(bi)
        db_session.flush()

        with pytest.raises(ValueError, match="executing"):
            approve_merge(db_session, "test-proj", "F-00001")
