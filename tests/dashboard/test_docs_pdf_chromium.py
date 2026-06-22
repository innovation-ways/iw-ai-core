"""I-00074 S03 — Tests for PDF export via Chromium + Paged.js (not WeasyPrint).

Since the paged-layout redesign, ``render_pdf_chromium`` drives a fresh
``pdf_worker.py`` subprocess (Playwright + Paged.js) rather than invoking Chromium
directly with ``--print-to-pdf``. These tests assert against that worker contract.

Tests verify:
1. `render_pdf_chromium()` exists and is callable (reproduction test — fails before fix)
2. Paged.js polyfill missing → returns None (no exception)
3. Worker subprocess fails (non-zero rc) → returns None
4. Worker succeeds → returns PDF bytes
5. Worker subprocess timeout → returns None (not exception propagation)
6. subprocess.run launches the pdf_worker.py with html/pdf/pagedjs paths (proves worker path taken)
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
import sys
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
# Helper to create a minimal project + doc for route tests
# ---------------------------------------------------------------------------


@pytest.fixture
def test_doc_project(db_session: Session) -> Project:  # noqa: assertion-scanner
    """ "Create a Project row with a writable repo_root for PDF cache tests."""
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
def test_doc(db_session: Session, test_doc_project: Project) -> ProjectDoc:  # noqa: assertion-scanner
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


def test_i00074_render_pdf_pagedjs_missing(monkeypatch, tmp_path):
    """When the Paged.js polyfill is absent, returns None without launching a subprocess."""
    monkeypatch.setattr(md_mod, "_PAGEDJS_PATH", tmp_path / "nonexistent_paged.js")

    called = False

    def fake_run(cmd: list, **kwargs):  # type: ignore[no-untyped-def]
        """Flag that the subprocess was (incorrectly) launched."""
        nonlocal called
        called = True
        return MagicMock(returncode=0, stderr=b"")

    with patch("dashboard.utils.markdown.subprocess.run", side_effect=fake_run):
        result = render_pdf_chromium("<html><body>test</body></html>")

    assert result is None
    assert called is False


def test_i00074_render_pdf_chromium_subprocess_fails():
    """When the PDF worker exits with non-zero code, returns None."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = b"error: something went wrong"

    with patch("dashboard.utils.markdown.subprocess.run", return_value=mock_result):
        result = render_pdf_chromium("<html><body>test</body></html>")

    assert result is None


def _pdf_path_from_worker_cmd(cmd: list) -> Path:
    """Return the output PDF path argument from a pdf_worker.py invocation.

    Args:
        cmd: The argv list passed to ``subprocess.run`` — ``[python, pdf_worker.py,
            html_path, pdf_path, pagedjs_path, [chrome_path]]``.

    Returns:
        The ``pdf_path`` element (the sole ``.pdf`` argument).
    """
    pdf_args = [a for a in cmd if isinstance(a, str) and a.endswith(".pdf")]
    assert len(pdf_args) == 1, f"expected exactly one .pdf arg, got {pdf_args}"
    return Path(pdf_args[0])


def test_i00074_render_pdf_chromium_success():
    """When the worker succeeds and writes the output PDF, returns the PDF bytes."""
    fake_pdf_content = b"%PDF-1.4 fake-content"

    def fake_run(cmd: list, **kwargs):  # type: ignore[no-untyped-def]
        """Simulate a successful pdf_worker run that writes to the pdf_path arg."""
        _pdf_path_from_worker_cmd(cmd).write_bytes(fake_pdf_content)
        result = MagicMock()
        result.returncode = 0
        result.stderr = b""
        return result

    with patch("dashboard.utils.markdown.subprocess.run", side_effect=fake_run):
        result = render_pdf_chromium("<html><body>test</body></html>")

    assert result == fake_pdf_content


def test_i00074_render_pdf_chromium_subprocess_timeout():
    """When the worker hangs and subprocess.run raises TimeoutExpired, returns None.

    Without the try/except wrapper around subprocess.run, a worker hang would
    propagate as an unhandled exception and the calling route would return 500
    instead of the intended 503.
    """

    def fake_run(cmd: list, **kwargs):  # type: ignore[no-untyped-def]
        """Simulate a hung worker subprocess."""
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 30))

    with patch("dashboard.utils.markdown.subprocess.run", side_effect=fake_run):
        result = render_pdf_chromium("<html><body>test</body></html>")

    assert result is None


def test_i00074_render_pdf_chromium_launches_pdf_worker():
    """render_pdf_chromium must launch pdf_worker.py with the html/pdf/pagedjs paths."""
    captured_calls: list[list] = []

    def fake_run(cmd: list, **kwargs):  # type: ignore[no-untyped-def]
        """Capture the worker invocation and write a stub PDF to the pdf_path arg."""
        captured_calls.append(cmd)
        _pdf_path_from_worker_cmd(cmd).write_bytes(b"%PDF fake")
        result = MagicMock()
        result.returncode = 0
        result.stderr = b""
        return result

    with patch("dashboard.utils.markdown.subprocess.run", side_effect=fake_run):
        render_pdf_chromium("<html><body>x</body></html>")

    assert len(captured_calls) == 1
    cmd = captured_calls[0]
    # Semantic: the worker script and the three required path args are present.
    assert cmd[0] == sys.executable, "worker must run under the same interpreter"
    assert cmd[1].endswith("pdf_worker.py"), "must invoke the pdf_worker.py script"
    assert str(md_mod._PAGEDJS_PATH) in cmd, "must pass the Paged.js polyfill path"
    html_args = [a for a in cmd if isinstance(a, str) and a.endswith(".html")]
    assert len(html_args) == 1, "must pass exactly one input HTML path"


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
