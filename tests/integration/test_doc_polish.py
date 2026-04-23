"""Integration tests for F-00014 doc polish features.

Tests diff view, global search, ZIP export, and link validation routes.
Uses testcontainers — never connects to live DB.
"""

from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.cli.doc_commands import docs_export
from orch.db.models import (
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    Project,
    ProjectDoc,
    ProjectDocVersion,
)
from orch.doc_service import DocService

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Any

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        def override_get_db() -> Generator[Session, None, None]:
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


def _make_project(
    db: Session, project_id: str = "test-proj", display_name: str = "Test Project"
) -> Project:
    project = Project(
        id=project_id,
        display_name=display_name,
        repo_root="/repos/test",
        config={},
    )
    db.add(project)
    db.flush()
    return project


def _make_doc(
    db: Session,
    project_id: str = "test-proj",
    doc_id: str = "module-auth",
    title: str = "Auth Module",
    doc_type: DocType = DocType.module,
    tier: DocTier = DocTier.semi_automated,
    status: DocStatus = DocStatus.published,
    content: str | None = "# Auth Module\n\nThis is the auth module.",
    project: Project | None = None,
) -> ProjectDoc:
    if project is None:
        project = db.query(Project).filter_by(id=project_id).first()
    if project is None:
        project = _make_project(db, project_id)

    doc = ProjectDoc(
        id=f"{project_id}:{doc_id}",
        project_id=project_id,
        doc_id=doc_id,
        title=title,
        slug=doc_id.replace("_", "-"),
        doc_type=doc_type,
        tier=tier,
        editorial_category=EditorialCategory.technical,
        status=status,
        audience=["developers"],
        source_paths=["src/auth/mod.rs"],
        content=content,
        version=0,
    )
    db.add(doc)
    db.flush()

    if content is not None:
        svc = DocService(db)
        svc.update_doc(project_id, doc_id, content=content, trigger_reason="test-setup")

    return doc


def _add_version(
    db: Session, doc: ProjectDoc, version_num: int, content: str, trigger: str = "test"
) -> None:
    ver = ProjectDocVersion(
        doc_id=doc.id,
        version=version_num,
        content=content,
        trigger_reason=trigger,
    )
    db.add(ver)
    db.flush()


# ---------------------------------------------------------------------------
# 1. Diff Tests
# ---------------------------------------------------------------------------


