"""AC6 unit: abandon-merge endpoint — flips recoverable status to failed and emits event.

AC6:
1. abandon-merge flips merge_failed/migration_invalid/migration_rebase_failed → failed
2. merge_abandoned daemon_event is emitted
3. Original notes preserved + " [operator abandoned via abandon-merge]" appended
4. reject other statuses with 422
5. merge_abandoned event is in SSE _TOAST_EVENTS and _TOAST_SEVERITY (AC7 unit-level)

Uses the FastAPI TestClient pattern from existing dashboard tests.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers.sse import _TOAST_EVENTS, _TOAST_SEVERITY
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

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# TestClient fixture (copied from existing dashboard test patterns)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a TestClient that overrides get_db to use the test db_session."""
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            """Yield the test db_session for FastAPI dependency injection."""
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_work_item(db: Session, project_id: str, item_id: str) -> WorkItem:
    """Create and flush a minimal WorkItem in approved status for testing.

    Args:
        db: SQLAlchemy session to use.
        project_id: ID of the owning project.
        item_id: Unique work item ID.

    Returns:
        The flushed WorkItem instance.
    """
    item = WorkItem(
        id=item_id,
        project_id=project_id,
        type=WorkItemType.Feature,
        title=f"Test {item_id}",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(item)
    db.flush()
    return item


def make_batch(db: Session, project_id: str, batch_id: str) -> Batch:
    """Create and flush a minimal Batch in executing status for testing.

    Args:
        db: SQLAlchemy session to use.
        project_id: ID of the owning project.
        batch_id: Unique batch ID.

    Returns:
        The flushed Batch instance.
    """
    batch = Batch(
        id=batch_id,
        project_id=project_id,
        status=BatchStatus.executing,
        max_parallel=4,
        cli_tool="opencode",
        auto_publish=False,
    )
    db.add(batch)
    db.flush()
    return batch


def make_batch_item(
    db: Session,
    project_id: str,
    batch_id: str,
    work_item_id: str,
    status: BatchItemStatus,
    notes: str | None = None,
) -> BatchItem:
    """Create and flush a BatchItem with the given status for testing.

    Args:
        db: SQLAlchemy session to use.
        project_id: ID of the owning project.
        batch_id: ID of the parent batch.
        work_item_id: ID of the associated work item.
        status: Initial BatchItemStatus to set.
        notes: Optional notes string.

    Returns:
        The flushed BatchItem instance.
    """
    item = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=work_item_id,
        execution_group=0,
        status=status,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        worktree_info={"path": f"/wt/{work_item_id}"},
        notes=notes,
    )
    db.add(item)
    db.flush()
    return item


# ---------------------------------------------------------------------------
# AC6: abandon-merge flips to failed and emits event
# ---------------------------------------------------------------------------


