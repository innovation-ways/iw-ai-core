"""Integration tests for ProjectDoc, ProjectDocVersion, and DocGenerationJob models.

Tests verify:
- All three models can be inserted and queried back
- ENUM constraints work correctly
- Cascade deletes propagate correctly
- FTS trigger updates content_search when title/content change
- FTS full-text search query works
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError

from orch.db.models import (
    DocGenerationJob,
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    JobStatus,
    Project,
    ProjectDoc,
    ProjectDocVersion,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def make_project(project_id: str = "test-proj") -> Project:
    return Project(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
    )


def make_project_doc(
    project_id: str = "test-proj",
    doc_id: str = "module-auth",
    title: str = "Auth Module",
    audience: list[str] | None = None,
    source_paths: list[str] | None = None,
    content: str | None = "# Auth Module\n\nThis is the auth module.",
) -> ProjectDoc:
    return ProjectDoc(
        id=f"{project_id}:{doc_id}",
        project_id=project_id,
        doc_id=doc_id,
        title=title,
        slug="auth-module",
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.draft,
        audience=audience or ["developers", "architects"],
        source_paths=source_paths or ["src/auth/mod.rs"],
        content=content,
    )


# ---------------------------------------------------------------------------
# Test: ProjectDoc create and query
# ---------------------------------------------------------------------------


def test_project_doc_create(db_session: Session) -> None:
    """Create a ProjectDoc with all fields and persist it."""
    db_session.add(make_project())
    db_session.flush()

    doc = make_project_doc()
    db_session.add(doc)
    db_session.flush()

    result = db_session.get(ProjectDoc, "test-proj:module-auth")
    assert result is not None
    assert result.title == "Auth Module"
    assert result.doc_type == DocType.module
    assert result.tier == DocTier.semi_automated
    assert result.editorial_category == EditorialCategory.technical
    assert result.status == DocStatus.draft
    assert result.audience == ["developers", "architects"]
    assert result.source_paths == ["src/auth/mod.rs"]
    assert result.version == 0
    assert result.content is not None
    assert "Auth Module" in result.content


def test_project_doc_version_defaults(db_session: Session) -> None:
    """ProjectDoc version defaults to 0."""
    db_session.add(make_project())
    db_session.flush()

    doc = make_project_doc()
    db_session.add(doc)
    db_session.flush()

    assert doc.version == 0
    assert doc.generated_at is None
    assert doc.generated_by is None
    assert doc.html_path is None
    assert doc.pdf_path is None


def test_project_doc_jsonb_fields(db_session: Session) -> None:
    """JSONB audience and source_paths are stored as Python lists."""
    db_session.add(make_project())
    db_session.flush()

    doc = make_project_doc(
        audience=["senior-developers", "devops"],
        source_paths=["src/auth/token.rs", "src/auth/middleware.rs"],
    )
    db_session.add(doc)
    db_session.flush()

    result = db_session.get(ProjectDoc, "test-proj:module-auth")
    assert result is not None
    assert result.audience == ["senior-developers", "devops"]
    assert result.source_paths == ["src/auth/token.rs", "src/auth/middleware.rs"]


def test_project_doc_unique_constraint(db_session: Session) -> None:
    """(project_id, doc_id) must be unique."""
    db_session.add(make_project())
    db_session.flush()

    doc1 = make_project_doc(doc_id="module-auth")
    doc2 = make_project_doc(doc_id="module-auth")
    db_session.add(doc1)
    db_session.flush()
    db_session.add(doc2)
    with pytest.raises((IntegrityError, Exception)):  # noqa: B017
        db_session.flush()


def test_project_doc_cascade_on_project_delete(db_session: Session) -> None:
    """Deleting a project must cascade delete its ProjectDoc records."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_project_doc())
    db_session.flush()

    project = db_session.get(Project, "test-proj")
    db_session.delete(project)
    db_session.flush()

    docs = db_session.query(ProjectDoc).filter_by(project_id="test-proj").all()
    assert docs == []


# ---------------------------------------------------------------------------
# Test: ProjectDocVersion create and query
# ---------------------------------------------------------------------------


