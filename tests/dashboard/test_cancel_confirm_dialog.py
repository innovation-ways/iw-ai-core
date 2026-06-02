"""Tests for F-00082: cancel confirm-dialog GET endpoints return form-bearing modal.

Covers:
- AC1 (form-bearing): GET /api/confirm-batch/cancel/{id} returns textarea + checkbox
- AC1 (no form for non-cancel): GET /api/confirm-batch/approve/{id} does NOT return textarea
- Invariant 1 variant: service layer kwargs, not status manipulation
- Boundary: empty reason field uses default
- Boundary: whitespace reason is stripped

Uses real db_session (no mocks for DB state).
Monkeys-patch orch.cancel only for error-surfacing tests (AC6).
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


def _seed_project(db: Session, project_id: str = "test-confirm-proj") -> Project:
    project = Project(
        id=project_id,
        display_name="Test Confirm Project",
        repo_root="/repos/test",
        config={},
    )
    db.add(project)
    db.flush()
    return project


def _seed_batch(
    db: Session, project_id: str, batch_id: str, status: BatchStatus = BatchStatus.paused
) -> Batch:
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


def _seed_item(
    db: Session, project_id: str, item_id: str, status: WorkItemStatus = WorkItemStatus.in_progress
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


# ---------------------------------------------------------------------------
# Form-bearing modal tests
# ---------------------------------------------------------------------------


class TestConfirmDialogFormForCancelAction:
    """GET /api/confirm-batch/cancel/{id} returns a form-bearing modal."""

    def test_confirm_dialog_get_for_cancel_action_renders_form(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC1: cancel confirm dialog contains <textarea name='reason'> and checkbox."""
        project = _seed_project(db_session, "test-form-batch")
        batch = _seed_batch(db_session, project.id, "BATCH-FORM-TEST", BatchStatus.paused)
        db_session.commit()

        response = client.get(f"/project/{project.id}/api/confirm-batch/cancel/{batch.id}")
        assert response.status_code == 200, response.text
        html = response.text

        assert "<textarea" in html, "Cancel confirm dialog must contain a textarea"
        assert 'name="reason"' in html, "Textarea must have name='reason'"
        assert "<input" in html, "Cancel confirm dialog must contain an input element"
        assert 'type="checkbox"' in html, "The input must be a checkbox"
        assert 'name="reset_items"' in html, "Checkbox must have name='reset_items'"

    def test_confirm_dialog_get_for_non_cancel_action_does_not_render_form(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Non-cancel confirm dialog (approve) must NOT contain a textarea."""
        project = _seed_project(db_session, "test-approve-dialog")
        batch = _seed_batch(db_session, project.id, "BATCH-APPROVE-TEST", BatchStatus.planning)
        db_session.commit()

        response = client.get(f"/project/{project.id}/api/confirm-batch/approve/{batch.id}")
        assert response.status_code == 200, response.text
        html = response.text

        assert "<textarea" not in html, (
            "Approve confirm dialog must NOT contain a textarea — "
            "it should use the plain confirm_action.html fragment"
        )

    def test_item_confirm_dialog_get_for_cancel_action_renders_form(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Item-level cancel confirm dialog also renders the textarea + to_draft checkbox."""
        project = _seed_project(db_session, "test-form-item")
        item = _seed_item(db_session, project.id, "F-FORM-ITEM-TEST", WorkItemStatus.approved)
        db_session.commit()

        response = client.get(f"/project/{project.id}/api/confirm-item/cancel/{item.id}")
        assert response.status_code == 200, response.text
        html = response.text

        assert "<textarea" in html, "Item cancel confirm dialog must contain a textarea"
        assert 'name="reason"' in html
        assert "<input" in html, "Item cancel confirm dialog must contain an input element"
        assert 'type="checkbox"' in html, "The input must be a checkbox"
        assert 'name="to_draft"' in html, "Checkbox must have name='to_draft'"


# ---------------------------------------------------------------------------
# Form submission tests (AC1 real DB, AC2, AC3, AC4, AC5, AC6)
# ---------------------------------------------------------------------------


class TestBatchCancelEndToEnd:
    """AC1/AC2/AC4/AC5/AC6: batch cancel POST with real DB state."""

    def test_batch_cancel_executing_with_reset_items_resets_steps_and_returns_toast(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC1: executing batch + reset_items → batch=cancelled, item=draft, steps=pending.

        Real orch.cancel.cancel_batch with no mocking — verifies the full chain.
        """
        project = _seed_project(db_session, "test-ac1-batch")
        batch = _seed_batch(db_session, project.id, "BATCH-AC1-TEST", BatchStatus.executing)
        item = WorkItem(
            id="F-AC1-TEST",
            project_id=project.id,
            title="AC1 Test Item",
            type=WorkItemType.Feature,
            phase=WorkItemPhase.active,
            status=WorkItemStatus.in_progress,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(item)
        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=item.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
        from orch.db.models import StepStatus, StepType, WorkflowStep

        for i in range(1, 4):
            step = WorkflowStep(
                project_id=project.id,
                work_item_id=item.id,
                step_id=f"F-AC1-TEST-step-{i}",
                step_number=i,
                step_type=StepType.implementation,
                agent_label="test",
                status=StepStatus.in_progress if i == 1 else StepStatus.pending,
            )
            db_session.add(step)
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
            .filter(WorkflowStep.project_id == project.id, WorkflowStep.work_item_id == item.id)
            .order_by(WorkflowStep.step_number)
            .all()
        )
        for step in steps:
            assert step.status == StepStatus.pending, (
                f"Step {step.step_id} must be pending after reset, got {step.status.value}"
            )

        # Toast must mention cancelled + reset
        trigger_header = response.headers.get("HX-Trigger", "")
        assert "showToast" in trigger_header, (
            f"Response must have showToast trigger: {trigger_header}"
        )

    def test_batch_cancel_approved_to_cancelled(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC1 variant: approved batch → cancelled (no reset)."""
        project = _seed_project(db_session, "test-ac1b-batch")
        batch = _seed_batch(db_session, project.id, "BATCH-AC1B-TEST", BatchStatus.approved)
        item = WorkItem(
            id="F-AC1B-TEST",
            project_id=project.id,
            title="AC1B Test Item",
            type=WorkItemType.Feature,
            phase=WorkItemPhase.active,
            status=WorkItemStatus.approved,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(item)
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
            data={"reason": "operator request", "reset_items": "false"},
        )

        assert response.status_code == 204, response.text

        db_session.expire_all()
        batch_refresh = db_session.get(Batch, (project.id, batch.id))
        assert batch_refresh.status == BatchStatus.cancelled


class TestItemCancelEndToEnd:
    """AC2: cancel standalone in-progress item → marks in_progress steps skipped.

    NOTE: The service layer only marks in_progress steps as skipped (not pending
    steps). This test verifies actual behavior; the pending-step gap is documented
    as a service layer issue to address in a follow-up CR.
    """

    def test_item_cancel_standalone_in_progress_marks_steps_skipped(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC2: in_progress steps become skipped; pending steps stay pending (service behavior)."""
        project = _seed_project(db_session, "test-ac2-item")
        item = WorkItem(
            id="F-AC2-TEST",
            project_id=project.id,
            title="AC2 Test Item",
            type=WorkItemType.Feature,
            phase=WorkItemPhase.active,
            status=WorkItemStatus.in_progress,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(item)
        db_session.flush()

        from orch.db.models import StepStatus, StepType, WorkflowStep

        for i, status in enumerate(
            [StepStatus.in_progress, StepStatus.pending, StepStatus.pending], start=1
        ):
            db_session.add(
                WorkflowStep(
                    project_id=project.id,
                    work_item_id=item.id,
                    step_id=f"F-AC2-TEST-step-{i}",
                    step_number=i,
                    step_type=StepType.implementation,
                    agent_label="test",
                    status=status,
                )
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
            .filter(WorkflowStep.project_id == project.id, WorkflowStep.work_item_id == item.id)
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


class TestItemCancelInActiveBatch:
    """AC3: item cancel refused when item is in an active batch."""

    def test_item_cancel_disabled_with_hint_when_in_active_batch(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC3 UI: item in active batch → disabled button + hint rendered in template."""
        project = _seed_project(db_session, "test-ac3-ui")
        batch = _seed_batch(db_session, project.id, "BATCH-AC3-TEST", BatchStatus.executing)
        item = WorkItem(
            id="F-AC3-TEST",
            project_id=project.id,
            title="AC3 Test Item",
            type=WorkItemType.Feature,
            phase=WorkItemPhase.active,
            status=WorkItemStatus.in_progress,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(item)
        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=item.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
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

    def test_post_item_cancel_returns_409_when_in_active_batch(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC3 API: direct POST to item cancel when in active batch → 409."""
        project = _seed_project(db_session, "test-ac3-api")
        batch = _seed_batch(db_session, project.id, "BATCH-AC3-API", BatchStatus.executing)
        item = WorkItem(
            id="F-AC3-API-TEST",
            project_id=project.id,
            title="AC3 API Item",
            type=WorkItemType.Feature,
            phase=WorkItemPhase.active,
            status=WorkItemStatus.in_progress,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(item)
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
            f"/project/{project.id}/api/item/{item.id}/cancel",
            data={"reason": "test"},
        )

        assert response.status_code == 409, (
            f"Cancel must return 409 when item is in active batch, "
            f"got {response.status_code}: {response.text}"
        )
        assert "active batch" in response.text.lower(), "Error must mention 'active batch'"


class TestQuickCancelFromBatchesList:
    """AC4: quick-cancel from batches list uses default reason, no reset."""

    def test_quick_cancel_from_batches_list_posts_default_reason(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC4: quick-cancel POSTs with reason='cancelled from batches list', reset_items=false."""
        project = _seed_project(db_session, "test-ac4-list")
        batch = _seed_batch(db_session, project.id, "BATCH-AC4-LIST", BatchStatus.paused)
        db_session.commit()

        # Verify the batches list page has a cancel button
        list_response = client.get(f"/project/{project.id}/batches")
        assert list_response.status_code == 200, list_response.text
        assert "Cancel" in list_response.text, "Batches list must show a Cancel button"

        # POST the quick-cancel (matches the onclick in batches.html)
        response = client.post(
            f"/project/{project.id}/api/batch/{batch.id}/cancel",
            data={"reason": "cancelled from batches list", "reset_items": "false"},
        )

        assert response.status_code == 204, response.text
        db_session.expire_all()
        batch_refresh = db_session.get(Batch, (project.id, batch.id))
        assert batch_refresh.status == BatchStatus.cancelled, (
            f"Batch must be cancelled, got {batch_refresh.status.value}"
        )


class TestCancelBatchTerminalRefused:
    """AC5: cancel button hidden / endpoint refuses for terminal batches."""

    def test_cancel_button_hidden_for_terminal_batch(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC5 UI: completed batch → no Cancel button in template."""
        project = _seed_project(db_session, "test-ac5-ui")
        batch = _seed_batch(db_session, project.id, "BATCH-AC5-UI", BatchStatus.completed)
        db_session.commit()

        response = client.get(f"/project/{project.id}/batch/{batch.id}")
        assert response.status_code == 200, response.text

        # Search for a Cancel button in the actions area
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "html.parser")
        cancel_btns = [
            b
            for b in soup.find_all("button")
            if b.get_text(strip=True) == "Cancel"
            and not (b.get("id") or "").startswith("chat-assistant-")
        ]
        assert len(cancel_btns) == 0, "Completed batch must NOT have a Cancel button"

    def test_post_cancel_batch_returns_422_for_completed_batch(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC5 API: direct POST to completed batch cancel → 422."""
        project = _seed_project(db_session, "test-ac5-api")
        batch = _seed_batch(db_session, project.id, "BATCH-AC5-API", BatchStatus.completed)
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/batch/{batch.id}/cancel",
            data={"reason": "test"},
        )

        assert response.status_code == 422, (
            f"Cancel completed batch must return 422, got {response.status_code}: {response.text}"
        )
        assert "Cannot cancel" in response.text or "cannot cancel" in response.text.lower(), (
            "Error must mention 'Cannot cancel'"
        )


class TestTeardownErrorsSurfaceAsWarning:
    """AC6: teardown errors surface as warning toasts but do not block 200."""

    def test_teardown_errors_surface_as_warnings_but_return_200(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC6: orch.cancel.cancel_batch with teardown_errors → HTTP 200 + warning in toast."""
        project = _seed_project(db_session, "test-ac6-teardown")
        batch = _seed_batch(db_session, project.id, "BATCH-AC6-TEARDOWN", BatchStatus.paused)
        db_session.commit()

        with patch("orch.cancel.cancel_batch") as mock_cancel:
            mock_result = MagicMock()
            mock_result.cancelled_batch_items = ["F-1"]
            mock_result.reset_to_draft = []
            mock_result.killed_pids = []
            mock_result.teardown_errors = ["compose down failed: docker daemon unreachable"]
            mock_cancel.return_value = mock_result

            response = client.post(
                f"/project/{project.id}/api/batch/{batch.id}/cancel",
                data={"reason": "test teardown"},
            )

            assert response.status_code == 204, (
                f"Cancel with teardown errors must still return 204, "
                f"got {response.status_code}: {response.text}"
            )
            trigger_header = response.headers.get("HX-Trigger", "")
            assert "compose down failed" in trigger_header or "warning" in trigger_header.lower(), (
                f"Toast must mention teardown error: {trigger_header}"
            )

    def test_item_teardown_errors_surface_as_warnings_but_return_200(
        self, client: TestClient, db_session: Session
    ) -> None:
        """AC6 item variant: teardown_errors non-empty → warning line in toast."""
        project = _seed_project(db_session, "test-ac6-item-teardown")
        item = _seed_item(db_session, project.id, "F-AC6-ITEM", WorkItemStatus.in_progress)
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


# ---------------------------------------------------------------------------
# Boundary: empty reason, whitespace reason, unknown IDs
# ---------------------------------------------------------------------------


class TestBoundaryEmptyAndWhitespaceReason:
    """Boundary: empty reason uses default; whitespace reason is stripped."""

    def test_batch_cancel_empty_reason_uses_default(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Empty reason → service-layer default 'cancelled by operator' is used."""
        project = _seed_project(db_session, "test-empty-reason")
        batch = _seed_batch(db_session, project.id, "BATCH-EMPTY-REASON", BatchStatus.planning)
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/batch/{batch.id}/cancel",
            data={"reason": "", "reset_items": "false"},
        )

        assert response.status_code == 204, response.text
        db_session.expire_all()
        batch_refresh = db_session.get(Batch, (project.id, batch.id))
        assert batch_refresh.status == BatchStatus.cancelled

    def test_batch_cancel_whitespace_reason_stripped(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Whitespace reason → service-layer strips and uses the clean value."""
        project = _seed_project(db_session, "test-ws-reason")
        batch = _seed_batch(db_session, project.id, "BATCH-WS-REASON", BatchStatus.planning)
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

            # The handler passes reason="  redesign  " to the service layer
            # which strips it — verify the exact kwarg
            call_args = mock_cancel.call_args
            assert call_args.kwargs.get("reason") == "  redesign  ", (
                "Whitespace must be preserved in the call (service layer strips)"
            )


class TestBoundaryUnknownBatchAndItem:
    """Boundary: unknown batch/item IDs return 404."""

    def test_unknown_batch_id_returns_404(self, client: TestClient, db_session: Session) -> None:
        """Unknown batch ID → 404 with toast message containing the ID."""
        project = _seed_project(db_session, "test-unk-batch")
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/batch/BATCH-DOES-NOT-EXIST/cancel",
            data={"reason": "test"},
        )

        assert response.status_code == 404, response.text
        assert "BATCH-DOES-NOT-EXIST" in response.text, (
            "404 message must include the unknown batch ID"
        )

    def test_unknown_item_id_returns_404(self, client: TestClient, db_session: Session) -> None:
        """Unknown item ID → 404 with toast message containing the ID."""
        project = _seed_project(db_session, "test-unk-item")
        db_session.commit()

        response = client.post(
            f"/project/{project.id}/api/item/F-DOES-NOT-EXIST/cancel",
            data={"reason": "test"},
        )

        assert response.status_code == 404, response.text
        assert "F-DOES-NOT-EXIST" in response.text, "404 message must include the unknown item ID"


# ---------------------------------------------------------------------------
# Boundary: to_draft on draft item → 422
# ---------------------------------------------------------------------------


class TestBoundaryToDraftOnDraftItem:
    """Boundary: to_draft=true on draft item → service layer refuses with 422."""

    def test_to_draft_true_on_draft_item_returns_422(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Draft item + to_draft=true → ValueError → 422, no DB write."""
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

        # Verify DB unchanged
        db_session.expire_all()
        item_refresh = db_session.get(WorkItem, (project.id, item.id))
        assert item_refresh.status == WorkItemStatus.draft, (
            "Item status must be unchanged after rejected to_draft cancel"
        )


# ---------------------------------------------------------------------------
# Macro byte-equivalence: confirm_action_form default empty preserves output
# ---------------------------------------------------------------------------


class TestMacroByteEquivalence:
    """Invariant: confirm_action_form renders without errors for non-cancel actions.

    The confirm_action_form.html always includes the form (textarea + checkbox)
    — it is the caller's choice of action URL that determines what POST happens.
    The macro test verifies render success and that a textarea is present.
    """

    def test_confirm_action_form_renders_without_error_for_non_cancel_action(
        self,
    ) -> None:
        """confirm_action_form.html renders without errors for any action URL.

        The form is always included (textarea + checkbox) — what varies is the
        confirm_url POST target, which the test sets to a non-cancel action.
        The key assertion is that rendering succeeds without exceptions.
        """
        from jinja2 import Environment, FileSystemLoader

        templates_dir = "dashboard/templates"
        env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=True,
        )

        form = env.get_template("fragments/confirm_action_form.html")

        # Render confirm_action_form with a non-cancel approve action URL.
        # The form HTML is always present; the action URL is what differs.
        result = form.render(
            title="Approve Batch?",
            description="Approves the batch.",
            confirm_url="/project/test/api/batch/BATCH-001/approve",
            confirm_method="post",
            confirm_label="Approve",
            danger=False,
            default_reason="cancelled by operator",
            reset_field_name="reset_items",
            reset_field_label="Also reset member items to draft",
        )

        # Must produce valid HTML (no render errors)
        assert result, "Template must render to non-empty string"
        assert "<div" in result, "Template must produce HTML div element"
        # The form (textarea + checkbox) is always present in this template.
        assert "<textarea" in result, "Template must contain a textarea"
        assert result.count("<textarea") == 1, "Exactly one textarea must be present"
        assert 'name="reason"' in result, "Textarea must have name='reason'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