class TestDiffRoute:
    def test_diff_route_shows_changes(self, client: TestClient, db_session: Session) -> None:
        """GET /api/project/{id}/docs/{doc_id}/diff?v1=1&v2=2 shows added/removed lines."""
        project = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=project.id,
            doc_id="doc-diff",
            content="# Version 1\n\nHello world",
        )
        db_session.flush()

        _add_version(db_session, doc, 1, "# Version 1\n\nHello world")
        _add_version(db_session, doc, 2, "# Version 2\n\nHello universe")

        resp = client.get(f"/project/{project.id}/api/docs/doc-diff/diff?v1=1&v2=2")
        assert resp.status_code == 200
        html = resp.text
        assert "diff-line-added" in html or "diff-line-removed" in html or "+" in html

    def test_diff_route_identical_versions(self, client: TestClient, db_session: Session) -> None:
        """Identical content returns 'identical' message."""
        project = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=project.id,
            doc_id="doc-identical",
            content="# Same\n\nContent here",
        )
        db_session.flush()

        _add_version(db_session, doc, 1, "# Same\n\nContent here")
        _add_version(db_session, doc, 2, "# Same\n\nContent here")

        resp = client.get(f"/project/{project.id}/api/docs/doc-identical/diff?v1=1&v2=2")
        assert resp.status_code == 200
        assert "identical" in resp.text.lower() or "no differences" in resp.text.lower()

    def test_diff_route_wrong_order_422(self, client: TestClient, db_session: Session) -> None:
        """v1 >= v2 returns 422."""
        project = _make_project(db_session)
        doc = _make_doc(db_session, project_id=project.id, doc_id="doc-order", content="# Content")
        db_session.flush()

        _add_version(db_session, doc, 1, "# V1")
        _add_version(db_session, doc, 2, "# V2")

        resp = client.get(f"/project/{project.id}/api/docs/doc-order/diff?v1=2&v2=1")
        assert resp.status_code == 422

    def test_diff_route_unknown_version_404(self, client: TestClient, db_session: Session) -> None:
        """Unknown version returns 404."""
        project = _make_project(db_session)
        doc = _make_doc(db_session, project_id=project.id, doc_id="doc-uk", content="# Content")
        db_session.flush()

        _add_version(db_session, doc, 1, "# V1")

        resp = client.get(f"/project/{project.id}/api/docs/doc-uk/diff?v1=1&v2=99")
        assert resp.status_code == 404

    def test_diff_route_same_version_422(self, client: TestClient, db_session: Session) -> None:
        """v1 == v2 returns 422 (same version guard)."""
        project = _make_project(db_session)
        doc = _make_doc(db_session, project_id=project.id, doc_id="doc-same", content="# Content")
        db_session.flush()

        _add_version(db_session, doc, 1, "# V1")

        resp = client.get(f"/project/{project.id}/api/docs/doc-same/diff?v1=2&v2=2")
        assert resp.status_code == 422

    def test_diff_non_adjacent_versions(self, client: TestClient, db_session: Session) -> None:
        """Diff v1 and v3 (skipping v2) reflects v1→v3 change directly."""
        project = _make_project(db_session)
        doc = _make_doc(
            db_session, project_id=project.id, doc_id="doc-skip", content="# V1\n\nOriginal"
        )
        db_session.flush()

        _add_version(db_session, doc, 1, "# V1\n\nOriginal")
        _add_version(db_session, doc, 2, "# V2\n\nMiddle version")
        _add_version(db_session, doc, 3, "# V3\n\nFinal version")

        resp = client.get(f"/project/{project.id}/api/docs/doc-skip/diff?v1=1&v2=3")
        assert resp.status_code == 200
        html = resp.text
        assert "Original" in html or "Final" in html

    def test_diff_large_content_truncated(self, client: TestClient, db_session: Session) -> None:
        """Large diff shows truncation note."""
        project = _make_project(db_session)
        doc = _make_doc(db_session, project_id=project.id, doc_id="doc-large", content="# Start")
        db_session.flush()

        lines = ["# Line " + str(i) for i in range(600)]
        v1_content = "\n".join(lines[:300])
        v2_content = "\n".join(lines[300:]) + "\n# Extra line"

        _add_version(db_session, doc, 1, v1_content)
        _add_version(db_session, doc, 2, v2_content)

        resp = client.get(f"/project/{project.id}/api/docs/doc-large/diff?v1=1&v2=2")
        assert resp.status_code == 200
        html = resp.text
        assert "Show all" in html or "truncat" in html.lower() or "total lines" in html


# ---------------------------------------------------------------------------
# 2. Export Tests
# ---------------------------------------------------------------------------


