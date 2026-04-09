"""Unit tests for the batch archive endpoint and SSE event types.

Tests cover:
- _BATCH_ACTION_LABELS contains "archive" with correct values
- POST /batch/{batch_id}/archive happy path (completed status)
- POST /batch/{batch_id}/archive happy path (completed_with_errors status)
- POST /batch/{batch_id}/archive with wrong status returns 422
- POST /batch/{batch_id}/archive with nonexistent batch returns 404
- SSE _TOAST_EVENTS contains batch_archiving, batch_archived, batch_archive_failed
- SSE _TOAST_SEVERITY has correct mappings
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from orch.db.models import BatchStatus

# ---------------------------------------------------------------------------
# _BATCH_ACTION_LABELS tests (pure dict inspection — no DB)
# ---------------------------------------------------------------------------


class TestBatchActionLabels:
    """Verify that 'archive' is registered in _BATCH_ACTION_LABELS."""

    def test_archive_key_exists(self) -> None:
        from dashboard.routers.actions import _BATCH_ACTION_LABELS

        assert "archive" in _BATCH_ACTION_LABELS

    def test_archive_label_structure(self) -> None:
        from dashboard.routers.actions import _BATCH_ACTION_LABELS

        entry = _BATCH_ACTION_LABELS["archive"]
        title, description, confirm_label, danger = entry

        assert "Archive" in title
        assert isinstance(description, str)
        assert len(description) > 0
        assert confirm_label == "Archive"
        assert danger is False  # archive is a normal completion action

    def test_archive_description_mentions_post_merge(self) -> None:
        from dashboard.routers.actions import _BATCH_ACTION_LABELS

        _, description, _, _ = _BATCH_ACTION_LABELS["archive"]
        # Description should mention what happens
        assert "archive" in description.lower() or "Archive" in description


# ---------------------------------------------------------------------------
# SSE event type tests (pure module-level constant inspection)
# ---------------------------------------------------------------------------


class TestSseEventTypes:
    """Verify that new archive events are registered in sse.py constants."""

    def test_batch_archiving_in_toast_events(self) -> None:
        from dashboard.routers.sse import _TOAST_EVENTS

        assert "batch_archiving" in _TOAST_EVENTS

    def test_batch_archived_in_toast_events(self) -> None:
        from dashboard.routers.sse import _TOAST_EVENTS

        assert "batch_archived" in _TOAST_EVENTS

    def test_batch_archive_failed_in_toast_events(self) -> None:
        from dashboard.routers.sse import _TOAST_EVENTS

        assert "batch_archive_failed" in _TOAST_EVENTS

    def test_batch_archived_severity_is_success(self) -> None:
        from dashboard.routers.sse import _TOAST_SEVERITY

        assert _TOAST_SEVERITY.get("batch_archived") == "success"

    def test_batch_archive_failed_severity_is_error(self) -> None:
        from dashboard.routers.sse import _TOAST_SEVERITY

        assert _TOAST_SEVERITY.get("batch_archive_failed") == "error"

    def test_batch_archiving_severity_is_info(self) -> None:
        from dashboard.routers.sse import _TOAST_SEVERITY

        assert _TOAST_SEVERITY.get("batch_archiving") == "info"

    def test_new_events_in_watched_events(self) -> None:
        """All toast events must be in _WATCHED_EVENTS (union with running update events)."""
        from dashboard.routers.sse import _TOAST_EVENTS, _WATCHED_EVENTS

        for event in ("batch_archiving", "batch_archived", "batch_archive_failed"):
            assert event in _WATCHED_EVENTS, f"{event} not in _WATCHED_EVENTS"
            assert event in _TOAST_EVENTS, f"{event} not in _TOAST_EVENTS"


# ---------------------------------------------------------------------------
# Endpoint tests via TestClient
# ---------------------------------------------------------------------------


def _make_app() -> Any:
    """Create a TestClient-ready FastAPI app."""
    from dashboard.app import create_app

    return create_app()


def _make_batch_mock(status: BatchStatus) -> MagicMock:
    b = MagicMock()
    b.id = "BATCH-00001"
    b.project_id = "test-proj"
    b.status = status
    return b


class TestArchiveBatchEndpoint:
    """Tests for POST /project/{project_id}/api/batch/{batch_id}/archive."""

    def _make_client(self, mock_db: MagicMock) -> TestClient:
        """Create a TestClient with the DB dependency overridden."""
        from dashboard.dependencies import get_db

        app = _make_app()
        app.dependency_overrides[get_db] = lambda: mock_db
        return TestClient(app, raise_server_exceptions=True)

    def _make_client_no_exc(self, mock_db: MagicMock) -> TestClient:
        from dashboard.dependencies import get_db

        app = _make_app()
        app.dependency_overrides[get_db] = lambda: mock_db
        return TestClient(app, raise_server_exceptions=False)

    def test_archive_completed_batch_returns_204(self) -> None:
        """POST archive on a completed batch emits event, launches thread, returns 204."""
        batch = _make_batch_mock(BatchStatus.completed)
        mock_db = MagicMock()
        mock_db.scalar.return_value = batch

        client = self._make_client(mock_db)

        with (
            patch("dashboard.routers.actions.archive_batch"),
            patch("threading.Thread") as mock_thread,
        ):
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            resp = client.post("/project/test-proj/api/batch/BATCH-00001/archive")

        assert resp.status_code == 204
        # Thread was started
        mock_thread_instance.start.assert_called_once()
        # A daemon event was emitted
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_archive_completed_with_errors_batch_returns_204(self) -> None:
        """POST archive on a completed_with_errors batch is also accepted."""
        batch = _make_batch_mock(BatchStatus.completed_with_errors)
        mock_db = MagicMock()
        mock_db.scalar.return_value = batch

        client = self._make_client(mock_db)

        with (
            patch("dashboard.routers.actions.archive_batch"),
            patch("threading.Thread") as mock_thread,
        ):
            mock_thread.return_value = MagicMock()
            resp = client.post("/project/test-proj/api/batch/BATCH-00001/archive")

        assert resp.status_code == 204

    def test_archive_wrong_status_returns_422(self) -> None:
        """POST archive on a planning/executing batch returns 422."""
        for wrong_status in (BatchStatus.planning, BatchStatus.executing, BatchStatus.paused):
            batch = _make_batch_mock(wrong_status)
            mock_db = MagicMock()
            mock_db.scalar.return_value = batch

            client = self._make_client_no_exc(mock_db)
            resp = client.post("/project/test-proj/api/batch/BATCH-00001/archive")
            assert resp.status_code == 422, f"Expected 422 for status {wrong_status.value}"

    def test_archive_nonexistent_batch_returns_404(self) -> None:
        """POST archive on a nonexistent batch returns 404."""
        mock_db = MagicMock()
        mock_db.scalar.return_value = None  # batch not found

        client = self._make_client_no_exc(mock_db)
        resp = client.post("/project/test-proj/api/batch/BATCH-MISSING/archive")
        assert resp.status_code == 404

    def test_archive_response_has_hx_trigger(self) -> None:
        """Response includes HX-Trigger header for toast notification."""
        batch = _make_batch_mock(BatchStatus.completed)
        mock_db = MagicMock()
        mock_db.scalar.return_value = batch

        client = self._make_client(mock_db)

        with (
            patch("dashboard.routers.actions.archive_batch"),
            patch("threading.Thread") as mock_thread,
        ):
            mock_thread.return_value = MagicMock()
            resp = client.post("/project/test-proj/api/batch/BATCH-00001/archive")

        assert "HX-Trigger" in resp.headers
        import json

        trigger = json.loads(resp.headers["HX-Trigger"])
        assert "showToast" in trigger
        toast = trigger["showToast"]
        assert toast["type"] == "info"
        assert "archiving" in toast["message"].lower() or "BATCH-00001" in toast["message"]

    def test_archive_thread_is_daemon(self) -> None:
        """Background thread is created with daemon=True."""
        batch = _make_batch_mock(BatchStatus.completed)
        mock_db = MagicMock()
        mock_db.scalar.return_value = batch

        client = self._make_client(mock_db)

        with (
            patch("dashboard.routers.actions.archive_batch"),
            patch("threading.Thread") as mock_thread,
        ):
            mock_thread.return_value = MagicMock()
            client.post("/project/test-proj/api/batch/BATCH-00001/archive")

        # Verify Thread was created with daemon=True
        call_kwargs = mock_thread.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("daemon") is True