class TestAbandonMerge:
    """AC6: abandon-merge endpoint — recoverable → failed with cascade."""

    @pytest.mark.parametrize(
        "recoverable_status",
        [
            BatchItemStatus.merge_failed,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rebase_failed,
        ],
    )
    def test_abandon_merge_flips_to_failed(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        recoverable_status: BatchItemStatus,
    ) -> None:
        """AC6: abandon-merge flips recoverable status → failed."""
        project_id = test_project.id
        item_id = f"F-abandon-{recoverable_status.value}"
        batch_id = f"B-abandon-{recoverable_status.value}"

        make_work_item(db_session, project_id, item_id)
        make_batch(db_session, project_id, batch_id)
        make_batch_item(db_session, project_id, batch_id, item_id, recoverable_status)
        db_session.commit()

        response = client.post(
            f"/project/{project_id}/api/item/{item_id}/abandon-merge",
            json={},
        )

        assert response.status_code in (200, 204), (
            f"abandon-merge should accept {recoverable_status.value}, "
            f"got {response.status_code}: {response.text[:200]}"
        )

        db_session.expire_all()
        bi: BatchItem | None = db_session.scalar(
            select(BatchItem).where(
                BatchItem.project_id == project_id,
                BatchItem.work_item_id == item_id,
            )
        )
        assert bi is not None
        assert bi.status == BatchItemStatus.failed, (
            f"Expected failed after abandon, got {bi.status.value}"
        )

    @pytest.mark.parametrize(
        "recoverable_status",
        [
            BatchItemStatus.merge_failed,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rebase_failed,
        ],
    )
    def test_abandon_merge_emits_event(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        recoverable_status: BatchItemStatus,
    ) -> None:
        """AC6: abandon-merge emits merge_abandoned daemon_event."""
        project_id = test_project.id
        item_id = f"F-event-{recoverable_status.value}"
        batch_id = f"B-event-{recoverable_status.value}"

        make_work_item(db_session, project_id, item_id)
        make_batch(db_session, project_id, batch_id)
        make_batch_item(db_session, project_id, batch_id, item_id, recoverable_status)
        db_session.commit()

        response = client.post(
            f"/project/{project_id}/api/item/{item_id}/abandon-merge",
            json={},
        )
        assert response.status_code in (200, 204)

        events = (
            db_session.query(DaemonEvent)
            .filter(
                DaemonEvent.project_id == project_id,
                DaemonEvent.event_type == "merge_abandoned",
            )
            .all()
        )
        assert len(events) >= 1, "merge_abandoned event must be emitted"
        assert events[0].entity_id == item_id
        assert events[0].entity_type == "work_item"

    @pytest.mark.parametrize(
        "rejected_status",
        [
            BatchItemStatus.pending,
            BatchItemStatus.completed,
            BatchItemStatus.merging,
            BatchItemStatus.failed,
            BatchItemStatus.setup_failed,
        ],
    )
    def test_abandon_merge_rejects_other_statuses(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        rejected_status: BatchItemStatus,
    ) -> None:
        """AC6: abandon-merge rejects non-recoverable statuses with 422."""
        project_id = test_project.id
        item_id = f"F-reject-{rejected_status.value}"
        batch_id = f"B-reject-{rejected_status.value}"

        make_work_item(db_session, project_id, item_id)
        make_batch(db_session, project_id, batch_id)
        make_batch_item(db_session, project_id, batch_id, item_id, rejected_status)
        db_session.commit()

        response = client.post(
            f"/project/{project_id}/api/item/{item_id}/abandon-merge",
            json={},
        )

        assert response.status_code == 422, (
            f"abandon-merge should reject {rejected_status.value}, got {response.status_code}"
        )

    def test_abandon_merge_appends_note(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """AC6: original notes preserved + abandon suffix appended."""
        project_id = test_project.id
        item_id = "F-notes-test"
        batch_id = "B-notes-test"
        original_note = "scope gate violation"

        make_work_item(db_session, project_id, item_id)
        make_batch(db_session, project_id, batch_id)
        make_batch_item(
            db_session,
            project_id,
            batch_id,
            item_id,
            BatchItemStatus.merge_failed,
            notes=original_note,
        )
        db_session.commit()

        response = client.post(
            f"/project/{project_id}/api/item/{item_id}/abandon-merge",
            json={},
        )
        assert response.status_code in (200, 204)

        db_session.expire_all()
        bi: BatchItem | None = db_session.scalar(
            select(BatchItem).where(
                BatchItem.project_id == project_id,
                BatchItem.work_item_id == item_id,
            )
        )
        assert bi is not None
        # Original note preserved
        assert bi.notes.startswith(original_note)
        # Suffix appended
        assert "[operator abandoned via abandon-merge]" in bi.notes


class TestMergeAbandonedSSEAllowlist:
    """AC7 unit: merge_abandoned in SSE registries (critical for toast delivery)."""

    def test_merge_abandoned_event_in_sse_toast_events(self) -> None:
        """AC7: merge_abandoned must be in _TOAST_EVENTS so SSE streams it."""
        assert "merge_abandoned" in _TOAST_EVENTS, (
            "merge_abandoned must be in _TOAST_EVENTS (CR-00028)"
        )

    def test_merge_abandoned_event_in_sse_toast_severity(self) -> None:
        """AC7: merge_abandoned must have a severity mapping so it toasts correctly."""
        assert "merge_abandoned" in _TOAST_SEVERITY, (
            "merge_abandoned must be in _TOAST_SEVERITY (CR-00028)"
        )
        assert _TOAST_SEVERITY["merge_abandoned"] == "warning", (
            "merge_abandoned severity must be warning (CR-00028)"
        )
