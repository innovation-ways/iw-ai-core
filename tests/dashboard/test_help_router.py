"""Full coverage tests for GET /_help/{slug}.

Uses FastAPI TestClient with testcontainer DB session override.
All 22 known slugs are parametrised; edge cases cover path traversal,
regex violations, and HTTP method restrictions.
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


# ---------------------------------------------------------------------------
# All 22 slugs from the F-00080 allow-list (derived from fragment files on disk).
# Order matches the design doc for traceability.
# ---------------------------------------------------------------------------
ALL_SLUGS = [
    "projects",
    "queue",
    "history",
    "batches",
    "batch_detail",
    "item_detail",
    "jobs",
    "job_detail",
    "code",
    "docs",
    "research",
    "tests",
    "quality",
    "search",
    "status",
    "worktrees",
    "containers",
    "all_active",
    "config",
    "keep_alive",
    "coverage",
    "running",
]

# ---------------------------------------------------------------------------
# Mandatory heading substrings every fragment must contain (plain substrings).
# ---------------------------------------------------------------------------
MANDATORY_HEADINGS = [
    "What is this page?",
    "What can I do here?",
    "Vocabulary",
    "Take the 30-second tour",
]


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


class TestHelpFragmentEndpoint:
    """Tests for GET /_help/{slug}."""

    @pytest.mark.parametrize("slug", ALL_SLUGS)
    def test_known_slug_returns_200_with_correct_headings(
        self, client: TestClient, slug: str
    ) -> None:
        """Every known slug returns 200, text/html, and all 4 mandatory headings."""
        resp = client.get(f"/_help/{slug}")
        assert resp.status_code == 200, f"slug={slug!r} should return 200"
        assert resp.headers["content-type"].startswith("text/html"), (
            f"slug={slug!r} content-type should be text/html"
        )
        for heading in MANDATORY_HEADINGS:
            assert heading in resp.text, (
                f"slug={slug!r} fragment missing required heading: {heading!r}"
            )

    def test_unknown_slug_returns_404(self, client: TestClient) -> None:
        """An slug not in the allow-list returns 404."""
        resp = client.get("/_help/does-not-exist")
        assert resp.status_code == 404

    @pytest.mark.parametrize(
        "path",
        [
            "/_help/../etc/passwd",
            "/_help/..%2Fetc%2Fpasswd",
            "/_help/UPPERCASE",
            "/_help/has%20spaces",
            "/_help/123-leading-digit",
        ],
    )
    def test_invalid_slug_returns_404(self, client: TestClient, path: str) -> None:
        """Path traversal, uppercase, spaces, and leading-digit slugs all return 404."""
        resp = client.get(path)
        assert resp.status_code == 404, f"path={path!r} should return 404"

    def test_empty_slug_returns_404(self, client: TestClient) -> None:
        """GET /_help/ with no slug segment returns 404 (route does not match)."""
        resp = client.get("/_help/")
        assert resp.status_code == 404

    def test_slug_too_long_returns_404(self, client: TestClient) -> None:
        """A 33-char slug exceeds the regex {0,31} quantifier and returns 404."""
        long_slug = "a" * 33
        resp = client.get(f"/_help/{long_slug}")
        assert resp.status_code == 404

    def test_query_string_is_ignored(self, client: TestClient) -> None:
        """A query string on a valid slug does not affect routing and returns 200."""
        resp = client.get("/_help/queue?foo=bar&baz=qux")
        assert resp.status_code == 200

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("post", "/_help/queue"),
            ("put", "/_help/queue"),
            ("delete", "/_help/queue"),
            ("patch", "/_help/queue"),
        ],
    )
    def test_methods_other_than_get_return_405(
        self, client: TestClient, method: str, path: str
    ) -> None:
        """POST/PUT/DELETE/PATCH on /_help/{slug} returns 405 Method Not Allowed."""
        resp = getattr(client, method)(path)
        assert resp.status_code == 405, (
            f"{method.upper()} {path} should return 405, got {resp.status_code}"
        )


@pytest.mark.parametrize("slug", ["queue", "batches", "status", "code"])
def test_help_fragment_docs_link_points_to_system_docs(client: TestClient, slug: str) -> None:
    """The 'Open full docs' link in help fragments uses /system/docs/ not /docs/."""
    resp = client.get(f"/_help/{slug}")
    assert resp.status_code == 200
    # Must contain a /system/docs/ href
    assert 'href="/system/docs/' in resp.text, (
        f'slug={slug!r} fragment should contain href="/system/docs/..."; '
        f"first 500 chars: {resp.text[:500]}"
    )
    # Must not contain the old broken /docs/ href
    assert 'href="/docs/' not in resp.text, (
        f"slug={slug!r} fragment still contains old broken /docs/ href"
    )
    # Must not contain /orch/ href
    assert 'href="/orch/' not in resp.text, f"slug={slug!r} fragment still contains /orch/ href"
