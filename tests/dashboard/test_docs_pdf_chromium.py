"""I-00074 S03 — Tests for PDF export via Chromium (not WeasyPrint).

Tests verify:
1. `render_pdf_chromium()` exists and is callable (reproduction test — fails before fix)
2. Chromium binary missing → returns None (no exception)
3. Chromium subprocess fails (non-zero rc) → returns None
4. Chromium succeeds → returns PDF bytes
5. Chromium subprocess timeout → returns None (not exception propagation)
6. subprocess.run is called with --print-to-pdf flag (proves Chromium path taken)
7. `docs_pdf_view` route uses Chromium, not WeasyPrint
8. `docs_pdf_view` returns 503 when Chromium unavailable
9. `docs_pdf` download route uses Chromium, not WeasyPrint
10. `_make_render_pdf_fn()` returns `render_pdf_chromium`

Semantic correctness over shape checking (I003 lesson):
- BAD:  assert response.status_code == 200  (shape only — WeasyPrint would also give 200)
- GOOD: assert mock_render.called_once()   (semantic — proves Chromium path taken)
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers.docs import _make_render_pdf_fn
from dashboard.utils import markdown as md_mod
from dashboard.utils.markdown import render_pdf_chromium
from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory, Project, ProjectDoc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Client fixture (from tests/dashboard/conftest.py pattern)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a TestClient that overrides get_db to use the test db_session."""
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
# Helper to create a minimal project + doc for route tests
# ---------------------------------------------------------------------------


@pytest.fixture
def test_doc_project(db_session: Session) -> Project:
    """Create a Project row with a writable repo_root for PDF cache tests."""
    project = Project(
        id="test-proj-pdf",
        display_name="Test Project PDF",
        repo_root="/tmp/test-pdf-proj",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


@pytest.fixture
def test_doc(db_session: Session, test_doc_project: Project) -> ProjectDoc:
    """Create a minimal ProjectDoc row for PDF route tests."""
    doc = ProjectDoc(
        id=f"{test_doc_project.id}:test-doc",
        doc_id="test-doc",
        project_id=test_doc_project.id,
        title="Test Document",
        slug="test-doc",
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory.technical,
        doc_type=DocType.architecture,
        status=DocStatus.published,
        content=(
            "# Hello\n\nSome text with a Mermaid diagram:\n\n"
            "```mermaid\ngraph TD\n    A[Start] --> B[End]\n```"
        ),
        version=1,
    )
    db_session.add(doc)
    db_session.flush()
    return doc


# ---------------------------------------------------------------------------
# Group 1: Unit tests for render_pdf_chromium()
# ---------------------------------------------------------------------------


def test_i00074_render_pdf_chromium_exists():
    """Fails before fix (function didn't exist); passes after."""
    assert callable(render_pdf_chromium)


def test_i00074_render_pdf_chromium_binary_missing(monkeypatch, tmp_path):
    """When Chromium binary does not exist, returns None (not an exception)."""
    monkeypatch.setattr(md_mod, "_PLAYWRIGHT_CHROME", tmp_path / "nonexistent_chrome")

    result = render_pdf_chromium("<html><body>test</body></html>")
    assert result is None


def test_i00074_render_pdf_chromium_subprocess_fails(monkeypatch, tmp_path):
    """When Chromium exits with non-zero code, returns None."""
    fake_chrome = tmp_path / "chrome"
    fake_chrome.touch()
    monkeypatch.setattr(md_mod, "_PLAYWRIGHT_CHROME", fake_chrome)

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = b"error: something went wrong"

    with patch("dashboard.utils.markdown.subprocess.run", return_value=mock_result):
        result = render_pdf_chromium("<html><body>test</body></html>")

    assert result is None


def test_i00074_render_pdf_chromium_success(monkeypatch, tmp_path):
    """When Chromium succeeds and writes output PDF, returns the PDF bytes."""
    fake_chrome = tmp_path / "chrome"
    fake_chrome.touch()
    monkeypatch.setattr(md_mod, "_PLAYWRIGHT_CHROME", fake_chrome)

    fake_pdf_content = b"%PDF-1.4 fake-content"

    def fake_run(cmd: list, **kwargs):  # type: ignore[no-untyped-def]
        # Find --print-to-pdf=<path> and write fake PDF there
        for arg in cmd:
            if isinstance(arg, str) and arg.startswith("--print-to-pdf="):
                out_path = Path(arg.split("=", 1)[1])
                out_path.write_bytes(fake_pdf_content)
        result = MagicMock()
        result.returncode = 0
        result.stderr = b""
        return result

    with patch("dashboard.utils.markdown.subprocess.run", side_effect=fake_run):
        result = render_pdf_chromium("<html><body>test</body></html>")

    assert result == fake_pdf_content


def test_i00074_render_pdf_chromium_subprocess_timeout(monkeypatch, tmp_path):
    """When Chromium hangs and subprocess.run raises TimeoutExpired, returns None.

    Without the try/except wrapper around subprocess.run, a Chromium hang would
    propagate as an unhandled exception and the calling route would return 500
    instead of the intended 503.
    """

    fake_chrome = tmp_path / "chrome"
    fake_chrome.touch()
    monkeypatch.setattr(md_mod, "_PLAYWRIGHT_CHROME", fake_chrome)

    def fake_run(cmd: list, **kwargs):  # type: ignore[no-untyped-def]
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 30))

    with patch("dashboard.utils.markdown.subprocess.run", side_effect=fake_run):
        result = render_pdf_chromium("<html><body>test</body></html>")

    assert result is None


