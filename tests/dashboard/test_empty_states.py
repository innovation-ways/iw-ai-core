"""Empty-state rendering test for F-00080 list views.

Only tests pages that use the empty_state macro in their page template itself.
Pages that use htmx fragment loading (jobs, quality, tests, worktrees) do NOT
render the macro from the page template — the fragment shows plain text when
empty. These are excluded from this test; their empty behavior is verified by
the fragment smoke tests (separate concern).

Each test renders one page via TestClient and asserts the response HTML
contains: data-empty-state="<slug>", an <h3>, a <p>, and a primary CTA <a>.

I-00079: also verifies that primary CTA hrefs resolve to HTTP 200 and do not
carry the stale /docs/<name>.md form (which 404s — docs live at /system/docs/).
"""

from __future__ import annotations

import os
import re
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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


def _assert_empty_state_markers(html: str, slug: str) -> None:
    """Assert the four required markers are present in rendered HTML."""
    assert f'data-empty-state="{slug}"' in html, (
        f"slug={slug!r}: expected data-empty-state attribute not found in HTML"
    )
    assert "<h3" in html, f"slug={slug!r}: expected <h3> heading not found in HTML"
    assert "<p" in html, f"slug={slug!r}: expected <p> body not found in HTML"
    assert 'class="empty-state__cta-primary"' in html, (
        f"slug={slug!r}: expected primary CTA link not found in HTML"
    )


class TestEmptyStateRendering:
    """Assert each list view renders the empty_state macro markers."""

    def test_queue_empty_state(self, client: TestClient, test_project) -> None:
        """GET /project/{id}/queue with no items renders empty_state markers."""
        resp = client.get(f"/project/{test_project.id}/queue")
        assert resp.status_code == 200
        _assert_empty_state_markers(resp.text, "queue")

    def test_batches_empty_state(self, client: TestClient, test_project) -> None:
        """GET /project/{id}/batches with no batches renders empty_state markers."""
        resp = client.get(f"/project/{test_project.id}/batches")
        assert resp.status_code == 200
        _assert_empty_state_markers(resp.text, "batches")

    def test_history_empty_state(self, client: TestClient, test_project) -> None:
        """GET /project/{id}/history with no items renders empty_state markers."""
        resp = client.get(f"/project/{test_project.id}/history")
        assert resp.status_code == 200
        _assert_empty_state_markers(resp.text, "history")

    def test_research_empty_state(self, client: TestClient, test_project) -> None:
        """GET /project/{id}/research with no items renders empty_state markers."""
        resp = client.get(f"/project/{test_project.id}/research")
        assert resp.status_code == 200
        _assert_empty_state_markers(resp.text, "research")

    def test_docs_empty_state(self, client: TestClient, test_project) -> None:
        """GET /project/{id}/docs with no docs renders empty_state markers."""
        resp = client.get(f"/project/{test_project.id}/docs")
        assert resp.status_code == 200
        _assert_empty_state_markers(resp.text, "docs")

    def test_all_active_empty_state(self, client: TestClient) -> None:
        """GET /system/all-active with no active items renders empty_state markers."""
        resp = client.get("/system/all-active")
        assert resp.status_code == 200
        _assert_empty_state_markers(resp.text, "all_active")


def _primary_hrefs(html: str) -> list[str]:
    """Return every empty-state primary CTA href in the rendered HTML."""
    return re.findall(r'<a\s+href="([^"]+)"\s+class="empty-state__cta-primary"', html)


