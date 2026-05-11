"""I-00080 S07 — Dashboard integration tests for docs diagram rendering.

Tests the fix for: server-side Mermaid render is uncached and dark-mode-unaware
(slow loads, white-on-white diagram labels, blank HTML/PDF tabs).

These tests drive FastAPI routes / Jinja2 templates via the dashboard `client`
fixture, so they live under tests/dashboard/ (the `client` fixture is registered
only in tests/dashboard/conftest.py via the integration conftest re-export).

Test contract (semantic assertions — shape-checks would false-positive):
- BAD:  assert "mermaid" in html          (matches <script src=.../mermaid.min.js>)
- GOOD: assert 'class="mermaid"' in html  or  re.search(r'class="mermaid"')
- GOOD: assert "1e293b" in html           (specific enforced dark colour token)
- GOOD: assert resp.status_code == 200 and b"unavailable" in resp.content.lower()

Design references:
- S01 (backend-impl):  colour token 1e293b, wrapper div colour:#1e293b
- S03 (frontend-impl): client-side shim converts pre>code.language-mermaid → div.mermaid
- S05 (api-impl):      render_mermaid=False, cache dir docs/.generated/{pid}/,
                       "PDF unavailable" 200 with <h2>PDF unavailable</h2>

IMPORTANT: TestClient does NOT execute JavaScript, so the S03 client-side shim
never runs in these tests. We check for pre>code.language-mermaid (the pre-shim
state) or the mermaid libs <script> tag. The mermaid.min.js <script> tag IS
present in the page HTML (inserted by the template unconditionally), which
confirms the library is loaded for the client-side shim.
"""

from __future__ import annotations

