"""Integration tests for F-00040 enhanced diff API endpoints.

Tests the three new endpoints:
- GET  /project/{id}/api/docs/{doc_id}/diff/sections     — JSON section-level diff
- GET  /project/{id}/api/docs/{doc_id}/diff/sections/{section_name} — HTML single-section diff
- GET  /project/{id}/api/docs/{doc_id}/diff/ai-summary  — 204 stub for F-00025

Also verifies the original /diff endpoint still returns HTML unified diff.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    ProjectDocVersion,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> TestClient:
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db():
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


def _make_project(db: Session, project_id: str = "test-proj-f00040") -> Project:
    project = Project(
        id=project_id,
        display_name="Test Project F-00040",
        repo_root="/repos/test",
        config={},
    )
    db.add(project)
    db.flush()
    return project


def _make_doc(
    db: Session,
    project_id: str,
    doc_id: str = "test-doc",
    title: str = "Test Document",
    content: str = (
        "# Test Document\n\n## Purpose\nSome content here.\n\n## Architecture\nMore content."
    ),
) -> ProjectDoc:
    doc = ProjectDoc(
        id=f"{project_id}:{doc_id}",
        project_id=project_id,
        doc_id=doc_id,
        title=title,
        slug=doc_id.replace("_", "-"),
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.draft,
        audience=["developers"],
        source_paths=["src/test.rs"],
        content=content,
    )
    db.add(doc)
    db.flush()
    return doc


def _add_version(db: Session, doc: ProjectDoc, version_num: int, content: str) -> None:
    ver = ProjectDocVersion(
        doc_id=doc.id,
        version=version_num,
        content=content,
        trigger_reason="test",
    )
    db.add(ver)
    db.flush()


# ---------------------------------------------------------------------------
# GET /project/{id}/api/docs/{doc_id}/diff/sections — JSON section diff
# ---------------------------------------------------------------------------


class TestDiffSectionsEndpoint:
    def test_sections_endpoint_returns_json(self, client: TestClient, db_session: Session) -> None:
        """GET /diff/sections returns 200 JSON with section data."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-sections-1",
            content="# Doc\n\n## Purpose\nOld purpose content.\n",
        )
        _add_version(db_session, doc, 1, "# Doc\n\n## Purpose\nOld purpose content.\n")
        _add_version(
            db_session,
            doc,
            2,
            "# Doc\n\n## Purpose\nNew purpose content.\n## Usage\nNew section added.\n",
        )

        resp = client.get(f"/project/{proj.id}/api/docs/doc-sections-1/diff/sections?v1=1&v2=2")
        assert resp.status_code == 200

        data = resp.json()
        assert "sections" in data
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) == 2

        section = data["sections"][0]
        assert "section_name" in section
        assert "status" in section
        assert "unified_diff" in section
        assert section["status"] == "changed"

    def test_sections_endpoint_version_numbers_preserved(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Response includes correct version_old and version_new values."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-sections-2",
            content="# Doc\n\n## Purpose\nOld.\n",
        )
        _add_version(db_session, doc, 3, "# Doc\n\n## Purpose\nOld.\n")
        _add_version(db_session, doc, 7, "# Doc\n\n## Purpose\nNew.\n")

        resp = client.get(f"/project/{proj.id}/api/docs/doc-sections-2/diff/sections?v1=3&v2=7")
        assert resp.status_code == 200

        data = resp.json()
        assert data["version_old"] == 3
        assert data["version_new"] == 7

    def test_sections_added_status(self, client: TestClient, db_session: Session) -> None:
        """New section in v2 shows status 'added'."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-sections-3",
            content="# Doc\n\n## Purpose\nContent.\n",
        )
        _add_version(db_session, doc, 1, "# Doc\n\n## Purpose\nContent.\n")
        _add_version(
            db_session, doc, 2, "# Doc\n\n## Purpose\nContent.\n## Usage\nAdded section.\n"
        )

        resp = client.get(f"/project/{proj.id}/api/docs/doc-sections-3/diff/sections?v1=1&v2=2")
        assert resp.status_code == 200

        data = resp.json()
        statuses = {s["section_name"]: s["status"] for s in data["sections"]}
        assert statuses["Usage"] == "added"
        assert statuses["Purpose"] == "unchanged"

    def test_sections_removed_status(self, client: TestClient, db_session: Session) -> None:
        """Section removed in v2 shows status 'removed'."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-sections-4",
            content="# Doc\n\n## Purpose\nContent.\n## Deprecated\nWill be removed.\n",
        )
        _add_version(
            db_session,
            doc,
            1,
            "# Doc\n\n## Purpose\nContent.\n## Deprecated\nWill be removed.\n",
        )
        _add_version(db_session, doc, 2, "# Doc\n\n## Purpose\nContent.\n")

        resp = client.get(f"/project/{proj.id}/api/docs/doc-sections-4/diff/sections?v1=1&v2=2")
        assert resp.status_code == 200

        data = resp.json()
        statuses = {s["section_name"]: s["status"] for s in data["sections"]}
        assert statuses["Deprecated"] == "removed"
        assert statuses["Purpose"] == "unchanged"