def test_project_doc_version_create(db_session: Session) -> None:
    """Create a ProjectDocVersion snapshot with FK to ProjectDoc."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_project_doc())
    db_session.flush()

    version = ProjectDocVersion(
        doc_id="test-proj:module-auth",
        version=1,
        content="# Auth Module v1\n\nVersion 1 content.",
        generated_by="skill:iw-doc-generator",
        trigger_reason="cli:iw doc-update",
    )
    db_session.add(version)
    db_session.flush()

    result = db_session.get(ProjectDocVersion, version.id)
    assert result is not None
    assert result.doc_id == "test-proj:module-auth"
    assert result.version == 1
    assert "Version 1 content" in result.content
    assert result.generated_by == "skill:iw-doc-generator"
    assert result.trigger_reason == "cli:iw doc-update"


def test_project_doc_version_cascade_on_doc_delete(db_session: Session) -> None:
    """Deleting a ProjectDoc must cascade delete its versions."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_project_doc())
    db_session.flush()

    version = ProjectDocVersion(
        doc_id="test-proj:module-auth",
        version=1,
        content="Snapshot content",
    )
    db_session.add(version)
    db_session.flush()

    doc = db_session.get(ProjectDoc, "test-proj:module-auth")
    db_session.delete(doc)
    db_session.flush()

    versions = db_session.query(ProjectDocVersion).filter_by(doc_id="test-proj:module-auth").all()
    assert versions == []


def test_project_doc_version_multiple_versions(db_session: Session) -> None:
    """Multiple version snapshots can exist for the same doc."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_project_doc())
    db_session.flush()

    for i in range(1, 4):
        version = ProjectDocVersion(
            doc_id="test-proj:module-auth",
            version=i,
            content=f"Content version {i}",
            trigger_reason=f"manual-update-{i}",
        )
        db_session.add(version)
    db_session.flush()

    versions = (
        db_session.query(ProjectDocVersion)
        .filter_by(doc_id="test-proj:module-auth")
        .order_by(ProjectDocVersion.version)
        .all()
    )
    assert len(versions) == 3
    assert [v.version for v in versions] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Test: DocGenerationJob create and query
# ---------------------------------------------------------------------------


def test_doc_generation_job_create(db_session: Session) -> None:
    """Create a DocGenerationJob with all fields."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_project_doc())
    db_session.flush()

    job_id = str(uuid.uuid4())
    job = DocGenerationJob(
        id=job_id,
        project_id="test-proj",
        doc_id="test-proj:module-auth",
        status=JobStatus.queued,
    )
    db_session.add(job)
    db_session.flush()

    result = db_session.get(DocGenerationJob, job_id)
    assert result is not None
    assert result.project_id == "test-proj"
    assert result.doc_id == "test-proj:module-auth"
    assert result.status == JobStatus.queued


def test_doc_generation_job_status_default(db_session: Session) -> None:
    """JobStatus defaults to queued."""
    db_session.add(make_project())
    db_session.flush()

    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="test-proj",
    )
    db_session.add(job)
    db_session.flush()

    assert job.status == JobStatus.queued


def test_doc_generation_job_doc_id_nullable(db_session: Session) -> None:
    """DocGenerationJob.doc_id is nullable — job survives doc deletion."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_project_doc())
    db_session.flush()

    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="test-proj",
        doc_id="test-proj:module-auth",
    )
    db_session.add(job)
    db_session.flush()

    # Simulate doc deletion via SET NULL
    db_session.execute(text("DELETE FROM project_docs WHERE id = 'test-proj:module-auth'"))
    db_session.flush()

    db_session.refresh(job)
    assert job.doc_id is None


def test_doc_generation_job_cascade_on_project_delete(db_session: Session) -> None:
    """Deleting a project must cascade delete its DocGenerationJob records."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_project_doc())
    db_session.flush()

    job = DocGenerationJob(
        id=str(uuid.uuid4()),
        project_id="test-proj",
        doc_id="test-proj:module-auth",
    )
    db_session.add(job)
    db_session.flush()

    project = db_session.get(Project, "test-proj")
    db_session.delete(project)
    db_session.flush()

    jobs = db_session.query(DocGenerationJob).filter_by(project_id="test-proj").all()
    assert jobs == []


# ---------------------------------------------------------------------------
# Test: ENUM constraints reject invalid values
# ---------------------------------------------------------------------------


def test_invalid_doc_type_rejected(db_session: Session) -> None:
    """DB must reject an invalid doc_type value."""
    db_session.add(make_project())
    db_session.flush()

    with pytest.raises(DataError):
        db_session.execute(
            text(
                "INSERT INTO project_docs "
                "(id, project_id, doc_id, title, slug, doc_type, tier, editorial_category, status) "
                "VALUES ('test-proj:bad', 'test-proj', 'bad', 'Bad', 'bad', "
                "'invalid_type', 'human_authored', 'technical', 'planned')"
            )
        )


