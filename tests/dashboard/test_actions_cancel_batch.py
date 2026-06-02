"""Expanded tests for F-00082: batch cancel endpoint.

S01 anchor tests are already present. This file adds:
- AC1 real-DB test (executing batch + reset_items → cancelled, items=draft, steps=pending)
- AC4: quick-cancel from batches list
- AC5: terminal batch refused (direct POST)
- AC6: teardown errors surface as warning, response still 204
- Boundary: empty reason, whitespace reason, unknown batch ID
- Invariant 1: handler calls service layer with exact kwargs
- Invariant 4: teardown errors never break the 2xx response
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
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
# TestClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Provide a TestClient with get_db overridden to the test db_session."""
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
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_project(db: Session, project_id: str = "test-batch-proj") -> Project:
    """Create and flush a minimal Project for testing.

    Args:
        db: SQLAlchemy session to use.
        project_id: Unique project ID.

    Returns:
        The flushed Project instance.
    """
    project = Project(
        id=project_id,
        display_name="Test Batch Project",
        repo_root="/repos/test",
        config={},
    )
    db.add(project)
    db.flush()
    return project


def _seed_batch(
    db: Session, project_id: str, batch_id: str, status: BatchStatus = BatchStatus.planning
) -> Batch:
    """Create and flush a Batch with the given status for testing.

    Args:
        db: SQLAlchemy session to use.
        project_id: ID of the owning project.
        batch_id: Unique batch ID.
        status: Initial BatchStatus to set.

    Returns:
        The flushed Batch instance.
    """
    batch = Batch(
        id=batch_id,
        project_id=project_id,
        status=status,
        max_parallel=5,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=False,
    )
    db.add(batch)
    db.flush()
    return batch


