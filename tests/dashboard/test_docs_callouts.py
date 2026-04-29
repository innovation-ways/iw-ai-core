"""Tests for GitHub-style callout rendering in docs detail pages.

The markdown library converts [!TYPE] blockquotes to <blockquote><p>[!TYPE] ...</p></blockquote>.
The server-side post-processor in render_markdown_with_callouts() converts these to
<div class="callout callout-{type}"> elements so FastAPI TestClient can verify them
without running JavaScript.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from fastapi import FastAPI


class TestDocsCallouts:
    """Tests for callout blockquote → callout div server-side conversion."""

    def _make_app(self) -> FastAPI:
        from dashboard.app import create_app

        return create_app()

    def _make_client(self, mock_db: MagicMock) -> TestClient:
        from dashboard.dependencies import get_db

        app = self._make_app()
        app.dependency_overrides[get_db] = lambda: mock_db
        return TestClient(app, raise_server_exceptions=False)

    def _make_project(self, project_id: str = "test-proj") -> MagicMock:
        p = MagicMock()
        p.id = project_id
        p.display_name = "Test Project"
        p.config = {}
        p.repo_root = "/tmp/test"
        return p

    def _make_doc_with_content(self, doc_id: str, content: str) -> MagicMock:
        doc = MagicMock()
        doc.id = f"{doc_id}"
        doc.doc_id = doc_id
        doc.title = f"Test {doc_id}"
        doc.slug = doc_id
        doc.content = content
        doc.doc_type = MagicMock(value="architecture")
        doc.status = MagicMock(value="published")
        doc.tier = MagicMock(value="primary")
        doc.version = 1
        doc.html_path = None
        doc.pdf_path = None
        doc.broken_links = None
        return doc

    def test_warning_callout_rendered_as_div(self) -> None:
        """[!WARNING] blockquote becomes class="callout callout-warning" div."""
        mock_project = self._make_project()
        mock_doc = self._make_doc_with_content(
            "test-doc",
            "> [!WARNING]\n> This is a warning message.\n",
        )

        mock_db = MagicMock()
        mock_db.scalar.return_value = mock_project

        with (
            patch("dashboard.routers.docs.DocService.get_doc", return_value=mock_doc),
            patch("dashboard.routers.docs.DocService.list_doc_versions", return_value=[]),
        ):
            client = self._make_client(mock_db)
            response = client.get("/project/test-proj/docs/test-doc")

        assert response.status_code == 200
        assert "callout-warning" in response.text, (
            'Expected class="callout callout-warning" in response HTML'
        )

    def test_note_callout_rendered_as_div(self) -> None:
        """[!NOTE] blockquote becomes class="callout callout-note" div."""
        mock_project = self._make_project()
        mock_doc = self._make_doc_with_content(
            "test-doc",
            "> [!NOTE]\n> This is a note.\n",
        )

        mock_db = MagicMock()
        mock_db.scalar.return_value = mock_project

        with (
            patch("dashboard.routers.docs.DocService.get_doc", return_value=mock_doc),
            patch("dashboard.routers.docs.DocService.list_doc_versions", return_value=[]),
        ):
            client = self._make_client(mock_db)
            response = client.get("/project/test-proj/docs/test-doc")

        assert response.status_code == 200
        assert "callout-note" in response.text, (
            'Expected class="callout callout-note" in response HTML'
        )

    def test_multiple_callout_types_rendered(self) -> None:
        """Multiple callout types all render correctly in same document."""
        mock_project = self._make_project()
        content = (
            "> [!NOTE]\n> A note.\n\n"
            "> [!WARNING]\n> A warning.\n\n"
            "> [!DANGER]\n> A danger.\n\n"
            "> [!TIP]\n> A tip.\n\n"
            "> [!IMPORTANT]\n> An important note.\n"
        )
        mock_doc = self._make_doc_with_content("test-doc", content)

        mock_db = MagicMock()
        mock_db.scalar.return_value = mock_project

        with (
            patch("dashboard.routers.docs.DocService.get_doc", return_value=mock_doc),
            patch("dashboard.routers.docs.DocService.list_doc_versions", return_value=[]),
        ):
            client = self._make_client(mock_db)
            response = client.get("/project/test-proj/docs/test-doc")

        assert response.status_code == 200
        assert "callout-note" in response.text
        assert "callout-warning" in response.text
        assert "callout-danger" in response.text
        assert "callout-tip" in response.text
        assert "callout-important" in response.text

    def test_regular_blockquote_unchanged(self) -> None:
        """Blockquotes without [!TYPE] prefix are left as-is (not callout)."""
        mock_project = self._make_project()
        mock_doc = self._make_doc_with_content(
            "test-doc",
            "> This is a regular blockquote without callout syntax.\n",
        )

        mock_db = MagicMock()
        mock_db.scalar.return_value = mock_project

        with (
            patch("dashboard.routers.docs.DocService.get_doc", return_value=mock_doc),
            patch("dashboard.routers.docs.DocService.list_doc_versions", return_value=[]),
        ):
            client = self._make_client(mock_db)
            response = client.get("/project/test-proj/docs/test-doc")

        assert response.status_code == 200
        assert "callout-" not in response.text, "Regular blockquote should not become a callout div"
