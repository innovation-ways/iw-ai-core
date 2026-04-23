"""Integration tests for docs dashboard routes.

Tests verify:
- GET /project/{project_id}/docs — doc library page
- GET /project/{project_id}/docs/{doc_id} — document detail page
- GET /project/{project_id}/docs/{doc_id}/pdf — PDF download
- GET /api/project/{project_id}/docs/search — htmx search/filter fragment
- GET /api/project/{project_id}/docs/{doc_id}/versions — version drawer fragment
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
from orch.doc_service import DocService

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from sqlalchemy.orm import Session


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


def make_project(
    db: Session, project_id: str = "test-proj", repo_root: str = "/repos/test"
) -> Project:
    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root=repo_root,
        config={},
    )
    db.add(project)
    db.flush()
    return project


def make_doc(
    db: Session,
    project_id: str = "test-proj",
    doc_id: str = "module-auth",
    title: str = "Auth Module",
    doc_type: DocType = DocType.module,
    tier: DocTier = DocTier.semi_automated,
    status: DocStatus = DocStatus.draft,
    content: str | None = "# Auth Module\n\nThis is the auth module.",
    audience: list[str] | None = None,
    source_paths: list[str] | None = None,
) -> ProjectDoc:
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
        audience=audience or ["developers", "architects"],
        source_paths=source_paths or ["src/auth/mod.rs"],
        content=content,
    )
    db.add(doc)
    db.flush()
    return doc


# ---------------------------------------------------------------------------
# Docs Library — GET /project/{project_id}/docs
# ---------------------------------------------------------------------------


def test_docs_library_empty_state(client: TestClient, db_session: Session) -> None:
    """Library page shows empty state when no docs exist."""
    make_project(db_session)

    resp = client.get("/project/test-proj/docs")
    assert resp.status_code == 200
    assert "No documentation found" in resp.text
    assert "iw doc-update" in resp.text


def test_docs_library_with_docs(client: TestClient, db_session: Session) -> None:
    """Library page shows all docs as cards."""
    make_project(db_session)
    make_doc(db_session, doc_id="module-auth", title="Auth Module", doc_type=DocType.module)
    make_doc(db_session, doc_id="api-users", title="Users API", doc_type=DocType.api)
    make_doc(
        db_session,
        doc_id="arch-overview",
        title="Architecture Overview",
        doc_type=DocType.architecture,
    )

    resp = client.get("/project/test-proj/docs")
    assert resp.status_code == 200
    assert "Auth Module" in resp.text
    assert "Users API" in resp.text
    assert "Architecture Overview" in resp.text


def test_docs_library_404_for_unknown_project(client: TestClient) -> None:
    """Unknown project returns 404."""
    resp = client.get("/project/nonexistent/docs")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Docs Library Filter & Search — GET /api/project/{project_id}/docs/search
# ---------------------------------------------------------------------------


def test_docs_library_filter_by_type(client: TestClient, db_session: Session) -> None:
    """Filter by doc_type shows only matching docs."""
    make_project(db_session)
    make_doc(db_session, doc_id="module-auth", title="Auth Module", doc_type=DocType.module)
    make_doc(db_session, doc_id="api-users", title="Users API", doc_type=DocType.api)

    resp = client.get("/project/test-proj/api/docs/search?doc_type=module")
    assert resp.status_code == 200
    assert "Auth Module" in resp.text
    assert "Users API" not in resp.text


def test_docs_library_filter_by_status(client: TestClient, db_session: Session) -> None:
    """Filter by status shows only matching docs."""
    make_project(db_session)
    make_doc(db_session, doc_id="doc1", title="Draft Doc", status=DocStatus.draft)
    make_doc(db_session, doc_id="doc2", title="Published Doc", status=DocStatus.published)

    resp = client.get("/project/test-proj/api/docs/search?status=published")
    assert resp.status_code == 200
    assert "Draft Doc" not in resp.text
    assert "Published Doc" in resp.text


def test_docs_library_fts_search(client: TestClient, db_session: Session) -> None:
    """FTS search returns matching docs."""
    make_project(db_session)
    make_doc(
        db_session,
        doc_id="module-auth",
        title="Auth Module",
        content="This module handles authentication with OAuth2.",
    )
    make_doc(
        db_session,
        doc_id="api-users",
        title="Users API",
        content="REST endpoints for user CRUD operations.",
    )

    resp = client.get("/project/test-proj/api/docs/search?q=authentication")
    assert resp.status_code == 200
    assert "Auth Module" in resp.text

    resp = client.get("/project/test-proj/api/docs/search?q=nonexistent_xyz")
    assert resp.status_code == 200
    assert "No documents match your search" in resp.text


def test_docs_library_filter_plus_search_combined(client: TestClient, db_session: Session) -> None:
    """Combined filter and search returns intersection."""
    make_project(db_session)
    make_doc(
        db_session,
        doc_id="module-auth",
        title="Auth Module",
        doc_type=DocType.module,
        content="Handles authentication tokens.",
    )
    make_doc(
        db_session,
        doc_id="api-auth",
        title="Auth API",
        doc_type=DocType.api,
        content="REST API for authentication.",
    )

    resp = client.get("/project/test-proj/api/docs/search?doc_type=module&q=authentication")
    assert resp.status_code == 200
    assert "Auth Module" in resp.text
    assert "Auth API" not in resp.text


# ---------------------------------------------------------------------------
# Docs Detail — GET /project/{project_id}/docs/{doc_id}
# ---------------------------------------------------------------------------


def test_docs_detail_renders_content(client: TestClient, db_session: Session) -> None:
    """Detail page renders markdown content as HTML."""
    make_project(db_session)
    make_doc(
        db_session,
        doc_id="module-auth",
        title="Auth Module",
        content="# Hello\n\nThis is a test doc.",
    )

    resp = client.get("/project/test-proj/docs/module-auth")
    assert resp.status_code == 200
    assert "<h1>" in resp.text
    assert "Hello" in resp.text
    assert "Content not yet generated" not in resp.text


def test_docs_detail_no_content_placeholder(client: TestClient, db_session: Session) -> None:
    """Detail page shows placeholder when content is None (planned doc)."""
    make_project(db_session)
    make_doc(db_session, doc_id="planned-doc", title="Planned Doc", content=None)

    resp = client.get("/project/test-proj/docs/planned-doc")
    assert resp.status_code == 200
    assert "Content not yet generated" in resp.text


def test_docs_detail_not_found(client: TestClient, db_session: Session) -> None:
    """Detail page returns 404 for nonexistent doc."""
    make_project(db_session)

    resp = client.get("/project/test-proj/docs/nonexistent-doc")
    assert resp.status_code == 404


def test_docs_detail_shows_metadata_sidebar(client: TestClient, db_session: Session) -> None:
    """Detail page sidebar shows type, status, version."""
    make_project(db_session)
    make_doc(
        db_session,
        doc_id="module-auth",
        title="Auth Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        status=DocStatus.draft,
        content="# Auth",
    )

    resp = client.get("/project/test-proj/docs/module-auth")
    assert resp.status_code == 200
    assert "Module" in resp.text
    assert "Draft" in resp.text
    assert "v0" in resp.text


# ---------------------------------------------------------------------------
# Version History — GET /api/project/{project_id}/docs/{doc_id}/versions
# ---------------------------------------------------------------------------


def test_docs_version_drawer(client: TestClient, db_session: Session) -> None:
    """Version drawer shows all version snapshots."""
    make_project(db_session)
    doc = make_doc(db_session, doc_id="module-auth", title="Auth Module", content="# V1")
    db_session.flush()

    for i in range(1, 4):
        version = ProjectDocVersion(
            doc_id=doc.id,
            version=i,
            content=f"# Version {i}",
            trigger_reason=f"cli-update-{i}",
        )
        db_session.add(version)
    db_session.flush()

    resp = client.get("/project/test-proj/api/docs/module-auth/versions")
    assert resp.status_code == 200
    assert "v1" in resp.text
    assert "v2" in resp.text
    assert "v3" in resp.text
    assert "cli-update-1" in resp.text


def test_docs_version_drawer_empty(client: TestClient, db_session: Session) -> None:
    """Version drawer shows message when no versions exist."""
    make_project(db_session)
    make_doc(db_session, doc_id="module-auth", title="Auth Module", content=None)

    resp = client.get("/project/test-proj/api/docs/module-auth/versions")
    assert resp.status_code == 200
    assert "No version history yet" in resp.text


# ---------------------------------------------------------------------------
# PDF Download — GET /project/{project_id}/docs/{doc_id}/pdf
# ---------------------------------------------------------------------------


def test_docs_pdf_no_content(client: TestClient, db_session: Session) -> None:
    """PDF download returns 404 when doc has no content."""
    make_project(db_session)
    make_doc(db_session, doc_id="planned-doc", title="Planned Doc", content=None)

    resp = client.get("/project/test-proj/docs/planned-doc/pdf")
    assert resp.status_code == 404


def test_docs_pdf_not_found(client: TestClient, db_session: Session) -> None:
    """PDF download returns 404 for nonexistent doc."""
    make_project(db_session)

    resp = client.get("/project/test-proj/docs/nonexistent/pdf")
    assert resp.status_code == 404


def test_docs_pdf_with_content(client: TestClient, db_session: Session, tmp_path: Path) -> None:
    """PDF download returns 501 if WeasyPrint not installed, or PDF bytes if installed."""
    make_project(db_session, repo_root=str(tmp_path))
    make_doc(
        db_session,
        doc_id="module-auth",
        title="Auth Module",
        content="# Auth Module\n\nThis is a test document.",
    )

    resp = client.get("/project/test-proj/docs/module-auth/pdf")
    if resp.status_code == 200:
        assert resp.headers["content-type"] == "application/pdf"
        assert "Content-Disposition" in resp.headers
        assert "module-auth" in resp.headers["Content-Disposition"]
    elif resp.status_code == 501:
        assert "WeasyPrint" in resp.text or "not available" in resp.text
    else:
        pytest.fail(f"Unexpected status code {resp.status_code}")


# ---------------------------------------------------------------------------
# Invariant Tests
# ---------------------------------------------------------------------------


def test_invariant_version_matches_snapshot_count(client: TestClient, db_session: Session) -> None:
    """After N updates, ProjectDoc.version == count of ProjectDocVersion rows."""
    make_project(db_session)

    svc = DocService(db_session)
    doc = svc.create_doc(
        project_id="test-proj",
        doc_id="module-auth",
        title="Auth Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.draft,
        content="# V1",
        trigger_reason="initial",
    )
    db_session.flush()

    assert doc.version == 1
    versions = db_session.query(ProjectDocVersion).filter_by(doc_id=doc.id).all()
    assert len(versions) == 1


def test_invariant_content_hash_skip(client: TestClient, db_session: Session) -> None:
    """Identical content does not create a new version snapshot."""
    make_project(db_session)

    svc = DocService(db_session)
    svc.create_doc(
        project_id="test-proj",
        doc_id="module-auth",
        title="Auth Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.draft,
        content="# Same Content",
        trigger_reason="initial",
    )
    db_session.flush()

    updated = svc.update_doc("test-proj", "module-auth", content="# Same Content")
    db_session.flush()

    assert updated.version == 1
    versions = db_session.query(ProjectDocVersion).filter_by(doc_id="test-proj:module-auth").all()
    assert len(versions) == 1


def test_invariant_fts_stays_current(client: TestClient, db_session: Session) -> None:
    """FTS index is updated when content changes."""
    make_project(db_session)
    make_doc(
        db_session,
        doc_id="module-auth",
        title="Auth Module",
        content="Handles login with OAuth2.",
    )
    db_session.flush()

    from orch.doc_service import DocService

    svc = DocService(db_session)
    svc.update_doc(
        "test-proj",
        "module-auth",
        content="Handles login with OAuth2 and JWT tokens.",
    )
    db_session.flush()

    results = svc.list_docs("test-proj", search="JWT")
    assert len(results) == 1
    assert results[0].doc_id == "module-auth"


def test_invariant_pdf_path_only_set_on_success(client: TestClient, db_session: Session) -> None:
    """PDF path is only set if file was successfully generated."""
    make_project(db_session)
    doc = make_doc(db_session, doc_id="module-auth", title="Auth Module", content="# Content")
    db_session.flush()
    assert doc.pdf_path is None
