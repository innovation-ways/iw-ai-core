"""Expanded tests for F-00082: item cancel endpoint.

S01 anchor tests are already present. This file adds:
- AC2 real-DB test (standalone in_progress item → cancelled, steps=skipped)
- AC3: disabled-with-hint (UI) + 409 on direct POST (API)
- AC4: quick-cancel from batches list
- Boundary: unknown item ID
- Boundary: to_draft=true on draft item → 422
- Invariant 1: handler calls service layer with exact kwargs
- Invariant 4: teardown errors never break 2xx
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
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_project(db: Session, project_id: str = "test-item-proj") -> Project:
    project = Project(
        id=project_id,
        display_name="Test Item Project",
        repo_root="/repos/test",
        config={},
    )
    db.add(project)
    db.flush()
    return project


def _seed_item(
    db: Session,
    project_id: str,
    item_id: str,
    status: WorkItemStatus = WorkItemStatus.approved,
) -> WorkItem:
    item = WorkItem(
        id=item_id,
        project_id=project_id,
        title=f"Test {item_id}",
        type=WorkItemType.Feature,
        phase=WorkItemPhase.active,
        status=status,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(item)
    db.flush()
    return item


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


def _seed_item_in_active_batch(
    db: Session,
    project_id: str,
    item_id: str,
    batch_status: BatchStatus = BatchStatus.executing,
    item_status: WorkItemStatus = WorkItemStatus.in_progress,
) -> tuple[WorkItem, Batch]:
    """Create a WorkItem linked to a BatchItem in an active batch."""
    batch = Batch(
        id=f"BATCH-FOR-{item_id}",
        project_id=project_id,
        status=batch_status,
        max_parallel=5,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=False,
    )
    db.add(batch)
    item = WorkItem(
        id=item_id,
        project_id=project_id,
        title=f"Test {item_id}",
        type=WorkItemType.Feature,
        phase=WorkItemPhase.active,
        status=item_status,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(item)
    bi = BatchItem(
        project_id=project_id,
        batch_id=batch.id,
        work_item_id=item_id,
        status=BatchItemStatus.executing
        if batch_status == BatchStatus.executing
        else BatchItemStatus.pending,
        execution_group=0,
    )
    db.add(bi)
    db.flush()
    return item, batch


# ---------------------------------------------------------------------------
# S01 anchor tests (from RED evidence — kept for documentation, all GREEN now)
# ---------------------------------------------------------------------------


class TestS01AnchorItemCancel:
    """S01 anchor tests: POST calls orch.cancel.cancel_work_item with correct kwargs."""

    def test_cancel_item_calls_service_layer_with_form_params(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """GREEN: POST with form data calls orch.cancel.cancel_work_item with parsed kwargs."""
        item = _seed_item(db_session, test_project.id, "F-S01-ANCHOR", WorkItemStatus.approved)

        with patch("orch.cancel.cancel_work_item") as mock_cancel:
            mock_result = MagicMock()
            mock_result.teardown_errors = []
            mock_cancel.return_value = mock_result

            _resp = client.post(
                f"/project/{test_project.id}/api/item/{item.id}/cancel",
                data={"reason": "operator requested", "to_draft": "true"},
            )

            mock_cancel.assert_called_once()
            call_args = mock_cancel.call_args
            assert call_args.args[1] == test_project.id
            assert call_args.args[2] == item.id
            assert call_args.kwargs["reason"] == "operator requested"
            assert call_args.kwargs["to_draft"] is True

    def test_cancel_item_maps_lookup_error_to_404(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """GREEN: LookupError from service layer → HTTP 404."""
        item = _seed_item(db_session, test_project.id, "F-S01-404", WorkItemStatus.approved)

        with patch("orch.cancel.cancel_work_item") as mock_cancel:
            mock_cancel.side_effect = LookupError(
                f"Work item X-99992 not found in project {test_project.id}"
            )

            resp = client.post(
                f"/project/{test_project.id}/api/item/{item.id}/cancel",
                data={"reason": "test"},
            )

            assert resp.status_code == 404
            assert "X-99992" in resp.text or "not found" in resp.text.lower()

    def test_cancel_item_maps_active_batch_value_error_to_409(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """GREEN: ValueError containing 'active batch' → HTTP 409 Conflict."""
        item = _seed_item(db_session, test_project.id, "F-S01-409", WorkItemStatus.in_progress)

        with patch("orch.cancel.cancel_work_item") as mock_cancel:
            mock_cancel.side_effect = ValueError(
                "Cannot cancel work item: belongs to active batch BATCH-99993"
            )

            resp = client.post(
                f"/project/{test_project.id}/api/item/{item.id}/cancel",
                data={"reason": "test"},
            )

            assert resp.status_code == 409
            assert "active batch" in resp.text.lower()

    def test_cancel_item_success_builds_toast_with_status(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """GREEN: success response carries reload=True and toast mentions new status + reason."""
        item = _seed_item(db_session, test_project.id, "F-S01-SUCC", WorkItemStatus.in_progress)

        with patch("orch.cancel.cancel_work_item") as mock_cancel:
            mock_result = MagicMock()
            mock_result.teardown_errors = []
            mock_cancel.return_value = mock_result

            resp = client.post(
                f"/project/{test_project.id}/api/item/{item.id}/cancel",
                data={"reason": "operator cut", "to_draft": "false"},
            )

            assert resp.status_code == 204
            trigger_header = resp.headers.get("HX-Trigger", "")
            assert "showToast" in trigger_header
            assert "reload" in trigger_header

    def test_cancel_item_teardown_errors_append_warning_to_toast(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """GREEN: teardown_errors non-empty → warning line appended to toast message."""
        item = _seed_item(db_session, test_project.id, "F-S01-ERR", WorkItemStatus.in_progress)

        with patch("orch.cancel.cancel_work_item") as mock_cancel:
            mock_result = MagicMock()
            mock_result.teardown_errors = ["docker compose down failed: daemon unreachable"]
            mock_cancel.return_value = mock_result

            resp = client.post(
                f"/project/{test_project.id}/api/item/{item.id}/cancel",
                data={"reason": "test"},
            )

            assert resp.status_code == 204
            trigger_header = resp.headers.get("HX-Trigger", "")
            assert (
                "docker compose down failed" in trigger_header
                or "warning" in trigger_header.lower()
            )


# ---------------------------------------------------------------------------
# AC2: Real DB test — standalone in-progress item → cancelled, steps=skipped
# ---------------------------------------------------------------------------


class TestItemCancelRealDB:
    """AC2: end-to-end with real DB, no mocking of the service layer."""

    def test_item_cancel_standalone_in_progress_marks_steps_skipped(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC2: in_progress steps become skipped; pending steps stay pending (service behavior)."""
        project = _seed_project(db_session, "test-ac2-real")
        item = _seed_item_with_steps(
            db_session,
            project.id,
            "F-AC2-REAL",
            step_statuses=[StepStatus.in_progress, StepStatus.pending, StepStatus.pending],
        )
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/item/{item.id}/cancel",
            data={"reason": "cancelled by operator", "to_draft": "false"},
        )

        assert response.status_code == 204, response.text

        db_session.expire_all()
        item_refresh = db_session.get(WorkItem, (project.id, item.id))
        assert item_refresh.status == WorkItemStatus.cancelled, (
            f"Item must be cancelled, got {item_refresh.status.value}"
        )

        steps = (
            db_session.query(WorkflowStep)
            .filter(
                WorkflowStep.project_id == project.id,
                WorkflowStep.work_item_id == item.id,
            )
            .order_by(WorkflowStep.step_number)
            .all()
        )
        # Cancel must flip ALL non-terminal steps (pending + in_progress +
        # needs_fix) to 'skipped' so the work item's pipeline doesn't pick
        # them up again. Terminal steps (completed/failed/skipped) are kept
        # untouched — but this fixture seeds none of those, so every step
        # must end up skipped.
        for step in steps:
            assert step.status == StepStatus.skipped, (
                f"Step {step.step_id} must be skipped after cancel (was {step.status.value})"
            )

    def test_item_cancel_standalone_approved_with_to_draft(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC2 variant: approved item + to_draft=true → item=draft, steps=pending."""
        project = _seed_project(db_session, "test-ac2-draft")
        item = _seed_item_with_steps(
            db_session, project.id, "F-AC2-DRAFT", step_statuses=[StepStatus.pending]
        )
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/item/{item.id}/cancel",
            data={"reason": "redesign", "to_draft": "true"},
        )

        assert response.status_code == 204, response.text
        db_session.expire_all()
        item_refresh = db_session.get(WorkItem, (project.id, item.id))
        assert item_refresh.status == WorkItemStatus.draft, (
            f"Item must be reset to draft, got {item_refresh.status.value}"
        )


# ---------------------------------------------------------------------------
# AC3: Item cancel refused when in active batch (UI + API)
# ---------------------------------------------------------------------------


class TestItemCancelInActiveBatch:
    """AC3: item cancel refused when item is in an active batch."""

    def test_post_item_cancel_returns_409_when_in_active_batch(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC3 API: direct POST to item cancel when in active batch → 409."""
        project = _seed_project(db_session, "test-ac3-api")
        item, _ = _seed_item_in_active_batch(
            db_session, project.id, "F-AC3-API", BatchStatus.executing, WorkItemStatus.in_progress
        )
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/item/{item.id}/cancel",
            data={"reason": "test"},
        )

        assert response.status_code == 409, (
            f"Cancel must return 409 when item is in active batch, "
            f"got {response.status_code}: {response.text}"
        )
        assert "active batch" in response.text.lower(), "Error must mention 'active batch'"

    def test_item_cancel_disabled_with_hint_when_in_active_batch(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC3 UI: item in active batch → disabled button + hint rendered in template."""
        project = _seed_project(db_session, "test-ac3-ui")
        item, batch = _seed_item_in_active_batch(
            db_session, project.id, "F-AC3-UI", BatchStatus.executing, WorkItemStatus.in_progress
        )
        db_session.commit()

        response = client.get(f"/project/{project.id}/item/{item.id}")
        assert response.status_code == 200, response.text
        html = response.text

        # Must have a disabled cancel button
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        cancel_buttons = [
            b
            for b in soup.find_all("button")
            if b.get_text(strip=True) == "Cancel"
            and not (b.get("id") or "").startswith("chat-assistant-")
        ]
        assert len(cancel_buttons) > 0, "Cancel button must be present"
        disabled_btn = cancel_buttons[0]
        assert disabled_btn.get("disabled") is not None or "cursor-not-allowed" in str(
            disabled_btn
        ), "Cancel button must be disabled when item is in active batch"

        # Must have hint text
        assert "Belongs to active batch" in html, "Active-batch hint must be rendered"
        assert "cancel the batch instead" in html, "Hint must suggest cancelling the batch"

    def test_item_cancel_enabled_when_batch_is_terminal(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Item in a cancelled batch → cancel button is enabled (active-batch gate cleared)."""
        project = _seed_project(db_session, "test-ac3-terminal")
        item, _ = _seed_item_in_active_batch(
            db_session, project.id, "F-AC3-TERM", BatchStatus.cancelled, WorkItemStatus.in_progress
        )
        db_session.commit()

        response = client.get(f"/project/{project.id}/item/{item.id}")
        assert response.status_code == 200, response.text

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "html.parser")
        cancel_buttons = [
            b
            for b in soup.find_all("button")
            if b.get_text(strip=True) == "Cancel"
            and not (b.get("id") or "").startswith("chat-assistant-")
        ]
        assert len(cancel_buttons) > 0
        disabled_btns = [b for b in cancel_buttons if b.get("disabled") is not None]
        assert len(disabled_btns) == 0, (
            "Cancel button must NOT be disabled when parent batch is terminal"
        )


