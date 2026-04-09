"""Integration tests for batch archive — end-to-end with a real PostgreSQL testcontainer.

Tests verify the archive flow through the HTTP API layer:
- Archive endpoint validates status and returns correct HTTP codes
- Invalid status returns 422
- Non-existent batch returns 404
- Confirm dialog returns proper HTML fragment
- Synchronous batch_archiving event emission

Note: Testing the full background archive completion (batch_archived event
emitted by background thread) requires complex SessionLocal patching that
conflicts with FastAPI TestClient's threading model. The background thread
behavior is thoroughly tested in unit tests with proper mocking.
"""

from __future__ import annotations

from pathlib import Path
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """A temporary directory to serve as a project repo root."""
    return tmp_path / "repo"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    session: Session,
    project_id: str = "test-proj",
    config: dict | None = None,
    repo_root: Path | None = None,
) -> Project:
    if repo_root is None:
        repo_root = Path("/tmp/fallback-test-repo")  # noqa: S108
    project = Project(
        id=project_id,
        display_name=f"Test Project {project_id}",
        repo_root=str(repo_root),
        config=config or {},
    )
    session.add(project)
    session.flush()
    return project


def _make_work_item(
    session: Session,
    project_id: str,
    item_id: str,
    title: str = "Test Feature",
    status: WorkItemStatus = WorkItemStatus.completed,
    phase: WorkItemPhase = WorkItemPhase.active,
) -> WorkItem:
    wi = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Feature,
        title=title,
        status=status,
        phase=phase,
        config={},
        depends_on=[],
        blocks=[],
    )
    session.add(wi)
    session.flush()
    return wi


def _make_batch(
    session: Session,
    project_id: str,
    batch_id: str,
    status: BatchStatus = BatchStatus.completed,
) -> Batch:
    batch = Batch(
        project_id=project_id,
        id=batch_id,
        status=status,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
    )
    session.add(batch)
    session.flush()
    return batch


def _make_batch_item(
    session: Session,
    project_id: str,
    batch_id: str,
    work_item_id: str,
    status: BatchItemStatus = BatchItemStatus.merged,
) -> BatchItem:
    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=work_item_id,
        status=status,
        execution_group=0,
    )
    session.add(bi)
    session.flush()
    return bi


def _create_test_app(db_session: Session):
    """Build a FastAPI app that uses the test db session for all requests."""
    app = create_app()

    def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestArchiveBatchEndpoint:
    """Test the POST /project/{project_id}/api/batch/{batch_id}/archive endpoint."""

    def test_archive_completed_batch_returns_204(
        self,
        db_session: Session,
    ) -> None:
        """Archive endpoint returns 204 immediately (archive runs in background)."""
        project = _make_project(db_session, config={})
        batch = _make_batch(db_session, project.id, "BATCH-00001", BatchStatus.completed)
        _make_work_item(db_session, project.id, "F-00001")
        _make_batch_item(db_session, project.id, batch.id, "F-00001", BatchItemStatus.merged)
        db_session.commit()

        app = _create_test_app(db_session)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            f"/project/{project.id}/api/batch/{batch.id}/archive",
        )

        assert response.status_code == 204
        assert "HX-Trigger" in response.headers

    def test_archive_completed_batch_emits_batch_archiving_event(
        self,
        db_session: Session,
    ) -> None:
        """Endpoint emits batch_archiving event synchronously before background starts."""
        project = _make_project(db_session, config={})
        batch = _make_batch(db_session, project.id, "BATCH-00001", BatchStatus.completed)
        _make_work_item(db_session, project.id, "F-00001")
        _make_batch_item(db_session, project.id, batch.id, "F-00001", BatchItemStatus.merged)
        db_session.commit()

        app = _create_test_app(db_session)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            f"/project/{project.id}/api/batch/{batch.id}/archive",
        )
        assert response.status_code == 204

        # batch_archiving is committed synchronously before background thread starts
        db_session.expire_all()
        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.event_type == "batch_archiving",
                DaemonEvent.entity_id == batch.id,
            )
        )
        assert event is not None
        assert event.project_id == project.id

    def test_archive_batch_invalid_status_returns_422(
        self,
        db_session: Session,
    ) -> None:
        """Archive endpoint returns 422 for non-terminal batch status (executing)."""
        project = _make_project(db_session, config={})
        batch = _make_batch(db_session, project.id, "BATCH-00001", BatchStatus.executing)
        db_session.commit()

        app = _create_test_app(db_session)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            f"/project/{project.id}/api/batch/{batch.id}/archive",
        )

        assert response.status_code == 422

    def test_archive_batch_planning_status_returns_422(
        self,
        db_session: Session,
    ) -> None:
        """Archive endpoint returns 422 for planning-status batch."""
        project = _make_project(db_session, config={})
        batch = _make_batch(db_session, project.id, "BATCH-00001", BatchStatus.planning)
        db_session.commit()

        app = _create_test_app(db_session)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            f"/project/{project.id}/api/batch/{batch.id}/archive",
        )

        assert response.status_code == 422

    def test_archive_batch_not_found_returns_404(
        self,
        db_session: Session,
    ) -> None:
        """Archive endpoint returns 404 for non-existent batch."""
        project = _make_project(db_session, config={})
        db_session.commit()

        app = _create_test_app(db_session)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            f"/project/{project.id}/api/batch/NONEXISTENT/archive",
        )

        assert response.status_code == 404

    def test_archive_batch_project_not_found_returns_404(
        self,
        db_session: Session,
    ) -> None:
        """Archive endpoint returns 404 for non-existent project."""
        app = _create_test_app(db_session)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/project/nonexistent/api/batch/BATCH-00001/archive",
        )

        assert response.status_code == 404


class TestArchiveConfirmDialog:
    """Test GET /project/{project_id}/api/confirm-batch/archive/{batch_id}."""

    def test_confirm_dialog_returns_html_fragment(
        self,
        db_session: Session,
    ) -> None:
        """Confirm dialog returns an HTML fragment with Archive button."""
        project = _make_project(db_session, config={})
        batch = _make_batch(db_session, project.id, "BATCH-00001", BatchStatus.completed)
        db_session.commit()

        app = _create_test_app(db_session)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(
            f"/project/{project.id}/api/confirm-batch/archive/{batch.id}",
        )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Archive" in response.text

    def test_confirm_dialog_unknown_action_returns_400(
        self,
        db_session: Session,
    ) -> None:
        """Unknown batch action returns 400."""
        project = _make_project(db_session, config={})
        batch = _make_batch(db_session, project.id, "BATCH-00001", BatchStatus.completed)
        db_session.commit()

        app = _create_test_app(db_session)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(
            f"/project/{project.id}/api/confirm-batch/does-not-exist/{batch.id}",
        )

        assert response.status_code == 400

    def test_confirm_dialog_archived_batch_still_shows_archive(
        self,
        db_session: Session,
    ) -> None:
        """Confirm dialog still works for archived batch (shows Archive button is present)."""
        project = _make_project(db_session, config={})
        batch = _make_batch(db_session, project.id, "BATCH-00001", BatchStatus.archived)
        db_session.commit()

        app = _create_test_app(db_session)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(
            f"/project/{project.id}/api/confirm-batch/archive/{batch.id}",
        )

        # The confirm dialog endpoint doesn't check batch status;
        # the actual archive POST endpoint checks status
        assert response.status_code == 200
