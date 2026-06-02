"""AC4: GET /project/{project_id}/api/confirm-item/restart-setup/{item_id} confirm dialog.

The confirm dialog is served by the generic `confirm_item_dialog` dispatcher,
which reads from `_ITEM_ACTION_LABELS["restart-setup"]`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
# Tests: confirm dialog
# ---------------------------------------------------------------------------


class TestRestartSetupConfirmDialog:
    """AC4: confirm dialog returns expected HTML fragment."""

    def _setup_item(self, db_session: Session, test_project: Project, item_id: str) -> None:
        """Create a minimal setup-failed scenario for the dialog to render."""
        work_item = WorkItem(
            id=item_id,
            project_id=test_project.id,
            type=WorkItemType.Issue,
            title="CR-00029 Dialog Test",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(work_item)

        batch = Batch(
            id=f"CR00029-batch-dialog-{item_id}",
            project_id=test_project.id,
            status=BatchStatus.approved,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            work_item_id=item_id,
            batch_id=f"CR00029-batch-dialog-{item_id}",
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

    def test_confirm_dialog_returns_html_with_expected_text(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """GET returns HTML with the expected title and description."""
        item_id = "CR00029-confirm-dialog"
        self._setup_item(db_session, test_project, item_id)

        resp = client.get(f"/project/{test_project.id}/api/confirm-item/restart-setup/{item_id}")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

        html = resp.text

        # Title format: f"Restart setup {item_id}?" (dispatcher uses
        # f"{title.rstrip('?')} {item_id}?")
        assert f"Restart setup {item_id}?" in html

        # Description from _ITEM_ACTION_LABELS["restart-setup"]
        assert "This deletes the worktree and resets every step" in html
        assert "The daemon will re-run setup from scratch" in html

    def test_confirm_dialog_targets_post_endpoint(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """The dialog's confirm button POSTs to the restart_setup endpoint."""
        item_id = "CR00029-confirm-post"
        self._setup_item(db_session, test_project, item_id)

        resp = client.get(f"/project/{test_project.id}/api/confirm-item/restart-setup/{item_id}")
        assert resp.status_code == 200
        html = resp.text

        # The confirm button should POST to the restart_setup endpoint
        expected_post_url = f"/project/{test_project.id}/api/item/{item_id}/restart-setup"
        assert expected_post_url in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
