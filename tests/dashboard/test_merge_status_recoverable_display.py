"""AC7 unit: _merge_status() maps recoverable statuses to 'merge_failed' display value.

AC7: Given a BatchItem in merge_failed/migration_invalid/migration_rebase_failed,
_merge_status() returns 'merge_failed' (for badge + button rendering).
Also verifies legacy 'failed' is unchanged and merging→'in_progress' is preserved.

Uses the FastAPI TestClient pattern from existing dashboard tests — this
module imports from dashboard.routers.items which loads database session
factories, so a testcontainer db_session is required (not a true unit test
in the no-I/O sense, but a fast router-level test).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers.items import _merge_status
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

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# TestClient fixture
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
# AC7: _merge_status mapping
# ---------------------------------------------------------------------------


def _fake_batch_item(
    status: BatchItemStatus,
    merged_at: datetime | None = None,
    worktree_info: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a minimal mock BatchItem for _merge_status testing."""
    bi = MagicMock(spec=BatchItem)
    bi.status = status
    bi.merged_at = merged_at
    bi.worktree_info = worktree_info or {"path": "/wt/test"}
    return bi


class TestMergeStatusRecoverableMapping:
    """AC7: _merge_status maps recoverable statuses to 'merge_failed'."""

    @pytest.mark.parametrize(
        "recoverable_status",
        [
            BatchItemStatus.merge_failed,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rebase_failed,
        ],
    )
    def test_merge_status_maps_recoverable_to_merge_failed(
        self,
        recoverable_status: BatchItemStatus,
    ) -> None:
        """AC7: recoverable status → _merge_status returns 'merge_failed'."""
        bi = _fake_batch_item(recoverable_status)
        assert _merge_status(bi) == "merge_failed", (
            f"_merge_status({recoverable_status.value}) must return 'merge_failed'"
        )

    def test_merge_status_legacy_failed_unchanged(self) -> None:
        """AC7: legacy failed status → 'failed' (no regression)."""
        bi = _fake_batch_item(BatchItemStatus.failed)
        assert _merge_status(bi) == "failed"

    def test_merge_status_merging_unchanged(self) -> None:
        """AC7: merging → 'in_progress' (no regression)."""
        bi = _fake_batch_item(BatchItemStatus.merging)
        assert _merge_status(bi) == "in_progress"

    def test_merge_status_completed_unchanged(self) -> None:
        """AC7: completed → 'in_progress' (waiting for merge to finish)."""
        bi = _fake_batch_item(BatchItemStatus.completed)
        assert _merge_status(bi) == "in_progress"

    def test_merge_status_merged_shows_completed(self) -> None:
        """merged items show 'completed' display (merge done)."""
        bi = _fake_batch_item(BatchItemStatus.merged, merged_at=datetime.now(UTC))
        assert _merge_status(bi) == "completed"

    def test_merge_status_none_returns_pending(self) -> None:
        """_merge_status(None) → 'pending' (no item / no worktree)."""
        assert _merge_status(None) == "pending"

    def test_merge_status_no_worktree_returns_pending(self) -> None:
        """_merge_status with no worktree_info → 'pending' (regardless of status).

        Per _merge_status: if worktree_info is falsy, return 'pending' immediately.
        This is a display-level guard — no worktree means nothing to merge.
        """
        bi = _fake_batch_item(BatchItemStatus.merge_failed, worktree_info=None)
        assert _merge_status(bi) == "pending"


class TestMergeStatusDBIntegration:
    """AC7: _merge_status with real DB-backed BatchItem rows via client fixture."""

    def test_merge_status_merge_failed_in_db(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """AC7: BatchItem in DB with merge_failed status → _merge_status returns merge_failed."""
        project_id = test_project.id
        item_id = "F-db-merge-failed"
        batch_id = "B-db-merge-failed"

        work_item = WorkItem(
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
        db_session.add(work_item)

        batch = Batch(
            id=batch_id,
            project_id=project_id,
            status=BatchStatus.executing,
            max_parallel=4,
            cli_tool="opencode",
            auto_publish=False,
        )
        db_session.add(batch)

        batch_item = BatchItem(
            id=f"{project_id}_{item_id}",
            project_id=project_id,
            batch_id=batch_id,
            work_item_id=item_id,
            execution_group=0,
            status=BatchItemStatus.merge_failed,
            started_at=datetime(2024, 1, 1, tzinfo=UTC),
            worktree_info={"path": f"/wt/{item_id}"},
        )
        db_session.add(batch_item)
        db_session.commit()

        # Verify _merge_status handles DB row
        assert _merge_status(batch_item) == "merge_failed"