def test_invalid_doc_status_rejected(db_session: Session) -> None:
    """DB must reject an invalid doc_status value."""
    db_session.add(make_project())
    db_session.flush()

    with pytest.raises(DataError):
        db_session.execute(
            text(
                "INSERT INTO project_docs "
                "(id, project_id, doc_id, title, slug, doc_type, tier, editorial_category, status) "
                "VALUES ('test-proj:bad', 'test-proj', 'bad', 'Bad', 'bad', "
                "'module', 'human_authored', 'technical', 'invalid_status')"
            )
        )


def test_invalid_job_status_rejected(db_session: Session) -> None:
    """DB must reject an invalid job_status value."""
    db_session.add(make_project())
    db_session.flush()

    with pytest.raises(DataError):
        db_session.execute(
            text(
                "INSERT INTO doc_generation_jobs (id, project_id, status) "
                "VALUES ('00000000-0000-0000-0000-000000000001', 'test-proj', 'invalid_status')"
            )
        )


# ---------------------------------------------------------------------------
# Test: FTS trigger updates content_search
# ---------------------------------------------------------------------------


def test_project_doc_fts_trigger_on_insert(db_session: Session) -> None:
    """Inserting a ProjectDoc must auto-populate content_search via trigger."""
    db_session.add(make_project())
    db_session.flush()

    doc = make_project_doc(
        title="Authentication Module",
        content="This module handles user login and session management.",
    )
    db_session.add(doc)
    db_session.flush()
    db_session.refresh(doc)

    assert doc.content_search is not None
    assert doc.content_search != ""


def test_project_doc_fts_trigger_on_update(db_session: Session) -> None:
    """Updating ProjectDoc content must refresh content_search via trigger."""
    db_session.add(make_project())
    db_session.flush()

    doc = make_project_doc(title="Auth Module", content="Initial content.")
    db_session.add(doc)
    db_session.flush()
    db_session.refresh(doc)
    old_search = doc.content_search

    doc.content = "Updated: bearer tokens and refresh tokens and session rotation."
    db_session.flush()
    db_session.refresh(doc)

    assert doc.content_search != old_search
    assert doc.content_search is not None


def test_project_doc_fts_trigger_title_only(db_session: Session) -> None:
    """Without content, content_search should be set from title only."""
    db_session.add(make_project())
    db_session.flush()

    doc = ProjectDoc(
        id="test-proj:module-no-content",
        project_id="test-proj",
        doc_id="module-no-content",
        title="API Reference Documentation",
        slug="api-reference",
        doc_type=DocType.api,
        tier=DocTier.human_authored,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.planned,
        content=None,
    )
    db_session.add(doc)
    db_session.flush()
    db_session.refresh(doc)

    assert doc.content_search is not None


def test_project_doc_fts_full_text_search(db_session: Session) -> None:
    """FTS search using plainto_tsquery must find docs by content keywords."""
    db_session.add(make_project())
    db_session.flush()

    docs = [
        ("module-auth", "Authentication Module", "user login session management OAuth2"),
        ("api-users", "Users API", "REST API endpoints for user CRUD operations"),
        ("arch-overview", "Architecture Overview", "system architecture microservices diagram"),
    ]
    for doc_id, title, content in docs:
        db_session.add(
            ProjectDoc(
                id=f"test-proj:{doc_id}",
                project_id="test-proj",
                doc_id=doc_id,
                title=title,
                slug=doc_id,
                doc_type=DocType.module,
                tier=DocTier.semi_automated,
                editorial_category=EditorialCategory.technical,
                status=DocStatus.draft,
                content=content,
            )
        )
    db_session.flush()

    results = (
        db_session.query(ProjectDoc)
        .filter(ProjectDoc.content_search.op("@@")(text("plainto_tsquery('english', 'session')")))
        .all()
    )
    assert len(results) == 1
    assert results[0].doc_id == "module-auth"

    results = (
        db_session.query(ProjectDoc)
        .filter(ProjectDoc.content_search.op("@@")(text("plainto_tsquery('english', 'API')")))
        .all()
    )
    assert len(results) == 1
    assert results[0].doc_id == "api-users"

    results = (
        db_session.query(ProjectDoc)
        .filter(
            ProjectDoc.content_search.op("@@")(text("plainto_tsquery('english', 'architecture')"))
        )
        .all()
    )
    assert len(results) >= 1
    assert "arch-overview" in [r.doc_id for r in results]