class TestEmptyStateHrefResolves:
    """I-00079: empty-state primary CTA hrefs must resolve to HTTP 200.

    Pre-fix: href == '/docs/<Name>.md' → GET returns 404.
    Post-fix: href == '/system/docs/<key>' → GET returns 200.
    """

    def test_i00079_queue_empty_state_cta_resolves(self, client: TestClient, test_project) -> None:
        """The 'How to design an item →' CTA must NOT 404.

        The queue page has two empty-state blocks (approved-items + drafts); both
        CTAs must be checked.  Pre-fix: href == '/docs/IW_AI_Core_CLI_Spec.md' → 404.
        Post-fix: href == '/system/docs/IW_AI_Core_CLI_Spec#iw-approve' → 200.
        """
        resp = client.get(f"/project/{test_project.id}/queue")
        assert resp.status_code == 200
        hrefs = _primary_hrefs(resp.text)
        assert hrefs, "queue empty state must render a primary CTA"
        for href in hrefs:
            # semantic: the broken pattern must be gone
            assert not href.startswith("/docs/"), f"stale bare /docs/ link: {href}"
            assert ".md" not in href.split("#")[0], f"stale .md suffix in link: {href}"
            # semantic: the link must actually resolve
            target = href.split("#")[0]
            followed = client.get(target)
            assert followed.status_code == 200, f"empty-state CTA {href!r} → {followed.status_code}"
        # be explicit about the expected destination
        assert any(h.startswith("/system/docs/IW_AI_Core_CLI_Spec") for h in hrefs)

    def test_i00079_history_empty_state_cta_resolves(
        self, client: TestClient, test_project
    ) -> None:
        """The 'How execution works →' CTA must NOT 404.

        Pre-fix: href == '/docs/IW_AI_Core_Architecture.md' → 404.
        Post-fix: href == '/system/docs/IW_AI_Core_Architecture' → 200.
        """
        resp = client.get(f"/project/{test_project.id}/history")
        assert resp.status_code == 200
        hrefs = _primary_hrefs(resp.text)
        assert hrefs, "history empty state must render a primary CTA"
        for href in hrefs:
            assert not href.startswith("/docs/"), f"stale bare /docs/ link: {href}"
            assert ".md" not in href.split("#")[0], f"stale .md suffix in link: {href}"
            target = href.split("#")[0]
            followed = client.get(target)
            assert followed.status_code == 200, f"empty-state CTA {href!r} → {followed.status_code}"
        assert any(h.startswith("/system/docs/IW_AI_Core_Architecture") for h in hrefs)

    def test_i00079_batches_empty_state_cta_resolves(
        self, client: TestClient, test_project
    ) -> None:
        """The 'About batches →' CTA must NOT 404.

        Pre-fix: href == '/docs/IW_AI_Core_Daemon_Design.md#batches' → 404.
        Post-fix: href == '/system/docs/IW_AI_Core_Daemon_Design#batches' → 200.
        """
        resp = client.get(f"/project/{test_project.id}/batches")
        assert resp.status_code == 200
        hrefs = _primary_hrefs(resp.text)
        assert hrefs, "batches empty state must render a primary CTA"
        for href in hrefs:
            assert not href.startswith("/docs/"), f"stale bare /docs/ link: {href}"
            assert ".md" not in href.split("#")[0], f"stale .md suffix in link: {href}"
            target = href.split("#")[0]
            followed = client.get(target)
            assert followed.status_code == 200, f"empty-state CTA {href!r} → {followed.status_code}"
        assert any(h.startswith("/system/docs/IW_AI_Core_Daemon_Design") for h in hrefs)

    def test_i00079_all_active_empty_state_cta_resolves(self, client: TestClient) -> None:
        """The 'Daemon overview →' CTA must NOT 404.

        Pre-fix: href == '/docs/IW_AI_Core_Daemon_Design.md' → 404.
        Post-fix: href == '/system/docs/IW_AI_Core_Daemon_Design' → 200.
        """
        resp = client.get("/system/all-active")
        assert resp.status_code == 200
        hrefs = _primary_hrefs(resp.text)
        assert hrefs, "all_active empty state must render a primary CTA"
        for href in hrefs:
            assert not href.startswith("/docs/"), f"stale bare /docs/ link: {href}"
            assert ".md" not in href.split("#")[0], f"stale .md suffix in link: {href}"
            target = href.split("#")[0]
            followed = client.get(target)
            assert followed.status_code == 200, f"empty-state CTA {href!r} → {followed.status_code}"
        assert any(h.startswith("/system/docs/IW_AI_Core_Daemon_Design") for h in hrefs)

    def test_i00079_docs_library_empty_state_cta_resolves(
        self, client: TestClient, test_project
    ) -> None:
        """The 'Doc catalogue →' CTA must NOT 404.

        Pre-fix: href == '/docs/implementation/00_INDEX.md' → 404.
        Post-fix: href == '/system/docs/implementation/00_INDEX' → 200.
        This page exercises CR-00044's subdirectory doc serving.
        """
        resp = client.get(f"/project/{test_project.id}/docs")
        assert resp.status_code == 200
        hrefs = _primary_hrefs(resp.text)
        assert hrefs, "docs library empty state must render a primary CTA"
        for href in hrefs:
            assert not href.startswith("/docs/"), f"stale bare /docs/ link: {href}"
            assert ".md" not in href.split("#")[0], f"stale .md suffix in link: {href}"
            target = href.split("#")[0]
            followed = client.get(target)
            assert followed.status_code == 200, f"empty-state CTA {href!r} → {followed.status_code}"
        assert any(h.startswith("/system/docs/implementation/00_INDEX") for h in hrefs)

    def test_i00079_research_library_empty_state_cta_resolves(
        self, client: TestClient, test_project
    ) -> None:
        """The 'Open the catalogue →' CTA must NOT 404.

        Pre-fix: href == '/docs/implementation/00_INDEX.md' → 404.
        Post-fix: href == '/system/docs/implementation/00_INDEX' → 200.
        """
        resp = client.get(f"/project/{test_project.id}/research")
        assert resp.status_code == 200
        hrefs = _primary_hrefs(resp.text)
        assert hrefs, "research library empty state must render a primary CTA"
        for href in hrefs:
            assert not href.startswith("/docs/"), f"stale bare /docs/ link: {href}"
            assert ".md" not in href.split("#")[0], f"stale .md suffix in link: {href}"
            target = href.split("#")[0]
            followed = client.get(target)
            assert followed.status_code == 200, f"empty-state CTA {href!r} → {followed.status_code}"
        assert any(h.startswith("/system/docs/implementation/00_INDEX") for h in hrefs)


