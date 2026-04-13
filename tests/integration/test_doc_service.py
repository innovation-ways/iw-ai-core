"""Unit tests for DocService using a real PostgreSQL testcontainer (no mocks)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

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
    from pathlib import Path

    from sqlalchemy.orm import Session


def make_project(session: Session, project_id: str = "test-proj") -> Project:
    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    session.add(project)
    session.flush()
    return project


# ---------------------------------------------------------------------------
# test_create_doc_creates_record_and_version
# ---------------------------------------------------------------------------


def test_create_doc_creates_record_and_version(db_session: Session) -> None:
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
        content="# Auth Module\n\nContent here.",
        generated_by="skill:iw-doc-generator",
        trigger_reason="cli:iw doc-update",
    )

    assert doc.id == "test-proj:module-auth"
    assert doc.project_id == "test-proj"
    assert doc.doc_id == "module-auth"
    assert doc.title == "Auth Module"
    assert doc.slug == "auth-module"
    assert doc.doc_type == DocType.module
    assert doc.tier == DocTier.semi_automated
    assert doc.status == DocStatus.draft
    assert doc.version == 1
    assert doc.content is not None
    assert doc.generated_at is not None

    versions = db_session.query(ProjectDocVersion).filter_by(doc_id=doc.id).all()
    assert len(versions) == 1
    assert versions[0].version == 1
    assert versions[0].content == "# Auth Module\n\nContent here."
    assert versions[0].trigger_reason == "cli:iw doc-update"


# ---------------------------------------------------------------------------
# test_create_doc_no_content_no_version_snapshot
# ---------------------------------------------------------------------------


def test_create_doc_no_content_no_version_snapshot(db_session: Session) -> None:
    make_project(db_session)

    svc = DocService(db_session)
    doc = svc.create_doc(
        project_id="test-proj",
        doc_id="module-planned",
        title="Planned Module",
        doc_type=DocType.module,
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory.guide,
        status=DocStatus.planned,
        content=None,
    )

    assert doc.version == 0
    assert doc.content is None
    assert doc.generated_at is None

    versions = db_session.query(ProjectDocVersion).filter_by(doc_id=doc.id).all()
    assert len(versions) == 0


# ---------------------------------------------------------------------------
# test_create_doc_unknown_project_raises_value_error
# ---------------------------------------------------------------------------


def test_create_doc_unknown_project_raises_value_error(db_session: Session) -> None:
    svc = DocService(db_session)
    with pytest.raises(ValueError, match="Project 'nonexistent' not found"):
        svc.create_doc(
            project_id="nonexistent",
            doc_id="module-auth",
            title="Auth Module",
            doc_type=DocType.module,
            tier=DocTier.semi_automated,
            editorial_category=EditorialCategory.technical,
        )


# ---------------------------------------------------------------------------
# test_update_doc_content_changed_creates_version
# ---------------------------------------------------------------------------


def test_update_doc_content_changed_creates_version(db_session: Session) -> None:
    make_project(db_session)

    svc = DocService(db_session)
    doc = svc.create_doc(
        project_id="test-proj",
        doc_id="module-auth",
        title="Auth Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        content="# Version 1",
        trigger_reason="initial",
    )
    assert doc.version == 1

    updated = svc.update_doc(
        "test-proj",
        "module-auth",
        content="# Version 2",
        generated_by="skill:iw-doc-generator",
        trigger_reason="updated-content",
    )

    assert updated.version == 2
    assert updated.content == "# Version 2"

    versions = (
        db_session.query(ProjectDocVersion)
        .filter_by(doc_id=doc.id)
        .order_by(ProjectDocVersion.version)
        .all()
    )
    assert len(versions) == 2
    assert versions[0].version == 1
    assert versions[1].version == 2
    assert versions[1].trigger_reason == "updated-content"


# ---------------------------------------------------------------------------
# test_update_doc_content_unchanged_no_new_version
# ---------------------------------------------------------------------------


def test_update_doc_content_unchanged_no_new_version(db_session: Session) -> None:
    make_project(db_session)

    svc = DocService(db_session)
    doc = svc.create_doc(
        project_id="test-proj",
        doc_id="module-auth",
        title="Auth Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        content="# Same Content",
        trigger_reason="initial",
    )
    assert doc.version == 1

    updated = svc.update_doc(
        "test-proj",
        "module-auth",
        title="Updated Title",
        content="# Same Content",
    )

    assert updated.version == 1
    assert updated.title == "Updated Title"

    versions = db_session.query(ProjectDocVersion).filter_by(doc_id=doc.id).all()
    assert len(versions) == 1


# ---------------------------------------------------------------------------
# test_update_doc_content_change_clears_pdf_path
# ---------------------------------------------------------------------------


def test_update_doc_content_change_clears_pdf_path(db_session: Session) -> None:
    make_project(db_session)

    svc = DocService(db_session)
    doc = svc.create_doc(
        project_id="test-proj",
        doc_id="module-auth",
        title="Auth Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        content="# Version 1",
    )
    db_session.flush()
    doc.pdf_path = "/path/to/doc.pdf"
    doc.html_path = "/path/to/doc.html"
    db_session.flush()

    updated = svc.update_doc(
        "test-proj",
        "module-auth",
        content="# Version 2",
    )

    assert updated.pdf_path is None
    assert updated.html_path is None


# ---------------------------------------------------------------------------
# test_upsert_doc_creates_when_missing
# ---------------------------------------------------------------------------


def test_upsert_doc_creates_when_missing(db_session: Session) -> None:
    make_project(db_session)

    svc = DocService(db_session)
    doc, created = svc.upsert_doc(
        project_id="test-proj",
        doc_id="module-new",
        title="New Module",
        doc_type=DocType.module,
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory.guide,
        content="# New content",
    )

    assert created is True
    assert doc.id == "test-proj:module-new"
    assert doc.version == 1


# ---------------------------------------------------------------------------
# test_upsert_doc_updates_when_exists
# ---------------------------------------------------------------------------


def test_upsert_doc_updates_when_exists(db_session: Session) -> None:
    make_project(db_session)

    svc = DocService(db_session)
    doc1, created1 = svc.upsert_doc(
        project_id="test-proj",
        doc_id="module-auth",
        title="Auth Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        content="# V1",
    )
    assert created1 is True
    assert doc1.version == 1

    doc2, created2 = svc.upsert_doc(
        project_id="test-proj",
        doc_id="module-auth",
        title="Auth Module Updated",
        content="# V2",
    )
    assert created2 is False
    assert doc2.version == 2
    assert doc2.title == "Auth Module Updated"
    assert doc2.content == "# V2"


# ---------------------------------------------------------------------------
# test_list_docs_filter_by_type
# ---------------------------------------------------------------------------


def test_list_docs_filter_by_type(db_session: Session) -> None:
    make_project(db_session)

    svc = DocService(db_session)
    svc.create_doc(
        project_id="test-proj",
        doc_id="module-auth",
        title="Auth Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        content="# auth",
    )
    svc.create_doc(
        project_id="test-proj",
        doc_id="api-users",
        title="Users API",
        doc_type=DocType.api,
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory.technical,
        content="# users api",
    )
    svc.create_doc(
        project_id="test-proj",
        doc_id="arch-overview",
        title="Architecture Overview",
        doc_type=DocType.architecture,
        tier=DocTier.fully_automated,
        editorial_category=EditorialCategory.technical,
        content="# architecture",
    )
    db_session.flush()

    docs = svc.list_docs("test-proj", doc_type=DocType.module)
    assert len(docs) == 1
    assert docs[0].doc_id == "module-auth"

    docs = svc.list_docs("test-proj", doc_type=DocType.api)
    assert len(docs) == 1
    assert docs[0].doc_id == "api-users"


# ---------------------------------------------------------------------------
# test_list_docs_fts_search
# ---------------------------------------------------------------------------


def test_list_docs_fts_search(db_session: Session) -> None:
    make_project(db_session)

    svc = DocService(db_session)
    svc.create_doc(
        project_id="test-proj",
        doc_id="module-auth",
        title="Authentication Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        content="Login and session management with OAuth2.",
    )
    svc.create_doc(
        project_id="test-proj",
        doc_id="api-users",
        title="Users API",
        doc_type=DocType.api,
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory.technical,
        content="REST endpoints for user CRUD operations.",
    )
    db_session.flush()

    results = svc.list_docs("test-proj", search="session")
    assert len(results) == 1
    assert results[0].doc_id == "module-auth"

    results = svc.list_docs("test-proj", search="REST")
    assert len(results) == 1
    assert results[0].doc_id == "api-users"

    results = svc.list_docs("test-proj", search="authentication")
    assert len(results) == 1
    assert results[0].doc_id == "module-auth"


# ---------------------------------------------------------------------------
# test_list_doc_versions_ordered
# ---------------------------------------------------------------------------


def test_list_doc_versions_ordered(db_session: Session) -> None:
    make_project(db_session)

    svc = DocService(db_session)
    svc.create_doc(
        project_id="test-proj",
        doc_id="module-auth",
        title="Auth Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        content="# V1",
    )

    svc.update_doc("test-proj", "module-auth", content="# V2")
    svc.update_doc("test-proj", "module-auth", content="# V3")

    versions = svc.list_doc_versions("test-proj", "module-auth")
    assert len(versions) == 3
    assert [v.version for v in versions] == [3, 2, 1]


# ---------------------------------------------------------------------------
# test_get_stale_docs
# ---------------------------------------------------------------------------


def test_get_stale_docs(db_session: Session, tmp_path: Path) -> None:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)  # noqa: S603,S607
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )  # noqa: S603,S607
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )  # noqa: S603,S607

    auth_rs = repo / "src" / "auth" / "mod.rs"
    auth_rs.parent.mkdir(parents=True, exist_ok=True)
    auth_rs.write_text("initial content", encoding="utf-8")
    subprocess.run(["git", "add", str(auth_rs)], cwd=repo, check=True, capture_output=True)  # noqa: S603,S607
    subprocess.run(
        ["git", "commit", "-m", "initial"],  # noqa: S603,S607
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            **__import__("os").environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
        },
    )

    import time

    time.sleep(0.1)

    auth_rs.write_text("updated content", encoding="utf-8")
    subprocess.run(["git", "add", str(auth_rs)], cwd=repo, check=True, capture_output=True)  # noqa: S603,S607
    subprocess.run(
        ["git", "commit", "-m", "updated"],  # noqa: S603,S607
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            **__import__("os").environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
        },
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )  # noqa: S603

    auth_rs = repo / "src" / "auth" / "mod.rs"
    auth_rs.parent.mkdir(parents=True, exist_ok=True)
    auth_rs.write_text("initial content", encoding="utf-8")
    subprocess.run(["git", "add", str(auth_rs)], cwd=repo, check=True, capture_output=True)  # noqa: S603
    subprocess.run(
        ["git", "commit", "-m", "initial"],  # noqa: S603
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            **__import__("os").environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
        },
    )

    import time

    time.sleep(0.1)

    auth_rs.write_text("updated content", encoding="utf-8")
    subprocess.run(["git", "add", str(auth_rs)], cwd=repo, check=True, capture_output=True)  # noqa: S603
    subprocess.run(
        ["git", "commit", "-m", "updated"],
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            **__import__("os").environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
        },
    )  # noqa: S603

    project = Project(
        id="test-proj",
        display_name="Test Project",
        repo_root=str(repo),
        config={},
    )
    db_session.add(project)
    db_session.flush()

    svc = DocService(db_session)
    doc = svc.create_doc(
        project_id="test-proj",
        doc_id="module-auth",
        title="Auth Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        content="# Content",
        generated_by="skill:iw-doc-generator",
    )
    db_session.flush()

    doc.generated_at = datetime.now(UTC) - timedelta(hours=25)
    doc.source_paths = ["src/auth/mod.rs"]
    db_session.flush()

    stale = svc.get_stale_docs("test-proj", str(repo), threshold_hours=24)
    assert len(stale) == 1
    assert stale[0][0].id == "test-proj:module-auth"


# ---------------------------------------------------------------------------
# test_delete_doc
# ---------------------------------------------------------------------------


def test_delete_doc(db_session: Session) -> None:
    make_project(db_session)

    svc = DocService(db_session)
    svc.create_doc(
        project_id="test-proj",
        doc_id="module-auth",
        title="Auth Module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        content="# Content",
    )
    db_session.flush()

    result = svc.delete_doc("test-proj", "module-auth")
    assert result is True

    assert db_session.get(ProjectDoc, "test-proj:module-auth") is None

    deleted_again = svc.delete_doc("test-proj", "module-auth")
    assert deleted_again is False


# ---------------------------------------------------------------------------
# test_update_doc_not_found_raises_key_error
# ---------------------------------------------------------------------------


def test_update_doc_not_found_raises_key_error(db_session: Session) -> None:
    make_project(db_session)

    svc = DocService(db_session)
    with pytest.raises(KeyError, match="Document 'test-proj:nonexistent' not found"):
        svc.update_doc("test-proj", "nonexistent", title="New Title")
