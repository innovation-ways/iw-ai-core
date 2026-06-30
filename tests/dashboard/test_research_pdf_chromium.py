"""Tests for research-document PDF + Markdown download routes.

The research view mirrors the docs view: a research document can be viewed inline
as a PDF (``/research/{doc_id}/pdf-view``), downloaded as a PDF attachment
(``/research/{doc_id}/pdf``), and downloaded as its raw Markdown source
(``/research/{doc_id}/md``). The PDF routes render markdown through the shared
branded ``pdf/doc_pdf.html`` template and the ``render_pdf_chromium`` worker, and
cache the result on disk keyed by doc version; the Markdown download serves
``ProjectDoc.content`` verbatim from the database with no rendering.

Semantic correctness over shape checking:
- BAD:  assert response.status_code == 200  (any backend gives 200)
- GOOD: assert mock_render.called_once()   (proves the Chromium path was taken)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory, Project, ProjectDoc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a TestClient that overrides get_db to use the test db_session."""
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


@pytest.fixture
def research_project(db_session: Session, tmp_path: Path) -> Project:  # noqa: assertion-scanner
    """Create a Project row with a writable repo_root for PDF cache tests."""
    project = Project(
        id="test-proj-research-pdf",
        display_name="Test Research Project",
        repo_root=str(tmp_path),
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


@pytest.fixture
def research_doc(db_session: Session, research_project: Project) -> ProjectDoc:  # noqa: assertion-scanner
    """Create a minimal research ProjectDoc row (doc_type=research, with content)."""
    doc = ProjectDoc(
        id=f"{research_project.id}:R-00152",
        doc_id="R-00152",
        project_id=research_project.id,
        title="A Research Document",
        slug="a-research-document",
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory.technical,
        doc_type=DocType.research,
        status=DocStatus.published,
        content="# Findings\n\nSome research prose with a **bold** claim.",
        version=1,
    )
    db_session.add(doc)
    db_session.flush()
    return doc


@pytest.fixture
def non_research_doc(db_session: Session, research_project: Project) -> ProjectDoc:  # noqa: assertion-scanner
    """Create an architecture (non-research) doc to assert the research routes reject it."""
    doc = ProjectDoc(
        id=f"{research_project.id}:ARCH-1",
        doc_id="ARCH-1",
        project_id=research_project.id,
        title="An Architecture Document",
        slug="an-architecture-document",
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory.technical,
        doc_type=DocType.architecture,
        status=DocStatus.published,
        content="# Arch\n\nNot a research doc.",
        version=1,
    )
    db_session.add(doc)
    db_session.flush()
    return doc


# ---------------------------------------------------------------------------
# pdf-view (inline) route
# ---------------------------------------------------------------------------


def test_research_pdf_view_uses_chromium(
    client: TestClient, research_project: Project, research_doc: ProjectDoc
):
    """The inline research PDF view renders via render_pdf_chromium and returns the bytes."""
    fake_pdf = b"%PDF-1.4 research-inline"

    with patch(
        "dashboard.routers.research.render_pdf_chromium", return_value=fake_pdf
    ) as mock_render:
        response = client.get(
            f"/project/{research_project.id}/research/{research_doc.doc_id}/pdf-view"
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == fake_pdf
    mock_render.assert_called_once()


def test_research_pdf_view_returns_200_with_unavailable_message(
    client: TestClient, research_project: Project, research_doc: ProjectDoc
):
    """When Chromium returns None, the inline view is a styled 200 HTML message, not a 503."""
    with patch("dashboard.routers.research.render_pdf_chromium", return_value=None):
        response = client.get(
            f"/project/{research_project.id}/research/{research_doc.doc_id}/pdf-view"
        )

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert response.text.find("PDF unavailable") != -1


# ---------------------------------------------------------------------------
# pdf (download) route
# ---------------------------------------------------------------------------


def test_research_pdf_download_uses_chromium_with_attachment(
    client: TestClient, research_project: Project, research_doc: ProjectDoc
):
    """The research PDF download renders via Chromium and sets a download filename header."""
    fake_pdf = b"%PDF-1.4 research-download"

    with patch(
        "dashboard.routers.research.render_pdf_chromium", return_value=fake_pdf
    ) as mock_render:
        response = client.get(f"/project/{research_project.id}/research/{research_doc.doc_id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    disposition = response.headers.get("content-disposition", "")
    assert disposition.find("attachment") != -1
    assert disposition.find(f"{research_doc.slug}-v{research_doc.version}.pdf") != -1
    mock_render.assert_called_once()


def test_research_pdf_download_returns_503_when_chromium_unavailable(
    client: TestClient, research_project: Project, research_doc: ProjectDoc
):
    """The download route returns 503 JSON (not a blank PDF) when Chromium is unavailable."""
    with patch("dashboard.routers.research.render_pdf_chromium", return_value=None):
        response = client.get(f"/project/{research_project.id}/research/{research_doc.doc_id}/pdf")

    assert response.status_code == 503
    assert response.json()["error"].lower().find("unavailable") != -1


# ---------------------------------------------------------------------------
# Caching + validation
# ---------------------------------------------------------------------------


def test_research_pdf_caches_and_reuses_without_rerender(
    client: TestClient, research_project: Project, research_doc: ProjectDoc
):
    """The second PDF request reuses the cached file on disk and skips Chromium entirely."""
    fake_pdf = b"%PDF-1.4 cached-research"

    with patch(
        "dashboard.routers.research.render_pdf_chromium", return_value=fake_pdf
    ) as mock_render:
        first = client.get(
            f"/project/{research_project.id}/research/{research_doc.doc_id}/pdf-view"
        )
    assert first.status_code == 200
    assert mock_render.call_count == 1

    cache_file = (
        Path(research_project.repo_root)
        / "docs"
        / ".generated"
        / research_project.id
        / f"{research_doc.doc_id}-v{research_doc.version}.pdf"
    )
    assert cache_file.exists()

    # Second request must NOT re-render — it serves the cached bytes.
    with patch(
        "dashboard.routers.research.render_pdf_chromium", return_value=b"%PDF should-not-be-used"
    ) as mock_render_2:
        second = client.get(
            f"/project/{research_project.id}/research/{research_doc.doc_id}/pdf-view"
        )

    assert second.status_code == 200
    assert second.content == fake_pdf
    mock_render_2.assert_not_called()


def test_research_pdf_view_404_for_non_research_doc(
    client: TestClient, research_project: Project, non_research_doc: ProjectDoc
):
    """The research PDF route rejects a non-research document with 404."""
    with patch("dashboard.routers.research.render_pdf_chromium", return_value=b"%PDF x"):
        response = client.get(
            f"/project/{research_project.id}/research/{non_research_doc.doc_id}/pdf-view"
        )

    assert response.status_code == 404


def test_research_pdf_404_for_missing_doc(client: TestClient, research_project: Project):
    """The research PDF download returns 404 when the document does not exist."""
    response = client.get(f"/project/{research_project.id}/research/R-99999/pdf")

    assert response.status_code == 404


def test_research_detail_page_has_pdf_tab_and_download(
    client: TestClient, research_project: Project, research_doc: ProjectDoc
):
    """The research detail page exposes a PDF tab and a Download PDF link."""
    response = client.get(f"/project/{research_project.id}/research/{research_doc.doc_id}")

    assert response.status_code == 200
    body = response.text
    # PDF tab present (switches to the pdf panel) and its lazy iframe target.
    assert body.find("switchDocTab('pdf')") != -1
    assert body.find(f"/research/{research_doc.doc_id}/pdf-view") != -1
    # Download PDF button links to the attachment route.
    assert (
        body.find(f'href="/project/{research_project.id}/research/{research_doc.doc_id}/pdf"') != -1
    )


# ---------------------------------------------------------------------------
# md (download) route
# ---------------------------------------------------------------------------


def test_research_md_download_serves_raw_content_with_attachment(
    client: TestClient, research_project: Project, research_doc: ProjectDoc
):
    """The Markdown download returns the stored content verbatim as a .md attachment."""
    response = client.get(f"/project/{research_project.id}/research/{research_doc.doc_id}/md")

    assert response.status_code == 200
    # Raw source served verbatim — body must equal the stored markdown exactly.
    assert response.text == research_doc.content
    assert response.headers["content-type"].find("text/markdown") != -1
    disposition = response.headers.get("content-disposition", "")
    assert disposition.find("attachment") != -1
    assert disposition.find(f"{research_doc.slug}-v{research_doc.version}.md") != -1


def test_research_md_download_404_for_non_research_doc(
    client: TestClient, research_project: Project, non_research_doc: ProjectDoc
):
    """The Markdown download rejects a non-research document with 404."""
    response = client.get(f"/project/{research_project.id}/research/{non_research_doc.doc_id}/md")

    assert response.status_code == 404


def test_research_md_download_404_for_missing_doc(client: TestClient, research_project: Project):
    """The Markdown download returns 404 when the document does not exist."""
    response = client.get(f"/project/{research_project.id}/research/R-99999/md")

    assert response.status_code == 404


def test_research_detail_page_has_md_download(
    client: TestClient, research_project: Project, research_doc: ProjectDoc
):
    """The research detail page exposes a Download MD link to the markdown attachment route."""
    response = client.get(f"/project/{research_project.id}/research/{research_doc.doc_id}")

    assert response.status_code == 200
    body = response.text
    assert (
        body.find(f'href="/project/{research_project.id}/research/{research_doc.doc_id}/md"') != -1
    )
    assert body.find("Download MD") != -1
