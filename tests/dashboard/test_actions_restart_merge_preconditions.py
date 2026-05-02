"""AC5 unit: restart-merge preconditions for recoverable merge statuses.

AC5: POST /actions/<proj>/item/<id>/restart-merge accepts merge_failed,
migration_invalid, and migration_rebase_failed as preconditions and resets
the BatchItem to completed.

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
) -> BatchItem:
    item = BatchItem(
        id=f"{project_id}_{work_item_id}",
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=work_item_id,
        execution_group=0,
        status=status,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        worktree_info={"path": f"/wt/{work_item_id}"},
        notes="initial note" if status != BatchItemStatus.pending else None,
    )
    db.add(item)
    db.flush()
    return item


# ---------------------------------------------------------------------------
# AC5: restart-merge preconditions
# ---------------------------------------------------------------------------


class TestRestartMergePreconditions:
    """AC5: restart-merge accepts recoverable statuses and resets to completed."""

    @pytest.mark.parametrize(
        "recoverable_status",
        [
            BatchItemStatus.merge_failed,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rebase_failed,
        ],
    )
    def test_restart_merge_accepts_recoverable_status(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        recoverable_status: BatchItemStatus,
    ) -> None:
        """AC5: POST restart-merge for recoverable status → 200/204 (not 422)."""
        project_id = test_project.id
        item_id = f"F-recoverable-{recoverable_status.value}"
        batch_id = f"B-recoverable-{recoverable_status.value}"

        make_work_item(db_session, project_id, item_id)
        make_batch(db_session, project_id, batch_id)
        make_batch_item(db_session, project_id, batch_id, item_id, recoverable_status)
        db_session.commit()

        response = client.post(
            f"/project/{project_id}/api/item/{item_id}/restart-merge",
            json={},
        )

        assert response.status_code in (200, 204), (
            f"restart-merge should accept {recoverable_status.value}, "
            f"got {response.status_code}: {response.text[:200]}"
        )

    @pytest.mark.parametrize(
        "recoverable_status",
        [
            BatchItemStatus.merge_failed,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rebase_failed,
        ],
    )
    def test_restart_merge_resets_to_completed(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        recoverable_status: BatchItemStatus,
    ) -> None:
        """AC5: restart-merge resets BatchItem.status to completed."""
        project_id = test_project.id
        item_id = f"F-completed-{recoverable_status.value}"
        batch_id = f"B-completed-{recoverable_status.value}"

        make_work_item(db_session, project_id, item_id)
        make_batch(db_session, project_id, batch_id)
        make_batch_item(db_session, project_id, batch_id, item_id, recoverable_status)
        db_session.commit()

        response = client.post(
            f"/project/{project_id}/api/item/{item_id}/restart-merge",
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
        assert bi.status == BatchItemStatus.completed, (
            f"Expected completed after restart-merge, got {bi.status.value}"
        )
        # Notes cleared
        assert bi.notes is None

    def test_restart_merge_rejects_pending(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """restart-merge for a non-recoverable status → 422."""
        project_id = test_project.id
        item_id = "F-pending-reject"
        batch_id = "B-pending-reject"

        make_work_item(db_session, project_id, item_id)
        make_batch(db_session, project_id, batch_id)
        make_batch_item(db_session, project_id, batch_id, item_id, BatchItemStatus.pending)
        db_session.commit()

        response = client.post(
            f"/project/{project_id}/api/item/{item_id}/restart-merge",
            json={},
        )

        assert response.status_code == 422, (
            f"restart-merge should reject pending status, got {response.status_code}"
        )

    def test_restart_merge_rejects_completed(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """restart-merge for completed status → 422 (already merged or in progress)."""
        project_id = test_project.id
        item_id = "F-completed-reject"
        batch_id = "B-completed-reject"

        make_work_item(db_session, project_id, item_id)
        make_batch(db_session, project_id, batch_id)
        make_batch_item(db_session, project_id, batch_id, item_id, BatchItemStatus.completed)
        db_session.commit()

        response = client.post(
            f"/project/{project_id}/api/item/{item_id}/restart-merge",
            json={},
        )

        assert response.status_code == 422

    def test_restart_merge_emits_merge_restarted_event(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """restart-merge emits merge_restarted daemon_event."""
        project_id = test_project.id
        item_id = "F-event-test"
        batch_id = "B-event-test"

        make_work_item(db_session, project_id, item_id)
        make_batch(db_session, project_id, batch_id)
        make_batch_item(db_session, project_id, batch_id, item_id, BatchItemStatus.merge_failed)
        db_session.commit()

        response = client.post(
            f"/project/{project_id}/api/item/{item_id}/restart-merge",
            json={},
        )
        assert response.status_code in (200, 204)

        events = (
            db_session.query(DaemonEvent)
            .filter(
                DaemonEvent.project_id == project_id,
                DaemonEvent.event_type == "merge_restarted",
            )
            .all()
        )
        assert len(events) >= 1, "merge_restarted event must be emitted"
        assert events[0].entity_id == item_id
