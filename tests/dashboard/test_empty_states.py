"""Empty-state rendering test for F-00080 list views.

Only tests pages that use the empty_state macro in their page template itself.
Pages that use htmx fragment loading (jobs, quality, tests, worktrees) do NOT
render the macro from the page template — the fragment shows plain text when
empty. These are excluded from this test; their empty behavior is verified by
the fragment smoke tests (separate concern).

Each test renders one page via TestClient and asserts the response HTML
contains: data-empty-state="<slug>", an <h3>, a <p>, and a primary CTA <a>.
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