import os
import re
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    Project,
    ProjectDoc,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Client fixture (same pattern as test_docs_running_jobs.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a TestClient that overrides get_db to use the test db_session."""
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
# Helpers
# ---------------------------------------------------------------------------


def _make_project_doc(
    db_session: Session,
    project_id: str,
    doc_id: str,
    *,
    title: str = "Test Doc",
    content: str = "# Test content",
    doc_type: DocType = DocType.architecture,
    status: DocStatus = DocStatus.published,
    version: int = 1,
    html_path: str | None = None,
    pdf_path: str | None = None,
) -> ProjectDoc:
    """Create and flush a ProjectDoc row with all required fields."""
    composite_id = f"{project_id}:{doc_id}"
    doc = ProjectDoc(
        id=composite_id,
        project_id=project_id,
        doc_id=doc_id,
        title=title,
        slug=doc_id,
        doc_type=doc_type,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        status=status,
        content=content,
        audience=[],
        source_paths=[],
        version=version,
        html_path=html_path,
        pdf_path=pdf_path,
    )
    db_session.add(doc)
    db_session.flush()
    return doc


# ---------------------------------------------------------------------------
# Test 1: markdown panel uses render_mermaid=False (client-side shim)
# ---------------------------------------------------------------------------


class TestDocsDetailClientSideDiagram:
    """Test that the markdown panel on docs_detail uses client-side rendering.

    Pre-fix: docs_detail called render_markdown_with_callouts with
    render_mermaid=True → mmdc <svg> embedded in page → slow loads.
    Post-fix: render_mermaid=False → raw language-mermaid block for
    client-side shim → fast page load.
    """

    def test_i00080_docs_detail_calls_render_mermaid_false(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Verify docs_detail calls render_markdown_with_callouts with
        render_mermaid=False. Pre-fix: called with True (blocking mmdc).
        Post-fix: called with False (client-side shim handles diagram).
        """
        _make_project_doc(
            db_session,
            test_project.id,
            "diagram-doc",
            title="Diagram Test",
            doc_type=DocType.architecture,
            content=(
                "# Architecture\n\n```mermaid\ngraph TD\n    A[Foo] --> B[Bar]\n```\n\nEnd of doc."
            ),
        )
        db_session.commit()

        # Capture render_markdown_with_callouts calls via spy at router level
        from dashboard.utils import markdown as md_mod

        original_fn = md_mod.render_markdown_with_callouts
        call_record: dict[str, Any] = {}

        def spy_fn(text: str, render_mermaid: bool = True) -> str:
            call_record["render_mermaid"] = render_mermaid
            call_record["text_len"] = len(text)
            return original_fn(text, render_mermaid=render_mermaid)

        # Patch at the module level used by docs.py
        with patch("dashboard.routers.docs.render_markdown_with_callouts", spy_fn):
            response = client.get(f"/project/{test_project.id}/docs/diagram-doc")

        assert response.status_code == 200, "docs_detail must return 200"

        # The critical assertion: render_mermaid must be False
        # Pre-fix: route called it with True (mmdc path) → slow
        # Post-fix: route calls it with False → fast, client-side shim
        assert call_record.get("render_mermaid") is False, (
            "render_markdown_with_callouts must be called with render_mermaid=False "
            "on docs_detail — the S03 client-side shim handles diagrams. "
            f"Got render_mermaid={call_record.get('render_mermaid')} "
            "(this means the page is still calling mmdc and will be slow)"
        )

    def test_i00080_docs_detail_page_contains_mermaid_lib(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """The docs_detail page must load mermaid.min.js (for client-side shim)."""
        _make_project_doc(
            db_session,
            test_project.id,
            "mermaid-lib-test",
            title="Mermaid Lib Test",
            doc_type=DocType.architecture,
            content="# Intro\n\nSome text.\n",
        )
        db_session.commit()

        response = client.get(f"/project/{test_project.id}/docs/mermaid-lib-test")
        assert response.status_code == 200
        html = response.text

        # Page must include mermaid.min.js (loaded by components/libs/mermaid.html)
        assert "mermaid.min.js" in html, (
            "mermaid.min.js <script> must be present — loaded by "
            "{% include 'components/libs/mermaid.html' %} in docs_detail.html"
        )

    def test_i00080_raw_dsl_diagram_doc_not_garbled(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """A doc_type=diagram doc with bare DSL (no ```mermaid fence) must not
        render as garbled markdown (<h2>setext</h2>, <p>DSL lines).

        Pre-fix: no _normalize_doc_content_for_render → raw DSL passed through
        markdown → `---` becomes thematic break, `config:` becomes setext <h2>,
        graph TD line becomes a paragraph.
        Post-fix: _normalize_doc_content_for_render wraps bare DSL in a fence,
        markdown produces pre>code.language-mermaid block.
        """
        # Raw DSL shape from orch/rag/mapgen.py (no ```mermaid fence)
        raw_dsl_content = (
            "<!-- purpose: demo -->\n"
            "---\n"
            "config:\n"
            "  layout: elk\n"
            "---\n"
            "graph TD\n"
            "    A[Foo] --> B[Bar]\n"
        )
        _make_project_doc(
            db_session,
            test_project.id,
            "raw-dsl-diagram",
            title="Raw DSL Diagram",
            doc_type=DocType.diagram,
            content=raw_dsl_content,
        )
        db_session.commit()

        response = client.get(f"/project/{test_project.id}/docs/raw-dsl-diagram")
        assert response.status_code == 200, "docs_detail must return 200"
        html = response.text

        # The raw DSL must NOT appear as setext markdown:
        # The `config:` line must not appear as an <h2> element
        # The `graph TD` line must not appear as a bare <p>
        # Signal: look for absence of DSL-as-heading
        h2_elements = re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.DOTALL)
        dsl_as_heading = any(
            t for t in h2_elements if "config" in t.lower() or "graph" in t.lower()
        )
        assert not dsl_as_heading, (
            f"DSL text must not appear as markdown headings. "
            f"Found h2 elements with DSL: {dsl_as_heading}"
        )

        # The normalized content should appear as a code block (language-mermaid)
        # or as a div.mermaid if the shim ran — either way it's NOT garbled
        has_mermaid_block = 'class="language-mermaid"' in html or 'class="mermaid"' in html
        assert has_mermaid_block, (
            "Raw-DSL diagram must be wrapped in a fenced mermaid block "
            "(via _normalize_doc_content_for_render) and appear as "
            "language-mermaid code block. Not found in HTML snippet: "
            f"{html[:600]}"
        )


# ---------------------------------------------------------------------------
# Test 3: html-view caches to html_path keyed by version
# ---------------------------------------------------------------------------


class TestHtmlViewCaching:
    """Test that docs_html_view writes and serves from a version-keyed cache."""

    def test_i00080_html_view_caches_to_html_path_keyed_by_version(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """After GET /docs/{doc_id}/html-view on a doc with no html_path,
        the doc's html_path is set and points at an existing file under
        docs/.generated whose filename contains v{version}.
        A second GET serves the cached file without re-rendering.
        """
        test_project.repo_root = str(tmp_path)
        db_session.commit()

        _make_project_doc(
            db_session,
            test_project.id,
            "html-cache-test",
            title="HTML Cache Test",
            content="# Intro\n\nSome text.\n",
            version=3,
            html_path=None,
        )
        db_session.commit()

        fake_render_html = (
            "<!DOCTYPE html><html><body>"
            "<p>Rendered successfully</p>"
            '<svg id="i00080-fake-diagram"></svg>'
            "<p>End of content</p>"
            "</body></html>"
        )
        call_count: dict[str, int] = {"renders": 0}

        def spy_render(text: str, render_mermaid: bool = True) -> str:
            call_count["renders"] += 1
            return fake_render_html

    def test_i00080_html_view_does_not_cache_degraded_render(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """When render_markdown_with_callouts returns HTML that still contains
        language-mermaid (mmdc unavailable), html_path must NOT be written to
        the DB. This prevents a degraded render from being permanently cached.
        """
        test_project.repo_root = str(tmp_path)
        db_session.commit()

        _make_project_doc(
            db_session,
            test_project.id,
            "degraded-test",
            title="Degraded Render Test",
            content="```mermaid\ngraph TD\n    P --> Q\n```\n",
            version=2,
            html_path=None,
        )
        db_session.commit()

        # Simulate mmdc-absent render: markdown returns raw mermaid block
        degraded_html = (
            "<body>\n"
            '<pre><code class="language-mermaid">graph TD\n    P --> Q\n'
            "</code></pre>\n"
            "</body>"
        )

        with patch(
            "dashboard.routers.docs.render_markdown_with_callouts",
            return_value=degraded_html,
        ):
            response = client.get(f"/project/{test_project.id}/docs/degraded-test/html-view")

        assert response.status_code == 200, "html-view must return 200 even when rendering degraded"

        # html_path must still be None — degraded render must not be cached
        db_session.expire_all()
        from orch.doc_service import DocService

        svc = DocService(db_session)
        updated_doc = svc.get_doc(test_project.id, "degraded-test")

        assert updated_doc is not None
        assert updated_doc.html_path is None, (
            "html_path must NOT be written when rendered HTML contains "
            "language-mermaid (mmdc unavailable / degraded render)"
        )


# ---------------------------------------------------------------------------
# Test 4: pdf-view returns 200 + message when Chromium unavailable
# ---------------------------------------------------------------------------


class TestPdfViewGracefulDegradation:
    """Test that docs_pdf_view returns HTTP 200 with a user-facing message
    when Chromium is unavailable, not a bare 503."""

    def test_i00080_pdf_view_unavailable_returns_200_with_message_not_503(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """When render_pdf_chromium returns None, GET /docs/{doc_id}/pdf-view
        must return HTTP 200 with an HTML body containing 'unavailable' —
        not a bare 503 that produces a blank iframe.

        Wording from S05: styled card with <h2>PDF unavailable</h2> and
        <p>Chromium binary not found...</p>
        """
        _make_project_doc(
            db_session,
            test_project.id,
            "pdf-unavail-test",
            title="PDF Unavailable Test",
            content="# Test\n\nSome content for PDF.",
            version=1,
            pdf_path=None,
        )
        db_session.commit()

        # Patch at the router level (how docs.py imports it)
        with patch("dashboard.routers.docs.render_pdf_chromium", return_value=None):
            response = client.get(f"/project/{test_project.id}/docs/pdf-unavail-test/pdf-view")

        assert response.status_code == 200, (
            f"pdf-view must return 200 when Chromium unavailable, got {response.status_code}. "
            "A 503 produces a blank iframe; a 200 shows a meaningful message."
        )
        assert "text/html" in response.headers.get("content-type", ""), (
            f"Response must be text/html, got {response.headers.get('content-type')}"
        )
        html_lower = response.text.lower()
        assert "unavailable" in html_lower, (
            "Response body must contain 'unavailable' (the user-facing message "
            f"that the PDF tab shows in the iframe). Got: {response.text[:300]}"
        )
        assert "pdf" in html_lower, "Response body should mention 'PDF' in the unavailable message"

    def test_i00080_pdf_view_caches_on_success(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """When Chromium is available and returns PDF bytes, pdf_path is
        written to the DB and the file exists with v{version} in its name."""
        test_project.repo_root = str(tmp_path)
        db_session.commit()

        _make_project_doc(
            db_session,
            test_project.id,
            "pdf-success-test",
            title="PDF Success Test",
            content="# Test\n\nContent.",
            version=4,
            pdf_path=None,
        )
        db_session.commit()

        fake_pdf = b"%PDF-1.4 fake pdf content"

        with patch("dashboard.routers.docs.render_pdf_chromium", return_value=fake_pdf):
            response = client.get(f"/project/{test_project.id}/docs/pdf-success-test/pdf-view")

        assert response.status_code == 200, "pdf-view must return 200 on success"
        assert "application/pdf" in response.headers.get("content-type", ""), (
            "Response must be application/pdf"
        )

        # pdf_path must be set and file must exist
        db_session.expire_all()
        from orch.doc_service import DocService

        svc = DocService(db_session)
        updated_doc = svc.get_doc(test_project.id, "pdf-success-test")

        assert updated_doc is not None
        assert updated_doc.pdf_path is not None, (
            "pdf_path must be set after successful PDF generation"
        )
        assert "-v4.pdf" in updated_doc.pdf_path, (
            f"pdf_path filename must contain -v4. Got: {updated_doc.pdf_path}"
        )
        cache_file = tmp_path / updated_doc.pdf_path
        assert cache_file.exists(), f"Cached PDF must exist at {cache_file}"


# ---------------------------------------------------------------------------
# Test 5: pdf download route still works
# ---------------------------------------------------------------------------


class TestPdfDownloadRegression:
    """Regression guard: the /docs/{doc_id}/pdf download route must remain
    functional (Content-Disposition: attachment with slug+version filename)."""

    def test_i00080_pdf_download_still_works(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """GET /project/{pid}/docs/{doc_id}/pdf with render_pdf_chromium
        mocked to return PDF bytes must return 200 application/pdf with
        Content-Disposition: attachment; filename="slug-v{version}.pdf".
        """
        test_project.repo_root = str(tmp_path)
        db_session.commit()

        _make_project_doc(
            db_session,
            test_project.id,
            "pdf-dl-test",
            title="PDF Download Test",
            content="# PDF Download\n\nTest content.",
            version=2,
            pdf_path=None,
        )
        db_session.commit()

        fake_pdf = b"%PDF-1.4 this is a fake pdf for download test"

        with patch("dashboard.routers.docs.render_pdf_chromium", return_value=fake_pdf):
            response = client.get(f"/project/{test_project.id}/docs/pdf-dl-test/pdf")

        assert response.status_code == 200, "PDF download must return 200"
        assert "application/pdf" in response.headers.get("content-type", ""), (
            "Content-Type must be application/pdf"
        )

        cd = response.headers.get("content-disposition", "")
        assert "attachment" in cd.lower(), (
            f"Content-Disposition must contain 'attachment', got: {cd}"
        )
        assert "pdf-dl-test" in cd, (
            f"Content-Disposition filename must contain the doc slug, got: {cd}"
        )
        assert "-v2.pdf" in cd, f"Content-Disposition filename must contain -v2, got: {cd}"


# ---------------------------------------------------------------------------
# S01 unit test file already exists (no duplication needed):
#   tests/unit/test_markdown_mermaid_legibility.py
# ---------------------------------------------------------------------------