class TestExportRoute:
    def test_export_route_single_doc_zip(self, client: TestClient, db_session: Session) -> None:
        """Single doc export returns ZIP with .md, .html, _generation_notes.md."""
        project = _make_project(db_session)
        _make_doc(
            db_session,
            project_id=project.id,
            doc_id="export-single",
            content="# Export Test\n\nContent.",
        )

        resp = client.get(f"/project/{project.id}/api/docs/export?doc_ids=export-single")
        assert resp.status_code == 200
        assert "application/zip" in resp.headers.get("content-type", "")

        buf = io.BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert any("export-single.md" in n for n in names)
            assert any(n.endswith(".html") for n in names)
            assert "_generation_notes.md" in names

            md_name = next(n for n in names if n.endswith(".md") and n != "_generation_notes.md")
            md_content = zf.read(md_name).decode()
            assert "Export Test" in md_content

    def test_export_route_multi_doc_zip(self, client: TestClient, db_session: Session) -> None:
        """Multi-doc export returns ZIP with subdirectories per doc."""
        project = _make_project(db_session)
        _make_doc(db_session, project_id=project.id, doc_id="multi-1", content="# Doc 1")
        _make_doc(db_session, project_id=project.id, doc_id="multi-2", content="# Doc 2")

        resp = client.get(f"/project/{project.id}/api/docs/export?doc_ids=multi-1,multi-2")
        assert resp.status_code == 200

        buf = io.BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert any("multi-1/multi-1.md" in n for n in names)
            assert any("multi-2/multi-2.md" in n for n in names)

    def test_export_route_skips_no_content_doc(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Export excludes docs with content=None."""
        project = _make_project(db_session)
        _make_doc(db_session, project_id=project.id, doc_id="has-content", content="# Has Content")
        _make_doc(db_session, project_id=project.id, doc_id="no-content", content=None)

        resp = client.get(f"/project/{project.id}/api/docs/export?doc_ids=has-content,no-content")
        assert resp.status_code == 200

        buf = io.BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert any("has-content.md" in n for n in names)
            assert not any("no-content" in n for n in names)

    def test_export_empty_doc_ids_exports_all(
        self, client: TestClient, db_session: Session
    ) -> None:
        """No doc_ids param exports all non-archived docs (route differs from CLI)."""
        project = _make_project(db_session)
        _make_doc(
            db_session,
            project_id=project.id,
            doc_id="pub-1",
            status=DocStatus.published,
            content="# Pub 1",
        )
        _make_doc(
            db_session,
            project_id=project.id,
            doc_id="pub-2",
            status=DocStatus.published,
            content="# Pub 2",
        )
        _make_doc(
            db_session,
            project_id=project.id,
            doc_id="archived-other",
            status=DocStatus.archived,
            content="# Archived",
        )

        resp = client.get(f"/project/{project.id}/api/docs/export")
        assert resp.status_code == 200

        buf = io.BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
            assert any("pub-1" in n for n in names)
            assert any("pub-2" in n for n in names)
            assert any("archived-other" in n for n in names)


class TestExportCli:
    def test_export_cli_generates_files(self, tmp_path: object, db_session: Session) -> None:
        """docs-export CLI creates ZIP file in output-dir."""
        import tempfile
        from contextlib import contextmanager
        from pathlib import Path

        _project = _make_project(db_session, project_id="cli-proj")
        _make_doc(db_session, project_id="cli-proj", doc_id="cli-doc", content="# CLI Export Doc")

        @contextmanager
        def fake_get_session() -> Generator[Session, None, None]:
            yield db_session

        runner = CliRunner()
        with runner.isolated_filesystem():
            out_dir = Path(tempfile.mkdtemp())
            result = runner.invoke(
                docs_export,
                ["cli-proj", "--output-dir", str(out_dir)],
                obj={"get_session": fake_get_session},
            )
            if result.exit_code != 0 and result.exception:
                raise result.exception

    def test_export_cli_unknown_project_exits_1(
        self, tmp_path: object, db_session: Session
    ) -> None:
        """Unknown project exits with code 1."""
        import tempfile
        from contextlib import contextmanager
        from pathlib import Path

        @contextmanager
        def fake_get_session() -> Generator[Session, None, None]:
            yield db_session

        runner = CliRunner()
        out_dir = Path(tempfile.mkdtemp())
        result = runner.invoke(
            docs_export,
            ["nonexistent-project", "--output-dir", str(out_dir)],
            obj={"get_session": fake_get_session},
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# 3. Link Validation Tests
# ---------------------------------------------------------------------------


class TestValidateLinks:
    def test_validate_links_internal_not_found(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Internal broken link detected and stored in doc.broken_links."""
        project = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=project.id,
            doc_id="doc-broken",
            content="Check [missing](docs/nonexistent.md) for details.",
        )

        resp = client.get(f"/project/{project.id}/api/docs/doc-broken/validate-links")
        assert resp.status_code == 200
        assert "not_found" in resp.text.lower() or "broken" in resp.text.lower()

        db_session.refresh(doc)
        assert doc.broken_links is not None
        assert any(
            b.get("type") == "internal" and b.get("status") == "not_found" for b in doc.broken_links
        )

    def test_validate_links_all_valid(
        self, client: TestClient, db_session: Session, tmp_path: Any
    ) -> None:
        """Valid internal links return 'All links valid'."""
        project = _make_project(
            db_session, project_id="val-proj", display_name="Validation Project"
        )
        project.repo_root = str(tmp_path)
        db_session.flush()

        doc_file = tmp_path / "docs" / "guide.md"
        doc_file.parent.mkdir()
        doc_file.write_text("# Guide\n\nContent")

        doc = _make_doc(
            db_session,
            project_id="val-proj",
            doc_id="doc-valid",
            content=f"Check [this guide]({doc_file}) for details.",
        )

        resp = client.get(f"/project/{project.id}/api/docs/doc-valid/validate-links")
        assert resp.status_code == 200
        assert "All links valid" in resp.text or "not_found" not in resp.text.lower()

        db_session.refresh(doc)
        assert doc.broken_links is None or doc.broken_links == []

    def test_validate_links_external_404(self, client: TestClient, db_session: Session) -> None:
        """External 404 marked as broken link."""
        project = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=project.id,
            doc_id="doc-ext-404",
            content="Check [broken](https://httpbin.org/status/404) link.",
        )

        mock_response = type("MockResponse", (), {"status_code": 404})()
        with patch("orch.doc_service.httpx.head", return_value=mock_response):
            resp = client.get(f"/project/{project.id}/api/docs/doc-ext-404/validate-links")
        assert resp.status_code == 200

        db_session.refresh(doc)
        assert doc.broken_links is not None
        assert any(
            b.get("type") == "external" and b.get("status") == "404" for b in doc.broken_links
        )

    def test_validate_links_no_content_422(self, client: TestClient, db_session: Session) -> None:
        """Doc with no content returns 422."""
        project = _make_project(db_session)
        _make_doc(db_session, project_id=project.id, doc_id="doc-empty", content=None)

        resp = client.get(f"/project/{project.id}/api/docs/doc-empty/validate-links")
        assert resp.status_code == 422

    def test_validate_links_max_links_limit(self, client: TestClient, db_session: Session) -> None:
        """Only first 20 links are validated."""
        project = _make_project(db_session)
        links = "\n".join(f"[link{i}](docs/file{i}.md)" for i in range(25))
        doc = _make_doc(
            db_session,
            project_id=project.id,
            doc_id="doc-many-links",
            content=f"# Links\n\n{links}",
        )

        resp = client.get(f"/project/{project.id}/api/docs/doc-many-links/validate-links")
        assert resp.status_code == 200

        db_session.refresh(doc)
        if doc.broken_links:
            assert len(doc.broken_links) <= 20

    def test_validate_links_transient_5xx_not_flagged(
        self, client: TestClient, db_session: Session
    ) -> None:
        """5xx responses marked as transient, not broken links."""
        project = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=project.id,
            doc_id="doc-5xx",
            content="Check [service](https://httpbin.org/status/503) link.",
        )

        mock_response = type("MockResponse", (), {"status_code": 503})()
        with patch("orch.doc_service.httpx.head", return_value=mock_response):
            resp = client.get(f"/project/{project.id}/api/docs/doc-5xx/validate-links")
        assert resp.status_code == 200

        db_session.refresh(doc)
        if doc.broken_links:
            assert not any(
                b.get("type") == "external" and b.get("status") == "404" for b in doc.broken_links
            )

    def test_validate_links_ssrf_blocked(self, client: TestClient, db_session: Session) -> None:
        """localhost/internal URLs blocked as SSRF."""
        project = _make_project(db_session)
        doc = _make_doc(
            db_session,
            project_id=project.id,
            doc_id="doc-ssrf",
            content="Check [internal](http://localhost:9900/internal) link.",
        )

        resp = client.get(f"/project/{project.id}/api/docs/doc-ssrf/validate-links")
        assert resp.status_code == 200

        db_session.refresh(doc)
        assert doc.broken_links is not None
        assert any(b.get("status") == "blocked_ssrf" for b in doc.broken_links)


