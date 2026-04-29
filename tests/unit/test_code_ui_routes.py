"""Unit tests for dashboard/routers/code_ui.py route handlers.

These tests focus on helper functions and error handling that don't require
template rendering. Template-dependent route tests are covered in integration tests.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from orch.db.models import CodeIndexJob, Project


def _make_app() -> Any:
    """Create a TestClient-ready FastAPI app."""
    from dashboard.app import create_app

    return create_app()


def _make_client(mock_db: MagicMock) -> TestClient:
    """Create a TestClient with the DB dependency overridden."""
    from dashboard.dependencies import get_db

    app = _make_app()
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _make_project(project_id: str = "test-proj") -> MagicMock:
    p = MagicMock(spec=Project)
    p.id = project_id
    p.display_name = "Test Project"
    p.config = {"code_understanding": {"index_tier": "balanced"}}
    return p


class TestMermaidPreprocessing:
    """Tests for _preprocess_mermaid helper."""

    def test_mermaid_blocks_converted_to_pre(self) -> None:
        from dashboard.routers.code_ui import _preprocess_mermaid

        input_md = "```mermaid\ngraph TD\n  A-->B\n```"
        result = _preprocess_mermaid(input_md)
        assert '<pre data-lang="mermaid">' in result
        assert "<code>" in result
        assert "graph TD" in result

    def test_multiple_mermaid_blocks_converted(self) -> None:
        from dashboard.routers.code_ui import _preprocess_mermaid

        input_md = "Some text\n```mermaid\ng1\n```\nMore\n```mermaid\ng2\n```\nEnd"
        result = _preprocess_mermaid(input_md)
        assert result.count('<pre data-lang="mermaid">') == 2
        assert "<code>" in result

    def test_no_mermaid_blocks_unchanged(self) -> None:
        from dashboard.routers.code_ui import _preprocess_mermaid

        input_md = "Just regular text\n```python\nprint('hi')\n```"
        result = _preprocess_mermaid(input_md)
        assert '<pre data-lang="mermaid">' not in result

    def test_mermaid_blocks_with_whitespace_converted(self) -> None:
        from dashboard.routers.code_ui import _preprocess_mermaid

        input_md = "```mermaid\n  graph TD\n    A-->B\n```"
        result = _preprocess_mermaid(input_md)
        assert '<pre data-lang="mermaid">' in result
        assert "graph TD" in result


class TestFormatDuration:
    """Tests for _format_duration helper."""

    def test_format_duration_minutes_seconds(self) -> None:
        from dashboard.routers.code_ui import _format_duration

        job = MagicMock()
        job.triggered_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        job.completed_at = datetime(2026, 1, 1, 12, 4, 32, tzinfo=UTC)
        result = _format_duration(job)
        assert result == "4m 32s"

    def test_format_duration_hours(self) -> None:
        from dashboard.routers.code_ui import _format_duration

        job = MagicMock()
        job.triggered_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        job.completed_at = datetime(2026, 1, 1, 14, 30, 0, tzinfo=UTC)
        result = _format_duration(job)
        assert result == "2h 30m"

    def test_format_duration_seconds_only(self) -> None:
        from dashboard.routers.code_ui import _format_duration

        job = MagicMock()
        job.triggered_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        job.completed_at = datetime(2026, 1, 1, 12, 0, 45, tzinfo=UTC)
        result = _format_duration(job)
        assert result == "45s"

    def test_format_duration_returns_none_when_completed_at_missing(self) -> None:
        from dashboard.routers.code_ui import _format_duration

        job = MagicMock()
        job.triggered_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        job.completed_at = None
        result = _format_duration(job)
        assert result is None

    def test_format_duration_returns_none_when_triggered_at_missing(self) -> None:
        from dashboard.routers.code_ui import _format_duration

        job = MagicMock()
        job.triggered_at = None
        job.completed_at = datetime(2026, 1, 1, 12, 4, 32, tzinfo=UTC)
        result = _format_duration(job)
        assert result is None


class TestGetProviderLabel:
    """Tests for _get_provider_label helper."""

    def test_provider_label_with_config(self) -> None:
        from dashboard.routers.code_ui import _get_provider_label

        project = MagicMock()
        project.config = {"code_understanding": {"index_tier": "fast"}}
        result = _get_provider_label(project)
        assert result == "local (fast)"

    def test_provider_label_default_tier(self) -> None:
        from dashboard.routers.code_ui import _get_provider_label

        project = MagicMock()
        project.config = {"code_understanding": {}}
        result = _get_provider_label(project)
        assert result == "local (balanced)"

    def test_provider_label_no_config(self) -> None:
        from dashboard.routers.code_ui import _get_provider_label

        project = MagicMock()
        project.config = {}
        result = _get_provider_label(project)
        assert result == "local (balanced)"

    def test_provider_label_none_config(self) -> None:
        from dashboard.routers.code_ui import _get_provider_label

        project = MagicMock()
        project.config = None
        result = _get_provider_label(project)
        assert result == "local (balanced)"

    def test_provider_label_quality_tier(self) -> None:
        from dashboard.routers.code_ui import _get_provider_label

        project = MagicMock()
        project.config = {"code_understanding": {"index_tier": "quality"}}
        result = _get_provider_label(project)
        assert result == "local (quality)"


class TestGetProjectOr404:
    """Tests for _get_project_or_404 helper."""

    def test_returns_project_when_found(self) -> None:
        from dashboard.routers.code_ui import _get_project_or_404

        project = _make_project()
        mock_db = MagicMock()
        mock_db.scalar.return_value = project

        result = _get_project_or_404("test-proj", mock_db)
        assert result is project

    def test_raises_404_when_not_found(self) -> None:
        import pytest
        from fastapi import HTTPException

        from dashboard.routers.code_ui import _get_project_or_404

        mock_db = MagicMock()
        mock_db.scalar.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            _get_project_or_404("nonexistent", mock_db)
        assert exc_info.value.status_code == 404


class TestCodeIndexStream:
    """Tests for the SSE stream endpoint logic."""

    def test_sse_stream_returns_idle_when_no_runner_in_registry(self) -> None:
        with patch.dict("dashboard.routers.code_ui.JOB_REGISTRY", {}, clear=False):
            app = _make_app()
            from dashboard.dependencies import get_db

            mock_db = MagicMock()
            app.dependency_overrides[get_db] = lambda: mock_db

            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/project/test-proj/api/code/index/stream", timeout=3)

            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")


class TestCodeCancelIndex:
    """Tests for the cancel endpoint."""

    def test_cancel_returns_404_when_no_running_job(self) -> None:
        with patch.dict("dashboard.routers.code_ui.JOB_REGISTRY", {}, clear=False):
            mock_db = MagicMock()
            mock_db.scalar.return_value = _make_project()

            client = _make_client(mock_db)
            response = client.delete("/project/test-proj/api/code/index")

            assert response.status_code == 404

    def test_cancel_calls_request_cancel_when_runner_exists(self) -> None:
        mock_runner = MagicMock()
        mock_runner.job_id = "job-abc"
        mock_runner.request_cancel = MagicMock()

        with patch.dict(
            "dashboard.routers.code_ui.JOB_REGISTRY",
            {"test-proj": mock_runner},
            clear=False,
        ):
            mock_db = MagicMock()
            mock_db.scalar.return_value = _make_project()

            client = _make_client(mock_db)
            response = client.delete("/project/test-proj/api/code/index")

            assert response.status_code == 200
            mock_runner.request_cancel.assert_called_once()


class TestJobAlreadyRunningError:
    """Tests for JobAlreadyRunningError handling in trigger endpoints."""

    def test_trigger_raises_409_on_job_already_running_error(self) -> None:
        from orch.rag.job import JobAlreadyRunningError

        project = _make_project()
        mock_db = MagicMock()
        mock_db.scalar.return_value = project
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        with (
            patch("dashboard.routers.code_ui.start_index_job") as start_mock,
            patch("dashboard.routers.code_ui.CodeIndexJob") as job_mock,
        ):
            start_mock.side_effect = JobAlreadyRunningError("test-proj")

            job_instance = MagicMock(spec=CodeIndexJob)
            job_instance.id = "job-abc"
            job_mock.return_value = job_instance

            client = _make_client(mock_db)
            response = client.post("/project/test-proj/api/code/index")

            assert response.status_code == 409