# ---------------------------------------------------------------------------
# GET /project/{id}/api/docs/{doc_id}/diff/sections/{section_name} — HTML single section
# ---------------------------------------------------------------------------


class TestDiffSectionsDetailEndpoint:
    def test_sections_single_section_returns_html(
        self, client: TestClient, db_session: Session
    ) -> None:
        """GET /diff/sections/{section_name} returns 200 HTML for a known section."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-detail-1",
            content="# Doc\n\n## Purpose\nOld purpose content.\n",
        )
        _add_version(db_session, doc, 1, "# Doc\n\n## Purpose\nOld purpose content.\n")
        _add_version(db_session, doc, 2, "# Doc\n\n## Purpose\nNew purpose content.\n")

        resp = client.get(
            f"/project/{proj.id}/api/docs/doc-detail-1/diff/sections/Purpose?v1=1&v2=2"
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        html = resp.text
        assert len(html) > 0

    def test_sections_single_section_contains_diff_content(
        self, client: TestClient, db_session: Session
    ) -> None:
        """HTML body contains diff content for the named section."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-detail-2",
            content="# Doc\n\n## Purpose\nOld content here.\n",
        )
        _add_version(db_session, doc, 1, "# Doc\n\n## Purpose\nOld content here.\n")
        _add_version(db_session, doc, 2, "# Doc\n\n## Purpose\nNew content here.\n")

        resp = client.get(
            f"/project/{proj.id}/api/docs/doc-detail-2/diff/sections/Purpose?v1=1&v2=2"
        )
        assert resp.status_code == 200
        html = resp.text
        assert any(marker in html for marker in ["+", "-", "diff-line-added", "diff-line-removed"])

    def test_sections_single_section_unknown_returns_404(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Unknown section_name returns 404."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-detail-3",
            content="# Doc\n\n## Purpose\nContent.\n",
        )
        _add_version(db_session, doc, 1, "# Doc\n\n## Purpose\nContent.\n")
        _add_version(db_session, doc, 2, "# Doc\n\n## Purpose\nContent v2.\n")

        resp = client.get(
            f"/project/{proj.id}/api/docs/doc-detail-3/diff/sections/NonExistent?v1=1&v2=2"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /project/{id}/api/docs/{doc_id}/diff/ai-summary — 204 stub
# ---------------------------------------------------------------------------


class TestDiffAiSummaryEndpoint:
    def test_ai_summary_returns_204_with_xstub_header(
        self, client: TestClient, db_session: Session
    ) -> None:
        """GET /diff/ai-summary returns 204 with X-Stub header."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-ai-summary-1",
            content="# Doc\n\n## Purpose\nContent.\n",
        )
        _add_version(db_session, doc, 1, "# Doc\n\n## Purpose\nContent.\n")
        _add_version(db_session, doc, 2, "# Doc\n\n## Purpose\nContent v2.\n")

        resp = client.get(f"/project/{proj.id}/api/docs/doc-ai-summary-1/diff/ai-summary?v1=1&v2=2")
        assert resp.status_code == 204
        assert resp.headers.get("X-Stub") == "waiting-for-F-00025"

    def test_ai_summary_no_body(self, client: TestClient, db_session: Session) -> None:
        """204 response has no body."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-ai-summary-2",
            content="# Doc\n\n## Purpose\nContent.\n",
        )
        _add_version(db_session, doc, 1, "# Doc\n\n## Purpose\nContent.\n")
        _add_version(db_session, doc, 2, "# Doc\n\n## Purpose\nContent v2.\n")

        resp = client.get(f"/project/{proj.id}/api/docs/doc-ai-summary-2/diff/ai-summary?v1=1&v2=2")
        assert resp.status_code == 204
        assert resp.text == ""


# ---------------------------------------------------------------------------
# Validation: v1 >= v2 → 422, non-existent version → 404
# ---------------------------------------------------------------------------