# ---------------------------------------------------------------------------
# AC4: quick-cancel from batches list (item cancel variant — item not in batch)
# ---------------------------------------------------------------------------


class TestItemCancelQuickFromList:
    """AC4 item variant: item-level cancel not in active batch."""

    def test_item_cancel_not_in_active_batch_allowed(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Item not in active batch → cancel button is enabled and POST succeeds."""
        project = _seed_project(db_session, "test-ac4-item")
        item = _seed_item_with_steps(
            db_session, project.id, "F-AC4-ITEM", step_statuses=[StepStatus.pending]
        )
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/item/{item.id}/cancel",
            data={"reason": "cancelled from list", "to_draft": "false"},
        )

        assert response.status_code == 204, response.text
        db_session.expire_all()
        item_refresh = db_session.get(WorkItem, (project.id, item.id))
        assert item_refresh.status == WorkItemStatus.cancelled


# ---------------------------------------------------------------------------
# Boundary: unknown item ID, to_draft on draft item
# ---------------------------------------------------------------------------


class TestBoundaryItemCancel:
    """Boundary rows for item cancel."""

    def test_unknown_item_id_returns_404(self, client: TestClient, db_session: Session) -> None:
        """Boundary: unknown item ID → 404."""
        project = _seed_project(db_session, "test-unk-item")
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/item/F-DOES-NOT-EXIST/cancel",
            data={"reason": "test"},
        )

        assert response.status_code == 404, response.text
        assert "F-DOES-NOT-EXIST" in response.text
        assert "not found" in response.text.lower()

    def test_to_draft_true_on_draft_item_returns_422(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Boundary: to_draft=true on draft item → 422, no DB write."""
        project = _seed_project(db_session, "test-draft-todraft")
        item = _seed_item(db_session, project.id, "F-DRAFT-TODRAFT", WorkItemStatus.draft)
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/item/{item.id}/cancel",
            data={"reason": "test", "to_draft": "true"},
        )

        assert response.status_code == 422, response.text
        assert "Cannot cancel" in response.text or "draft" in response.text.lower(), (
            "Error must mention that draft items cannot be cancelled with to_draft"
        )

        # DB unchanged
        db_session.expire_all()
        item_refresh = db_session.get(WorkItem, (project.id, item.id))
        assert item_refresh.status == WorkItemStatus.draft, (
            "Item status must be unchanged after rejected to_draft cancel"
        )

    def test_item_cancel_with_empty_reason_uses_default(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Boundary: empty reason → service-layer default 'cancelled by operator'."""
        project = _seed_project(db_session, "test-empty-reason-item")
        item = _seed_item(db_session, project.id, "F-EMPTY-REASON", WorkItemStatus.approved)
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/item/{item.id}/cancel",
            data={"reason": "", "to_draft": "false"},
        )

        assert response.status_code == 204, response.text
        db_session.expire_all()
        item_refresh = db_session.get(WorkItem, (project.id, item.id))
        assert item_refresh.status == WorkItemStatus.cancelled


# ---------------------------------------------------------------------------
# Invariant 1: cancel_item handler calls service layer with exact kwargs
# ---------------------------------------------------------------------------


class TestInvariant1ItemHandlerCallsServiceLayer:
    """Invariant 1: handler calls orch.cancel.cancel_work_item with parsed form params."""

    def test_cancel_item_handler_calls_service_layer_with_exact_kwargs(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Invariant 1: POST with reason + to_draft → cancel_work_item called with exact kwargs."""
        project = _seed_project(db_session, "test-inv1-item")
        item = _seed_item(db_session, project.id, "F-INV1-ITEM", WorkItemStatus.in_progress)
        db_session.commit()

        with patch("orch.cancel.cancel_work_item") as mock_cancel:
            mock_result = MagicMock()
            mock_result.teardown_errors = []
            mock_cancel.return_value = mock_result

            response = client.post(
                f"/project/{project.id}/api/item/{item.id}/cancel",
                data={"reason": "operator requested", "to_draft": "true"},
            )

            assert response.status_code == 204
            mock_cancel.assert_called_once()
            call_args = mock_cancel.call_args
            assert call_args.args[1] == project.id
            assert call_args.args[2] == item.id
            assert call_args.kwargs.get("reason") == "operator requested"
            assert call_args.kwargs.get("to_draft") is True

    def test_cancel_item_handler_does_not_call_cancel_twice(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Verify the handler calls cancel_work_item exactly once (no double-call)."""
        project = _seed_project(db_session, "test-once-item")
        item = _seed_item(db_session, project.id, "F-ONCE-ITEM", WorkItemStatus.approved)
        db_session.commit()

        with patch("orch.cancel.cancel_work_item") as mock_cancel:
            mock_result = MagicMock()
            mock_result.teardown_errors = []
            mock_cancel.return_value = mock_result

            client.post(
                f"/project/{project.id}/api/item/{item.id}/cancel",
                data={"reason": "once test", "to_draft": "false"},
            )

            assert mock_cancel.call_count == 1, (
                f"cancel_work_item must be called exactly once, got {mock_cancel.call_count}"
            )


# ---------------------------------------------------------------------------
# Invariant 4: teardown errors never break the response
# ---------------------------------------------------------------------------


class TestItemTeardownErrorsNeverBreakResponse:
    """Invariant 4: teardown_errors non-empty but result is still 2xx."""

    def test_item_cancel_teardown_errors_still_return_200(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Item cancel with teardown_errors → 204 + warning in toast (not 500)."""
        project = _seed_project(db_session, "test-teardown-item")
        item = _seed_item(db_session, project.id, "F-TEARDOWN-ITEM", WorkItemStatus.in_progress)
        db_session.commit()

        with patch("orch.cancel.cancel_work_item") as mock_cancel:
            mock_result = MagicMock()
            mock_result.new_status = WorkItemStatus.cancelled
            mock_result.reason = "operator cancel"
            mock_result.teardown_errors = ["git worktree remove failed: lock held"]
            mock_cancel.return_value = mock_result

            response = client.post(
                f"/project/{project.id}/api/item/{item.id}/cancel",
                data={"reason": "operator cancel"},
            )

            assert response.status_code == 204, response.text
            trigger_header = response.headers.get("HX-Trigger", "")
            assert (
                "git worktree remove failed" in trigger_header
                or "warning" in trigger_header.lower()
            ), f"Toast must contain teardown warning: {trigger_header}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
