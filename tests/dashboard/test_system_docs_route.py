"""Tests for GET /system/docs/{doc_slug} route.

Validates the docs-view route: correct slugs render HTML, invalid slugs
return 404, and path-traversal attempts are blocked.
"""

from __future__ import annotations

import os
from collections.abc import Generator
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


class TestSystemDocsRoute:
    """Tests for GET /system/docs/{doc_slug}."""

    def test_valid_doc_slug_returns_200(self, client: TestClient) -> None:
        """A valid doc slug (IW_AI_Core_Daemon_Design) returns 200 with HTML content."""
        resp = client.get("/system/docs/IW_AI_Core_Daemon_Design")
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}"
        assert resp.headers["content-type"].startswith("text/html")
        # The response must contain rendered HTML, not raw markdown
        # Check for prose-doc class which wraps the rendered content
        assert "prose-doc" in resp.text, (
            f"response should contain .prose-doc wrapper; first 500 chars: {resp.text[:500]}"
        )

    def test_valid_doc_slug_has_prose_doc_class(self, client: TestClient) -> None:
        """The rendered doc contains the .prose-doc container."""
        resp = client.get("/system/docs/IW_AI_Core_Daemon_Design")
        assert resp.status_code == 200
        assert "prose-doc" in resp.text

    def test_valid_doc_slug_shows_doc_title(self, client: TestClient) -> None:
        """The page title is derived from the doc slug with underscores replaced by spaces."""
        resp = client.get("/system/docs/IW_AI_Core_Architecture")
        assert resp.status_code == 200
        assert "IW AI Core Architecture" in resp.text

    def test_nonexistent_slug_returns_404(self, client: TestClient) -> None:
        """A slug that doesn't match any .md file in docs/ returns 404."""
        resp = client.get("/system/docs/This_Doc_Does_Not_Exist")
        assert resp.status_code == 404

    def test_path_traversal_returns_404(self, client: TestClient) -> None:
        """Path traversal via ..%2F..%2Fetc%2Fpasswd is blocked by regex and returns 404."""
        resp = client.get("/system/docs/..%2F..%2Fetc%2Fpasswd")
        assert resp.status_code == 404

    def test_path_traversal_raw_returns_404(self, client: TestClient) -> None:
        """Path traversal via literal ../ is blocked and returns 404."""
        resp = client.get("/system/docs/../../../etc/passwd")
        assert resp.status_code == 404

    def test_special_chars_in_slug_returns_404(self, client: TestClient) -> None:
        """Slugs with special characters (/, \\, spaces) return 404."""
        resp = client.get("/system/docs/hack<script>")
        assert resp.status_code == 404

    def test_empty_slug_returns_404(self, client: TestClient) -> None:
        """GET /system/docs/ with no slug segment returns 404."""
        resp = client.get("/system/docs/")
        assert resp.status_code == 404

    def test_methods_other_than_get_return_405(self, client: TestClient) -> None:
        """POST/PUT/DELETE/PATCH on /system/docs/{slug} returns 405 Method Not Allowed."""
        for method in ("post", "put", "delete", "patch"):
            resp = getattr(client, method)("/system/docs/IW_AI_Core_Daemon_Design")
            assert resp.status_code == 405, (
                f"{method.upper()} should return 405, got {resp.status_code}"
            )

    def test_doc_slug_from_help_py_mapping_queue(self, client: TestClient) -> None:
        """The queue help slug maps to IW_AI_Core_CLI_Spec with anchor #iw-approve."""
        # The route only knows doc_slug; the fragment anchor is handled client-side
        # so we just check the doc renders successfully
        resp = client.get("/system/docs/IW_AI_Core_CLI_Spec")
        assert resp.status_code == 200
        # Should contain heading with id="iw-approve" from the toc extension
        assert "iw-approve" in resp.text

    def test_multiple_valid_slugs_work(self, client: TestClient) -> None:
        """All slugs referenced in _SLUG_TO_DOC mapping should return 200."""
        # These are the slugs referenced in the help.py mapping
        doc_names = [
            "IW_AI_Core_Daemon_Design",
            "IW_AI_Core_Architecture",
            "IW_AI_Core_Tech_Stack",
            "IW_AI_Core_Dashboard_Design",
            "IW_AI_Core_CLI_Spec",
            "IW_AI_Core_DB_Setup",
            "IW_AI_Core_Worktree_Isolation",
        ]
        for doc_name in doc_names:
            resp = client.get(f"/system/docs/{doc_name}")
            assert resp.status_code == 200, f"{doc_name} should return 200, got {resp.status_code}"


class TestSystemDocsSlugMapping:
    """Tests for _SLUG_TO_DOC mapping correctness (T5, T6)."""

    def test_slug_to_doc_all_values_point_to_system_docs(self) -> None:
        """Every URL in _SLUG_TO_DOC starts with /system/docs/."""
        from dashboard.routers.help import _SLUG_TO_DOC

        for slug, url in _SLUG_TO_DOC.items():
            assert url.startswith("/system/docs/"), (
                f"slug={slug!r} maps to bad URL: {url!r} (expected prefix /system/docs/)"
            )

    def test_slug_to_doc_covers_all_help_slugs(self) -> None:
        """_SLUG_TO_DOC contains all 22 known help partial slugs."""
        from dashboard.routers.help import _SLUG_TO_DOC

        expected_slugs = {
            "all_active",
            "batch_detail",
            "batches",
            "code",
            "config",
            "containers",
            "coverage",
            "docs",
            "history",
            "item_detail",
            "job_detail",
            "jobs",
            "keep_alive",
            "projects",
            "quality",
            "queue",
            "research",
            "running",
            "search",
            "status",
            "tests",
            "worktrees",
        }
        missing = expected_slugs - set(_SLUG_TO_DOC.keys())
        assert not missing, f"Missing slugs in _SLUG_TO_DOC: {missing}"

    def test_toc_extension_generates_heading_ids(self, client: TestClient) -> None:
        """The toc extension generates id attributes on headings."""
        resp = client.get("/system/docs/IW_AI_Core_Architecture")
        assert resp.status_code == 200
        # toc extension creates id attributes like id="heading-name"
        assert 'id="' in resp.text, "rendered HTML should contain id= attributes from toc extension"