class TestDiffValidation:
    def test_v1_gte_v2_returns_422_on_sections_endpoints(
        self, client: TestClient, db_session: Session
    ) -> None:
        """v1 >= v2 returns 422 on /diff/sections and /diff/sections/{name} endpoints.

        Note: /diff/ai-summary is a stub that returns 204 regardless of v1/v2 values.
        """
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-validate-1",
            content="# Doc\n\n## Purpose\nContent.\n",
        )
        _add_version(db_session, doc, 1, "# Doc\n\n## Purpose\nContent.\n")
        _add_version(db_session, doc, 2, "# Doc\n\n## Purpose\nContent v2.\n")

        for endpoint in [
            f"/project/{proj.id}/api/docs/doc-validate-1/diff/sections?v1=2&v2=1",
            f"/project/{proj.id}/api/docs/doc-validate-1/diff/sections/Purpose?v1=2&v2=1",
        ]:
            resp = client.get(endpoint)
            assert resp.status_code == 422, f"Expected 422 for {endpoint}, got {resp.status_code}"

    def test_ai_summary_stub_ignores_v1_v2_validation(
        self, client: TestClient, db_session: Session
    ) -> None:
        """The /diff/ai-summary stub returns 204 even when v1 >= v2 (no validation)."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-validate-ai",
            content="# Doc\n\n## Purpose\nContent.\n",
        )
        _add_version(db_session, doc, 1, "# Doc\n\n## Purpose\nContent.\n")
        _add_version(db_session, doc, 2, "# Doc\n\n## Purpose\nContent v2.\n")

        resp = client.get(f"/project/{proj.id}/api/docs/doc-validate-ai/diff/ai-summary?v1=2&v2=1")
        assert resp.status_code == 204
        assert resp.headers.get("X-Stub") == "waiting-for-F-00025"

    def test_v1_equals_v2_returns_422(self, client: TestClient, db_session: Session) -> None:
        """v1 == v2 also returns 422."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-validate-2",
            content="# Doc\n\n## Purpose\nContent.\n",
        )
        _add_version(db_session, doc, 1, "# Doc\n\n## Purpose\nContent.\n")

        resp = client.get(f"/project/{proj.id}/api/docs/doc-validate-2/diff/sections?v1=1&v2=1")
        assert resp.status_code == 422

    def test_missing_version_returns_404(self, client: TestClient, db_session: Session) -> None:
        """Non-existent version returns 404."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-validate-3",
            content="# Doc\n\n## Purpose\nContent.\n",
        )
        _add_version(db_session, doc, 1, "# Doc\n\n## Purpose\nContent.\n")

        resp = client.get(f"/project/{proj.id}/api/docs/doc-validate-3/diff/sections?v1=1&v2=99")
        assert resp.status_code == 404

    def test_unknown_doc_returns_404_on_sections_endpoints(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Non-existent doc returns 404 on /diff/sections and /diff/sections/{name}."""
        proj = _make_project(db_session)

        for endpoint in [
            f"/project/{proj.id}/api/docs/nonexistent-doc/diff/sections?v1=1&v2=2",
            f"/project/{proj.id}/api/docs/nonexistent-doc/diff/sections/Purpose?v1=1&v2=2",
        ]:
            resp = client.get(endpoint)
            assert resp.status_code == 404, f"Expected 404 for {endpoint}, got {resp.status_code}"

    def test_unknown_doc_ai_summary_stub_returns_204(
        self, client: TestClient, db_session: Session
    ) -> None:
        """The /diff/ai-summary stub returns 204 even for unknown docs (no doc lookup)."""
        proj = _make_project(db_session)

        resp = client.get(f"/project/{proj.id}/api/docs/nonexistent-doc/diff/ai-summary?v1=1&v2=2")
        assert resp.status_code == 204
        assert resp.headers.get("X-Stub") == "waiting-for-F-00025"


# ---------------------------------------------------------------------------
# Original /diff endpoint unchanged
# ---------------------------------------------------------------------------


class TestOriginalDiffEndpoint:
    def test_existing_diff_endpoint_still_returns_html(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Original /diff endpoint still returns HTML unified diff."""
        proj = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=proj.id,
            doc_id="doc-original-diff",
            content="# Doc\n\n## Purpose\nContent.\n",
        )
        _add_version(db_session, doc, 1, "# Doc\n\n## Purpose\nOld content.\n")
        _add_version(db_session, doc, 2, "# Doc\n\n## Purpose\nNew content.\n")

        resp = client.get(f"/project/{proj.id}/api/docs/doc-original-diff/diff?v1=1&v2=2")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        html = resp.text
        assert len(html) > 0
        assert any(marker in html for marker in ["+", "-", "diff-line-added", "diff-line-removed"])
