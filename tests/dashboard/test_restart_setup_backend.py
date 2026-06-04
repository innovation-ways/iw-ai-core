"""CR-00029 smoke tests for restart_setup backend changes.

Tests:
1. `_synthetic_setup_step` returns `restartable=True` for the documented happy path
2. `restart_setup` endpoint returns 422 for an item where a step is `in_progress`
3. `restart_setup` endpoint succeeds for the happy path
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers.items import _synthetic_setup_step
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Fake BatchItem for unit tests (no DB required)
# ---------------------------------------------------------------------------


def _fake_batch_item(status: BatchItemStatus) -> Any:
    """Build a fake BatchItem-like object for unit testing restartable logic."""
    obj = SimpleNamespace()
    obj.status = status
    obj.worktree_info = None
    obj.started_at = None
    obj.notes = "setup failed" if status == BatchItemStatus.setup_failed else None
    return obj


# ---------------------------------------------------------------------------
# TestClient fixture (mirrors existing dashboard tests)
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
# Tests: _synthetic_setup_step restartable flag
# ---------------------------------------------------------------------------


class TestSyntheticSetupStepRestartable:
    """Smoke tests for _synthetic_setup_step restartable flag."""

    def test_restartable_true_when_setup_failed_and_all_steps_pending(self) -> None:
        """restartable is True when BatchItem is setup_failed and all steps still pending."""
        bi = _fake_batch_item(BatchItemStatus.setup_failed)
        step_detail = _synthetic_setup_step(bi, step_statuses=["pending"])
        assert step_detail.restartable is True

    def test_restartable_true_when_failed_and_all_steps_pending(self) -> None:
        """restartable is True for BatchItemStatus.failed (cascade) with all steps pending."""
        bi = _fake_batch_item(BatchItemStatus.failed)
        step_detail = _synthetic_setup_step(bi, step_statuses=["pending"])
        assert step_detail.restartable is True

    def test_restartable_false_when_batch_item_not_failed(self) -> None:
        """restartable is False when BatchItem is in a non-failed status."""
        bi = _fake_batch_item(BatchItemStatus.completed)
        step_detail = _synthetic_setup_step(bi, step_statuses=["pending"])
        assert step_detail.restartable is False

    def test_restartable_false_when_any_step_not_pending(self) -> None:
        """restartable is False when any WorkflowStep has progressed past pending."""
        bi = _fake_batch_item(BatchItemStatus.setup_failed)
        step_detail = _synthetic_setup_step(bi, step_statuses=["in_progress"])
        assert step_detail.restartable is False

    def test_restartable_true_when_step_statuses_empty(self) -> None:
        """restartable is True when step_statuses is an empty list (no steps defined yet).

        Empty list means no step has progressed past pending, so restart is safe.
        """
        bi = _fake_batch_item(BatchItemStatus.setup_failed)
        step_detail = _synthetic_setup_step(bi, step_statuses=[])
        assert step_detail.restartable is True

    def test_restartable_false_when_step_statuses_none(self) -> None:
        """restartable is False when step_statuses is None (backwards-compatible default)."""
        bi = _fake_batch_item(BatchItemStatus.setup_failed)
        step_detail = _synthetic_setup_step(bi, step_statuses=None)
        assert step_detail.restartable is False

    def test_restartable_false_when_bi_is_none(self) -> None:
        """restartable is False when bi is None (no BatchItem for this item)."""
        step_detail = _synthetic_setup_step(None, step_statuses=["pending"])
        assert step_detail.restartable is False


# ---------------------------------------------------------------------------
# Tests: restart_setup endpoint
# ---------------------------------------------------------------------------


class TestRestartSetupEndpoint:
    """Smoke tests for the POST /item/{item_id}/restart-setup endpoint."""

    def test_restart_setup_returns_422_when_no_batch_item(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Returns 422 when no BatchItem in setup_failed/failed status exists."""
        item_id = "CR00029-no-batch"
        work_item = WorkItem(
            id=item_id,
            project_id=test_project.id,
            type=WorkItemType.Issue,
            title="CR-00029 Test Item",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(work_item)
        db_session.flush()
        db_session.commit()

        resp = client.post(f"/project/{test_project.id}/api/item/{item_id}/restart-setup")
        assert resp.status_code == 422
        assert "Cannot restart setup" in resp.json()["detail"]

    def test_restart_setup_returns_422_when_step_has_progressed(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Returns 422 when a WorkflowStep has already progressed past pending."""
        item_id = "CR00029-progressed"

        work_item = WorkItem(
            id=item_id,
            project_id=test_project.id,
            type=WorkItemType.Issue,
            title="CR-00029 Test Item",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(work_item)
        db_session.flush()

        batch = Batch(
            id="CR00029-batch-20",
            project_id=test_project.id,
            status=BatchStatus.approved,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            work_item_id=item_id,
            batch_id="CR00029-batch-20",
            status=BatchItemStatus.setup_failed,
            notes="Setup failed",
        )
        db_session.add(batch_item)

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.in_progress,
        )
        db_session.add(step)
        db_session.flush()
        db_session.commit()

        resp = client.post(f"/project/{test_project.id}/api/item/{item_id}/restart-setup")
        assert resp.status_code == 422
        assert "progressed past pending" in resp.json()["detail"]

    def test_restart_setup_success_for_setup_failed_with_all_pending(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Succeeds for BatchItem in setup_failed with all WorkflowSteps still pending."""
        item_id = "CR00029-happy"

        work_item = WorkItem(
            id=item_id,
            project_id=test_project.id,
            type=WorkItemType.Issue,
            title="CR-00029 Test Item",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(work_item)
        db_session.flush()

        batch = Batch(
            id="CR00029-batch-21",
            project_id=test_project.id,
            status=BatchStatus.approved,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            work_item_id=item_id,
            batch_id="CR00029-batch-21",
            status=BatchItemStatus.setup_failed,
            notes="Setup failed",
        )
        db_session.add(batch_item)

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.pending,
        )
        db_session.add(step)
        db_session.flush()
        db_session.commit()

        resp = client.post(f"/project/{test_project.id}/api/item/{item_id}/restart-setup")
        assert resp.status_code == 204, resp.text

        # Verify item status was reset to approved
        db_session.expire_all()
        item = db_session.scalar(select(WorkItem).where(WorkItem.id == item_id))
        assert item.status == WorkItemStatus.approved

        # Verify BatchItem was reset to pending
        bi_after = db_session.scalar(
            select(BatchItem).where(
                BatchItem.work_item_id == item_id,
            )
        )
        assert bi_after.status == BatchItemStatus.pending

    def test_restart_setup_success_for_failed_status_with_no_step_runs(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Succeeds for BatchItem.status=failed (cascade scenario) with all steps pending."""
        item_id = "CR00029-cascade"

        work_item = WorkItem(
            id=item_id,
            project_id=test_project.id,
            type=WorkItemType.Issue,
            title="CR-00029 Test Item",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(work_item)
        db_session.flush()

        batch = Batch(
            id="CR00029-batch-22",
            project_id=test_project.id,
            status=BatchStatus.approved,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            work_item_id=item_id,
            batch_id="CR00029-batch-22",
            status=BatchItemStatus.failed,  # cascade failure
            notes="Cascade failure",
        )
        db_session.add(batch_item)

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.pending,
        )
        db_session.add(step)
        db_session.flush()
        db_session.commit()

        resp = client.post(f"/project/{test_project.id}/api/item/{item_id}/restart-setup")
        assert resp.status_code == 204, resp.text