class TestI00079RegressionPrevention:
    """Structural guards against the entire class of /docs/*.md link bugs recurring."""

    def test_i00079_no_legacy_docs_md_links_in_templates(self) -> None:
        """No template file may contain a primary_href with a /docs/*.md target.

        This is the regression-prevention test: a regex scan across all HTML templates
        ensures no developer can accidentally reintroduce the broken /docs/<name>.md form.
        """
        templates_dir = Path(__file__).parent.parent.parent / "dashboard" / "templates"
        legacy_pattern = re.compile(r"/docs/[A-Za-z0-9_./-]*\.md")
        findings: list[str] = []
        for filepath in templates_dir.rglob("*.html"):
            content = filepath.read_text(encoding="utf-8")
            if 'primary_href="/docs/' in content:
                findings.append(f'{filepath}: contains primary_href="/docs/..."')
            for match in legacy_pattern.finditer(content):
                pos = match.start()
                findings.append(f"{filepath}: contains legacy /docs/... link at position {pos}")
        assert not findings, "Legacy /docs/*.md links found:\n" + "\n".join(findings)

    def test_i00079_empty_state_cta_agrees_with_help_doc_map(
        self, client: TestClient, test_project
    ) -> None:
        """Empty-state CTA hrefs and help.py's _SLUG_TO_DOC must both point at real docs.

        For Queue, Batches, All Active: both surfaces point at the same doc.
        For History: the design records a documented divergence — the empty-state CTA
        intentionally points at IW_AI_Core_Architecture (matching its label) while
        _SLUG_TO_DOC["history"] points at IW_AI_Core_CLI_Spec.  The invariant we check
        is that BOTH start with /system/docs/ and have no .md suffix — catching future
        drift where one or both drift back to a broken form.
        """
        from dashboard.routers.help import _SLUG_TO_DOC

        pages_with_help_and_empty_state: list[tuple[str, str, str]] = [
            ("queue", f"/project/{test_project.id}/queue", "queue"),
            ("history", f"/project/{test_project.id}/history", "history"),
            ("batches", f"/project/{test_project.id}/batches", "batches"),
            ("all_active", "/system/all-active", "all_active"),
        ]

        for slug, path, _empty_state_slug in pages_with_help_and_empty_state:
            resp = client.get(path)
            assert resp.status_code == 200, f"page {path} must load"
            hrefs = _primary_hrefs(resp.text)
            assert hrefs, f"page {path} must render a primary CTA for slug {slug!r}"
            cta_path = hrefs[0].split("#")[0]
            help_doc = _SLUG_TO_DOC.get(slug, "").split("#")[0]
            # Both must start with /system/docs/ and have no .md suffix
            assert cta_path.startswith("/system/docs/"), (
                f"[{slug}] empty-state CTA does not start with /system/docs/: {cta_path!r}"
            )
            assert not cta_path.endswith(".md"), (
                f"[{slug}] empty-state CTA ends with .md: {cta_path!r}"
            )
            assert help_doc.startswith("/system/docs/"), (
                f"[{slug}] help _SLUG_TO_DOC does not start with /system/docs/: {help_doc!r}"
            )
            assert not help_doc.endswith(".md"), (
                f"[{slug}] help _SLUG_TO_DOC ends with .md: {help_doc!r}"
            )