def test_i00074_render_pdf_chromium_uses_print_to_pdf_flag(monkeypatch, tmp_path):
    """Chromium must be invoked with --print-to-pdf (not --output or stdout)."""
    fake_chrome = tmp_path / "chrome"
    fake_chrome.touch()
    monkeypatch.setattr(md_mod, "_PLAYWRIGHT_CHROME", fake_chrome)

    captured_calls: list[list] = []

    def fake_run(cmd: list, **kwargs):  # type: ignore[no-untyped-def]
        captured_calls.append(cmd)
        for arg in cmd:
            if isinstance(arg, str) and arg.startswith("--print-to-pdf="):
                out_path = Path(arg.split("=", 1)[1])
                out_path.write_bytes(b"%PDF fake")
        result = MagicMock()
        result.returncode = 0
        result.stderr = b""
        return result

    with patch("dashboard.utils.markdown.subprocess.run", side_effect=fake_run):
        render_pdf_chromium("<html><body>x</body></html>")

    assert len(captured_calls) == 1
    cmd = captured_calls[0]
    # Semantic: verify specific required flags
    flags = " ".join(cmd)
    assert "--print-to-pdf=" in flags, "Chromium must use --print-to-pdf flag"
    assert "--headless" in flags, "Chromium must run headless"
    assert "--no-sandbox" in flags, "Chromium must run with --no-sandbox for WSL/Linux"


# ---------------------------------------------------------------------------
# Group 2: Route-level tests (use client fixture)
# ---------------------------------------------------------------------------


def test_i00074_docs_pdf_view_does_not_call_weasyprint(
    client: TestClient, test_doc_project: Project, test_doc: ProjectDoc
):
    """The inline PDF view endpoint must not call WeasyPrint.HTML (I-00074)."""
    fake_pdf = b"%PDF-1.4 fake-inline"

    with patch("dashboard.routers.docs.render_pdf_chromium", return_value=fake_pdf) as mock_render:
        response = client.get(f"/project/{test_doc_project.id}/docs/{test_doc.doc_id}/pdf-view")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == fake_pdf
    mock_render.assert_called_once()


def test_i00074_docs_pdf_view_returns_200_with_unavailable_message(
    client: TestClient, test_doc_project: Project, test_doc: ProjectDoc
):
    """When Chromium returns None, response is 200 with styled HTML message (not bare 503).

    I-00080 S05 changed docs_pdf_view to return a styled 'PDF unavailable' HTML page
    with HTTP 200 when Chromium is unavailable, so the iframe shows a meaningful
    message instead of a blank screen. This aligns with the AC2 acceptance criterion.
    """
    with patch("dashboard.routers.docs.render_pdf_chromium", return_value=None):
        response = client.get(f"/project/{test_doc_project.id}/docs/{test_doc.doc_id}/pdf-view")

    assert response.status_code == 200
    assert "PDF unavailable" in response.text
    assert "text/html" in response.headers.get("content-type", "")


def test_i00074_docs_pdf_download_does_not_call_weasyprint(
    client: TestClient, test_doc_project: Project, test_doc: ProjectDoc
):
    """The PDF download route must not call WeasyPrint.HTML (I-00074)."""
    fake_pdf = b"%PDF-1.4 fake-download"

    with patch("dashboard.routers.docs.render_pdf_chromium", return_value=fake_pdf) as mock_render:
        response = client.get(f"/project/{test_doc_project.id}/docs/{test_doc.doc_id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers.get("content-disposition", "")
    mock_render.assert_called_once()


def test_i00074_make_render_pdf_fn_returns_chromium():
    """Export bundle factory must return render_pdf_chromium, not a WeasyPrint wrapper."""
    from dashboard.utils.markdown import render_pdf_chromium as expected

    fn = _make_render_pdf_fn()
    assert fn is expected
