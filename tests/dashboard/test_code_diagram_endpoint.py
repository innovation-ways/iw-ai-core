"""Contract tests for GET /api/projects/{project_id}/code/modules/{module_slug}/diagram."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# Module-level imports so that orch.db.session._engine is initialised during
# pytest collection — i.e. before the session-scoped _arm_live_db_guard fixture
# sets IW_CORE_TEST_CONTEXT=true. Mirrors the pattern used by
# tests/dashboard/test_jobs_filter_ui.py and test_staleness_router.py
# (see tests/CLAUDE.md "Gotchas" section for the rationale).
from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from fastapi import FastAPI


class TestDiagramEndpoint:
    """Tests for the /diagram fragment endpoint."""

    def _make_app(self) -> FastAPI:
        return create_app()

    def _make_client(self, mock_db: MagicMock) -> TestClient:
        app = self._make_app()
        app.dependency_overrides[get_db] = lambda: mock_db
        return TestClient(app, raise_server_exceptions=False)

    def _make_project(self, project_id: str = "test-proj") -> MagicMock:
        p = MagicMock()
        p.id = project_id
        p.display_name = "Test Project"
        p.config = {"code_understanding": {"index_tier": "balanced"}}
        return p

    def _make_diagram_doc(self, content: str = "graph TD\n  A --> B") -> MagicMock:
        doc = MagicMock()
        doc.content = content
        return doc

    def test_diagram_endpoint_returns_fragment_when_doc_exists(self) -> None:
        """Returns 200 with diagram DSL and data-lang="mermaid" when doc exists."""
        mock_project = self._make_project()
        mock_diagram_doc = self._make_diagram_doc("graph TD\n  A --> B")

        mock_db = MagicMock()
        mock_db.scalar.return_value = mock_project

        with patch("orch.doc_service.DocService.get_doc", return_value=mock_diagram_doc):
            client = self._make_client(mock_db)
            response = client.get(
                "/api/projects/test-proj/code/modules/test-mod/diagram",
            )

        assert response.status_code == 200
        assert "graph TD" in response.text
        # F-00065 renders code-module diagrams via <div class="mermaid">…</div>
        # (the chat code-block path uses <pre data-lang="mermaid">). Both render
        # via mermaid.js but only the former selector is correct here.
        assert 'class="mermaid"' in response.text

    def test_diagram_endpoint_returns_empty_state_when_no_doc(self) -> None:
        """Returns 200 with empty-state indicator when no diagram doc exists."""
        mock_project = self._make_project()

        mock_db = MagicMock()
        mock_db.scalar.return_value = mock_project

        with patch("orch.doc_service.DocService.get_doc", return_value=None):
            client = self._make_client(mock_db)
            response = client.get(
                "/api/projects/test-proj/code/modules/test-mod/diagram",
            )

        assert response.status_code == 200
        assert "code-diagram-empty" in response.text or "No diagram yet" in response.text, (
            "Expected empty-state CSS class or message in response"
        )

    def test_diagram_endpoint_returns_404_for_unknown_project(self) -> None:
        """Returns 404 when project does not exist."""
        mock_db = MagicMock()
        mock_db.scalar.return_value = None

        client = self._make_client(mock_db)
        response = client.get(
            "/api/projects/unknown/code/modules/test-mod/diagram",
        )

        assert response.status_code == 404