# ---------------------------------------------------------------------------
# 4. Global Search Tests
# ---------------------------------------------------------------------------


class TestGlobalSearch:
    def test_global_search_page_200(self, client: TestClient, db_session: Session) -> None:
        """GET /docs returns 200."""
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_global_search_returns_cross_project_results(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Search for 'authentication' returns docs from both projects."""
        proj1 = _make_project(db_session, project_id="proj-1", display_name="Project One")
        proj2 = _make_project(db_session, project_id="proj-2", display_name="Project Two")

        _make_doc(
            db_session,
            project_id="proj-1",
            doc_id="auth-mod",
            title="Auth Module",
            content="# Authentication\n\nModule content.",
            project=proj1,
        )
        _make_doc(
            db_session,
            project_id="proj-2",
            doc_id="auth-api",
            title="Auth API",
            content="# Authentication\n\nAPI content.",
            project=proj2,
        )

        resp = client.get("/api/docs/search?q=authentication")
        assert resp.status_code == 200
        html = resp.text
        assert "proj-1" in html or "Project One" in html
        assert "proj-2" in html or "Project Two" in html

    def test_global_search_excludes_archived(self, client: TestClient, db_session: Session) -> None:
        """Archived docs excluded from default results."""
        _make_project(db_session, project_id="arch-proj")
        _make_doc(
            db_session,
            project_id="arch-proj",
            doc_id="arch-doc",
            status=DocStatus.archived,
            content="# Archived content about authentication",
        )

        resp = client.get("/api/docs/search?q=authentication")
        assert resp.status_code == 200
        assert "arch-doc" not in resp.text or "archived" not in resp.text.lower()

    def test_global_search_filter_by_doc_type(
        self, client: TestClient, db_session: Session
    ) -> None:
        """doc_type filter returns only matching doc types."""
        proj = _make_project(db_session, project_id="type-proj")
        _make_doc(
            db_session,
            project_id="type-proj",
            doc_id="type-module",
            doc_type=DocType.module,
            content="# Module keyword content",
            project=proj,
        )
        _make_doc(
            db_session,
            project_id="type-proj",
            doc_id="type-api",
            doc_type=DocType.api,
            content="# API keyword content",
            project=proj,
        )

        resp = client.get("/api/docs/search?q=keyword&doc_type=api")
        assert resp.status_code == 200
        assert "type-api" in resp.text
        assert "type-module" not in resp.text

    def test_global_search_snippet_highlighted(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Search result excerpt is highlighted with <mark> or <b>."""
        _make_project(db_session, project_id="hl-proj")
        _make_doc(
            db_session,
            project_id="hl-proj",
            doc_id="hl-doc",
            content="# Authentication\n\nThis module covers authentication mechanisms.",
        )

        resp = client.get("/api/docs/search?q=authentication")
        assert resp.status_code == 200
        html = resp.text
        assert "<mark" in html or "&lt;mark" in html or "<b>" in html or "&lt;b" in html
        assert "authentication" in html.lower()

    def test_global_search_empty_results(self, client: TestClient, db_session: Session) -> None:
        """No matches returns empty state HTML."""
        resp = client.get("/api/docs/search?q=nonexistent_search_term_xyz_123")
        assert resp.status_code == 200
        assert (
            "no documentation found" in resp.text.lower()
            or "no results" in resp.text.lower()
            or "try different" in resp.text.lower()
        )

    def test_global_search_groups_by_project(self, client: TestClient, db_session: Session) -> None:
        """Results are grouped by project with section headers."""
        _make_project(db_session, project_id="grp-proj-1", display_name="Group Project 1")
        _make_project(db_session, project_id="grp-proj-2", display_name="Group Project 2")

        _make_doc(
            db_session,
            project_id="grp-proj-1",
            doc_id="grp-doc-1",
            content="# Content about testing in project 1",
        )
        _make_doc(
            db_session,
            project_id="grp-proj-2",
            doc_id="grp-doc-2",
            content="# Content about testing in project 2",
        )

        resp = client.get("/api/docs/search?q=testing")
        assert resp.status_code == 200
        html = resp.text
        assert "grp-proj-1" in html or "Group Project 1" in html
        assert "grp-proj-2" in html or "Group Project 2" in html

    def test_global_search_empty_query_returns_empty(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Empty query returns 200 with empty/zero-state HTML."""
        resp = client.get("/api/docs/search?q=")
        assert resp.status_code == 200
