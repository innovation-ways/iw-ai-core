"""Integration tests for orch.services.batches — batch service round-trip tests."""

from __future__ import annotations

from typing import Any

import pytest

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_approved_item(db_session: Any, project_id: str, item_id: str) -> WorkItem:
    """Insert a minimal approved WorkItem.

    Args:
        db_session: Active SQLAlchemy session.
        project_id: Project scope.
        item_id: Work item identifier.

    Returns:
        The inserted WorkItem ORM instance with approved status.
    """
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Feature,
        title=f"Item {item_id}",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
    )
    db_session.add(item)
    db_session.flush()
    return item


def _make_batch(
    db_session: Any,
    project_id: str,
    batch_id: str,
    *,
    status: BatchStatus = BatchStatus.planning,
    item_ids: list[str] | None = None,
) -> Batch:
    """Insert a minimal Batch with optional BatchItems.

    Args:
        db_session: Active SQLAlchemy session.
        project_id: Project scope.
        batch_id: Batch identifier.
        status: Initial batch status.
        item_ids: Optional list of work item IDs to add as batch items.

    Returns:
        The inserted Batch ORM instance.
    """
    batch = Batch(
        project_id=project_id,
        id=batch_id,
        status=status,
        max_parallel=4,
        auto_publish=False,
        auto_merge=True,
    )
    db_session.add(batch)
    db_session.flush()

    for iid in item_ids or []:
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=iid,
                execution_group=0,
                status=BatchItemStatus.pending,
            )
        )
    db_session.flush()
    return batch


# ---------------------------------------------------------------------------
# get_batch_status
# ---------------------------------------------------------------------------


class TestGetBatchStatus:
    """Covers the batch-status dict shape."""

    def test_get_batch_status_returns_expected_keys(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that get_batch_status returns concrete field values for a known batch."""
        from orch.services.batches import get_batch_status

        _make_batch(db_session, test_project.id, "BATCH-00001")
        result = get_batch_status(db_session, test_project.id, "BATCH-00001")
        assert result["batch_id"] == "BATCH-00001"
        assert result["project_id"] == test_project.id
        assert result["status"] == "planning"
        assert result["items"] == []

    def test_get_batch_status_nonexistent_raises_service_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that get_batch_status raises ServiceError when batch not found."""
        from orch.services._common import ServiceError
        from orch.services.batches import get_batch_status

        with pytest.raises(ServiceError):
            get_batch_status(db_session, test_project.id, "BATCH-99999")


# ---------------------------------------------------------------------------
# approve_batch
# ---------------------------------------------------------------------------


class TestApproveBatch:
    """Covers approve_batch transition."""

    def test_approve_batch_planning_to_approved(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that approve_batch transitions a planning batch to approved."""
        from orch.services.batches import approve_batch

        _make_batch(db_session, test_project.id, "BATCH-00010")
        result = approve_batch(db_session, test_project.id, "BATCH-00010")
        assert result["status"].find("approved") != -1

    def test_approve_batch_nonexistent_raises_service_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that approve_batch raises ServiceError when batch not found."""
        from orch.services._common import ServiceError
        from orch.services.batches import approve_batch

        with pytest.raises(ServiceError):
            approve_batch(db_session, test_project.id, "BATCH-99999")

    def test_approve_batch_wrong_status_raises_service_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that approve_batch raises ServiceError when batch is not in planning."""
        from orch.services._common import ServiceError
        from orch.services.batches import approve_batch

        _make_batch(db_session, test_project.id, "BATCH-00011", status=BatchStatus.approved)
        with pytest.raises(ServiceError):
            approve_batch(db_session, test_project.id, "BATCH-00011")


# ---------------------------------------------------------------------------
# pause_batch / resume_batch
# ---------------------------------------------------------------------------


class TestPauseResumeBatch:
    """Covers pause/resume batch transitions."""

    def test_pause_executing_batch(self, db_session: Any, test_project: Project) -> None:
        """Verifies that pause_batch transitions an executing batch to paused."""
        from orch.services.batches import pause_batch

        _make_batch(db_session, test_project.id, "BATCH-00020", status=BatchStatus.executing)
        result = pause_batch(db_session, test_project.id, "BATCH-00020")
        assert result["status"].find("paused") != -1

    def test_resume_paused_batch(self, db_session: Any, test_project: Project) -> None:
        """Verifies that resume_batch transitions a paused batch to executing."""
        from orch.services.batches import resume_batch

        _make_batch(db_session, test_project.id, "BATCH-00021", status=BatchStatus.paused)
        result = resume_batch(db_session, test_project.id, "BATCH-00021")
        assert result["status"].find("executing") != -1

    def test_pause_nonexistent_batch_raises_service_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that pause_batch raises ServiceError when batch not found."""
        from orch.services._common import ServiceError
        from orch.services.batches import pause_batch

        with pytest.raises(ServiceError):
            pause_batch(db_session, test_project.id, "BATCH-99999")


# ---------------------------------------------------------------------------
# list_batches
# ---------------------------------------------------------------------------


class TestListBatches:
    """Covers the list_batches service function."""

    def test_list_batches_returns_expected_shape(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that list_batches returns an empty batches list for a project with no data."""
        from orch.services.batches import list_batches

        result = list_batches(db_session, test_project.id)
        assert result["batches"] == []

    def test_list_batches_returns_created_batch(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that list_batches returns exactly one entry with the correct batch_id."""
        from orch.services.batches import list_batches

        _make_batch(db_session, test_project.id, "BATCH-00030")
        result = list_batches(db_session, test_project.id)
        assert len(result["batches"]) == 1
        assert result["batches"][0]["batch_id"] == "BATCH-00030"

    def test_list_batches_item_shape(self, db_session: Any, test_project: Project) -> None:
        """Verifies that a batch entry has the correct field values for a known planning batch."""
        from orch.services.batches import list_batches

        _make_batch(db_session, test_project.id, "BATCH-00031")
        result = list_batches(db_session, test_project.id)
        assert len(result["batches"]) == 1
        batch = result["batches"][0]
        assert batch["batch_id"] == "BATCH-00031"
        assert batch["status"] == "planning"
        assert batch["item_count"] == 0
        assert batch["completed_count"] == 0
        assert batch["created_at"] is not None

    def test_list_batches_filters_by_status(self, db_session: Any, test_project: Project) -> None:
        """Verifies that list_batches status filter excludes non-matching batches."""
        from orch.services.batches import list_batches

        _make_batch(db_session, test_project.id, "BATCH-00040", status=BatchStatus.planning)
        _make_batch(db_session, test_project.id, "BATCH-00041", status=BatchStatus.approved)
        result = list_batches(db_session, test_project.id, status="planning")
        batch_ids = [b["batch_id"] for b in result["batches"]]
        assert "BATCH-00040" in batch_ids
        assert "BATCH-00041" not in batch_ids