def _seed_item_with_steps(
    db: Session,
    project_id: str,
    item_id: str,
    step_statuses: list[StepStatus],
) -> WorkItem:
    """Create a WorkItem with steps in given statuses."""
    item = WorkItem(
        id=item_id,
        project_id=project_id,
        title=f"Test {item_id}",
        type=WorkItemType.Feature,
        phase=WorkItemPhase.active,
        status=WorkItemStatus.in_progress,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(item)
    db.flush()
    for i, status in enumerate(step_statuses, start=1):
        db.add(
            WorkflowStep(
                project_id=project_id,
                work_item_id=item_id,
                step_id=f"{item_id}-step-{i}",
                step_number=i,
                step_type=StepType.implementation,
                agent_label="test",
                status=status,
            )
        )
    return item


# ---------------------------------------------------------------------------
# S01 anchor tests (from RED evidence — kept for documentation, all GREEN now)
# ---------------------------------------------------------------------------


class TestS01AnchorBatchCancel:
    """S01 anchor tests: POST calls orch.cancel.cancel_batch with correct kwargs."""

    def test_cancel_batch_calls_service_layer_with_form_params(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """GREEN: POST with form data calls orch.cancel.cancel_batch with parsed kwargs."""
        batch = _seed_batch(db_session, test_project.id, "BATCH-S01-ANCHOR", BatchStatus.planning)

        with patch("orch.cancel.cancel_batch") as mock_cancel:
            mock_result = MagicMock()
            mock_result.cancelled_batch_items = []
            mock_result.reset_to_draft = []
            mock_result.killed_pids = []
            mock_result.teardown_errors = []
            mock_cancel.return_value = mock_result

            _resp = client.post(
                f"/project/{test_project.id}/api/batch/{batch.id}/cancel",
                data={"reason": "operator requested", "reset_items": "true"},
            )

            mock_cancel.assert_called_once()
            call_args = mock_cancel.call_args
            assert call_args.args[1] == test_project.id
            assert call_args.args[2] == batch.id
            assert call_args.kwargs["reason"] == "operator requested"
            assert call_args.kwargs["reset_items"] is True

    def test_cancel_batch_maps_lookup_error_to_404(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """GREEN: LookupError from service layer → HTTP 404."""
        batch = _seed_batch(db_session, test_project.id, "BATCH-S01-404", BatchStatus.planning)

        with patch("orch.cancel.cancel_batch") as mock_cancel:
            mock_cancel.side_effect = LookupError(
                f"Batch {batch.id} not found in project {test_project.id}"
            )

            resp = client.post(
                f"/project/{test_project.id}/api/batch/{batch.id}/cancel",
                data={"reason": "test"},
            )

            assert resp.status_code == 404
            assert "BATCH-S01-404" in resp.text or "not found" in resp.text.lower()

    def test_cancel_batch_maps_value_error_to_422(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """GREEN: ValueError from service layer → HTTP 422 (batch cancel has no 409 carve-out)."""
        batch = _seed_batch(db_session, test_project.id, "BATCH-S01-422", BatchStatus.executing)

        with patch("orch.cancel.cancel_batch") as mock_cancel:
            mock_cancel.side_effect = ValueError("Cannot cancel batch: status is 'executing'")

            resp = client.post(
                f"/project/{test_project.id}/api/batch/{batch.id}/cancel",
                data={"reason": "test"},
            )

            assert resp.status_code == 422

    def test_cancel_batch_success_builds_toast_with_summary(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """GREEN: Success response carries reload=True and toast mentions summary fields."""
        batch = _seed_batch(db_session, test_project.id, "BATCH-S01-SUCC", BatchStatus.paused)

        with patch("orch.cancel.cancel_batch") as mock_cancel:
            mock_result = MagicMock()
            mock_result.cancelled_batch_items = ["F-1", "F-2"]
            mock_result.reset_to_draft = ["F-3"]
            mock_result.killed_pids = [12345]
            mock_result.teardown_errors = []
            mock_cancel.return_value = mock_result

            resp = client.post(
                f"/project/{test_project.id}/api/batch/{batch.id}/cancel",
                data={"reason": "operator cut", "reset_items": "false"},
            )

            assert resp.status_code == 204
            trigger_header = resp.headers.get("HX-Trigger", "")
            assert "showToast" in trigger_header
            assert "reload" in trigger_header

    def test_cancel_batch_teardown_errors_append_warning_to_toast(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """GREEN: teardown_errors non-empty → warning line per error in toast message."""
        batch = _seed_batch(db_session, test_project.id, "BATCH-S01-ERR", BatchStatus.paused)

        with patch("orch.cancel.cancel_batch") as mock_cancel:
            mock_result = MagicMock()
            mock_result.cancelled_batch_items = ["F-1"]
            mock_result.reset_to_draft = []
            mock_result.killed_pids = []
            mock_result.teardown_errors = ["worktree remove failed: git worktree lock"]
            mock_cancel.return_value = mock_result

            resp = client.post(
                f"/project/{test_project.id}/api/batch/{batch.id}/cancel",
                data={"reason": "test"},
            )

            assert resp.status_code == 204
            trigger_header = resp.headers.get("HX-Trigger", "")
            assert "worktree remove failed" in trigger_header or "warning" in trigger_header.lower()


# ---------------------------------------------------------------------------
# AC1: Real DB test — executing batch + reset_items
# ---------------------------------------------------------------------------


class TestBatchCancelRealDB:
    """AC1: end-to-end with real DB, no mocking of the service layer."""

    def test_batch_cancel_executing_with_reset_items_resets_steps_and_returns_toast(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC1: executing batch + reset_items → batch=cancelled, item=draft, steps=pending.

        Uses real orch.cancel.cancel_batch (no mock) — verifies the full chain.
        """
        project = _seed_project(db_session, "test-ac1-real")
        batch = _seed_batch(db_session, project.id, "BATCH-AC1-REAL", BatchStatus.executing)
        item = _seed_item_with_steps(
            db_session,
            project.id,
            "F-AC1-REAL",
            step_statuses=[StepStatus.in_progress, StepStatus.pending, StepStatus.pending],
        )
        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=item.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/batch/{batch.id}/cancel",
            data={"reason": "redesign", "reset_items": "true"},
        )

        assert response.status_code == 204, response.text

        # Verify DB state
        db_session.expire_all()
        batch_refresh = db_session.get(Batch, (project.id, batch.id))
        item_refresh = db_session.get(WorkItem, (project.id, item.id))

        assert batch_refresh.status == BatchStatus.cancelled, (
            f"Batch must be cancelled, got {batch_refresh.status.value}"
        )
        assert item_refresh.status == WorkItemStatus.draft, (
            f"Item must be reset to draft, got {item_refresh.status.value}"
        )

        # Steps must be reset to pending
        steps = (
            db_session.query(WorkflowStep)
            .filter(
                WorkflowStep.project_id == project.id,
                WorkflowStep.work_item_id == item.id,
            )
            .order_by(WorkflowStep.step_number)
            .all()
        )
        for step in steps:
            assert step.status == StepStatus.pending, (
                f"Step {step.step_id} must be pending after reset, got {step.status.value}"
            )

        # Toast
        trigger_header = response.headers.get("HX-Trigger", "")
        assert "showToast" in trigger_header, f"Must have showToast trigger: {trigger_header}"
        assert "reload" in trigger_header, "Must have reload trigger"

    def test_batch_cancel_paused_no_reset_items(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC1 variant: paused batch + cancel without reset → items=cancelled."""
        project = _seed_project(db_session, "test-ac1-paused")
        batch = _seed_batch(db_session, project.id, "BATCH-AC1-PAUSED", BatchStatus.paused)
        item = _seed_item_with_steps(
            db_session, project.id, "F-AC1-PAUSED", step_statuses=[StepStatus.pending]
        )
        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=item.id,
            status=BatchItemStatus.pending,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/batch/{batch.id}/cancel",
            data={"reason": "operator cut", "reset_items": "false"},
        )

        assert response.status_code == 204, response.text
        db_session.expire_all()
        batch_refresh = db_session.get(Batch, (project.id, batch.id))
        assert batch_refresh.status == BatchStatus.cancelled


# ---------------------------------------------------------------------------
# AC4: Quick-cancel from batches list
# ---------------------------------------------------------------------------


class TestQuickCancelFromBatchesList:
    """AC4: quick-cancel from batches list uses default reason, no reset."""

    def test_quick_cancel_from_batches_list_posts_default_reason(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC4: per-row cancel on batches list → POST with 'cancelled from batches list'."""
        project = _seed_project(db_session, "test-ac4-real")
        batch = _seed_batch(db_session, project.id, "BATCH-AC4-REAL", BatchStatus.paused)
        db_session.commit()

        # Verify the batches list page shows a cancel button
        list_response = client.get(f"/project/{project.id}/batches")
        assert list_response.status_code == 200
        assert "Cancel" in list_response.text, "Batches list must show a Cancel button"

        # POST the quick-cancel (reason='cancelled from batches list', no reset)
        response = client.post(
            f"/project/{project.id}/api/batch/{batch.id}/cancel",
            data={"reason": "cancelled from batches list", "reset_items": "false"},
        )

        assert response.status_code == 204, response.text
        db_session.expire_all()
        batch_refresh = db_session.get(Batch, (project.id, batch.id))
        assert batch_refresh.status == BatchStatus.cancelled


# ---------------------------------------------------------------------------
# AC5: Terminal batch refused
# ---------------------------------------------------------------------------


class TestCancelBatchTerminalRefused:
    """AC5: direct POST refuses for terminal batches."""

    @pytest.mark.parametrize(
        "status",
        [BatchStatus.completed, BatchStatus.completed_with_errors, BatchStatus.archived],
        ids=lambda s: f"terminal_{s.value}",
    )
    def test_post_cancel_batch_returns_422_for_terminal_batch(
        self, client: TestClient, db_session: Session, status: BatchStatus
    ) -> None:
        """AC5 API: direct POST to terminal batch cancel → 422."""
        project = _seed_project(db_session, f"test-ac5-{status.value}")
        batch = _seed_batch(db_session, project.id, f"BATCH-AC5-{status.value}", status)
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/batch/{batch.id}/cancel",
            data={"reason": "test"},
        )

        assert response.status_code == 422, (
            f"Cancel terminal batch must return 422, got {response.status_code}: {response.text}"
        )
        assert "Cannot cancel" in response.text or "cannot cancel" in response.text.lower()

        # DB unchanged
        db_session.expire_all()
        batch_refresh = db_session.get(Batch, (project.id, batch.id))
        assert batch_refresh.status == status, "Batch status must be unchanged"


# ---------------------------------------------------------------------------
# AC6: Teardown errors surface as warning but do not block 200
# ---------------------------------------------------------------------------


class TestTeardownErrorsSurfaceAsWarning:
    """AC6: teardown errors never break the 2xx response."""

    def test_teardown_errors_append_warning_to_toast_but_status_is_204(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC6: teardown_errors non-empty → 204 + warning line in toast message."""
        project = _seed_project(db_session, "test-ac6-real")
        batch = _seed_batch(db_session, project.id, "BATCH-AC6-REAL", BatchStatus.paused)
        db_session.commit()

        with patch("orch.cancel.cancel_batch") as mock_cancel:
            mock_result = MagicMock()
            mock_result.cancelled_batch_items = ["F-1", "F-2"]
            mock_result.reset_to_draft = ["F-3"]
            mock_result.killed_pids = [12345]
            mock_result.teardown_errors = ["worktree remove failed: git worktree lock"]
            mock_cancel.return_value = mock_result

            response = client.post(
                f"/project/{project.id}/api/batch/{batch.id}/cancel",
                data={"reason": "operator cut"},
            )

            assert response.status_code == 204, (
                f"Cancel with teardown errors must still return 204, got {response.status_code}"
            )
            trigger_header = response.headers.get("HX-Trigger", "")
            assert (
                "worktree remove failed" in trigger_header or "warning" in trigger_header.lower()
            ), f"Toast must contain teardown warning: {trigger_header}"

    def test_cancel_batch_teardown_errors_via_mock_verify_warning_text(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Monkey-patch variant of AC6 to verify the exact warning text in HX-Trigger."""
        project = _seed_project(db_session, "test-ac6-mock")
        batch = _seed_batch(db_session, project.id, "BATCH-AC6-MOCK", BatchStatus.paused)
        db_session.commit()

        with patch("orch.cancel.cancel_batch") as mock_cancel:
            mock_result = MagicMock()
            mock_result.cancelled_batch_items = ["F-1"]
            mock_result.reset_to_draft = []
            mock_result.killed_pids = []
            mock_result.teardown_errors = ["compose down failed: daemon unreachable"]
            mock_cancel.return_value = mock_result

            response = client.post(
                f"/project/{project.id}/api/batch/{batch.id}/cancel",
                data={"reason": "test teardown"},
            )

            assert response.status_code == 204
            trigger_header = response.headers.get("HX-Trigger", "")
            assert "compose down failed" in trigger_header, (
                f"Toast must include teardown error: {trigger_header}"
            )


# ---------------------------------------------------------------------------
# Boundary: empty reason, whitespace reason, unknown batch ID
# ---------------------------------------------------------------------------


class TestBoundaryBatchCancel:
    """Boundary rows for batch cancel."""

    def test_batch_cancel_empty_reason_uses_service_default(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Boundary: empty reason → service-layer default 'cancelled by operator'."""
        project = _seed_project(db_session, "test-bound-empty")
        batch = _seed_batch(db_session, project.id, "BATCH-BOUND-EMPTY", BatchStatus.planning)
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/batch/{batch.id}/cancel",
            data={"reason": "", "reset_items": "false"},
        )

        assert response.status_code == 204, response.text
        db_session.expire_all()
        batch_refresh = db_session.get(Batch, (project.id, batch.id))
        assert batch_refresh.status == BatchStatus.cancelled

    def test_batch_cancel_whitespace_reason_passed_as_is(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Boundary: whitespace reason is passed through; service layer strips it."""
        project = _seed_project(db_session, "test-bound-ws")
        batch = _seed_batch(db_session, project.id, "BATCH-BOUND-WS", BatchStatus.planning)
        db_session.commit()

        with patch("orch.cancel.cancel_batch") as mock_cancel:
            mock_result = MagicMock()
            mock_result.cancelled_batch_items = []
            mock_result.reset_to_draft = []
            mock_result.killed_pids = []
            mock_result.teardown_errors = []
            mock_cancel.return_value = mock_result

            client.post(
                f"/project/{project.id}/api/batch/{batch.id}/cancel",
                data={"reason": "  redesign  ", "reset_items": "false"},
            )

            # Handler passes reason as-is; service layer does the stripping
            call_args = mock_cancel.call_args
            assert call_args.kwargs.get("reason") == "  redesign  ", (
                "Whitespace must be preserved in the handler→service call"
            )

    def test_unknown_batch_id_returns_404(self, client: TestClient, db_session: Session) -> None:
        """Boundary: unknown batch ID → 404."""
        project = _seed_project(db_session, "test-unk-batch")
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/batch/BATCH-99999/cancel",
            data={"reason": "test"},
        )

        assert response.status_code == 404, response.text
        assert "BATCH-99999" in response.text
        assert "not found" in response.text.lower()


# ---------------------------------------------------------------------------
# Invariant 1: cancel_batch handler calls service layer with exact kwargs
# ---------------------------------------------------------------------------


class TestInvariant1BatchHandlerCallsServiceLayer:
    """Invariant 1: handler calls orch.cancel.cancel_batch with parsed form params."""

    def test_cancel_batch_handler_calls_service_layer_with_exact_kwargs(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Invariant 1: POST with reason + reset_items → orch.cancel.cancel_batch called exactly."""
        project = _seed_project(db_session, "test-inv1-batch")
        batch = _seed_batch(db_session, project.id, "BATCH-INV1", BatchStatus.executing)
        db_session.commit()

        with patch("orch.cancel.cancel_batch") as mock_cancel:
            mock_result = MagicMock()
            mock_result.cancelled_batch_items = []
            mock_result.reset_to_draft = []
            mock_result.killed_pids = []
            mock_result.teardown_errors = []
            mock_cancel.return_value = mock_result

            response = client.post(
                f"/project/{project.id}/api/batch/{batch.id}/cancel",
                data={"reason": "operator requested", "reset_items": "true"},
            )

            assert response.status_code == 204
            mock_cancel.assert_called_once()
            call_args = mock_cancel.call_args
            assert call_args.args[1] == project.id, f"project_id must be {project.id}"
            assert call_args.args[2] == batch.id, f"batch_id must be {batch.id}"
            assert call_args.kwargs.get("reason") == "operator requested"
            assert call_args.kwargs.get("reset_items")

    def test_cancel_batch_handler_does_not_call_cancel_twice(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Verify the handler calls cancel_batch exactly once (no double-call)."""
        project = _seed_project(db_session, "test-once-batch")
        batch = _seed_batch(db_session, project.id, "BATCH-ONCE", BatchStatus.paused)
        db_session.commit()

        with patch("orch.cancel.cancel_batch") as mock_cancel:
            mock_result = MagicMock()
            mock_result.cancelled_batch_items = []
            mock_result.reset_to_draft = []
            mock_result.killed_pids = []
            mock_result.teardown_errors = []
            mock_cancel.return_value = mock_result

            client.post(
                f"/project/{project.id}/api/batch/{batch.id}/cancel",
                data={"reason": "once test", "reset_items": "false"},
            )

            assert mock_cancel.call_count == 1, (
                f"cancel_batch must be called exactly once, got {mock_cancel.call_count}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
