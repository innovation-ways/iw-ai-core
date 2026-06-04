"""Integration tests for DocSectionGuide CRUD and DocGenerationJob.section_guides_snapshot.

All tests use the testcontainer PostgreSQL — never connect to localhost:5433.
Each test is independent and gets a rolled-back transaction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import (
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    Project,
    ProjectDoc,
)
from orch.doc_service import DocService

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _make_project(session: Session, project_id: str = "test-proj") -> Project:
    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    session.add(project)
    session.flush()
    return project


def _make_doc(
    session: Session,
    project_id: str = "test-proj",
    doc_id: str = "module-auth",
    title: str = "Auth Module",
    content: str | None = "# Auth Module\n\nContent here.",
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
        source_paths=["src/auth/mod.rs"],
        content=content,
    )
    session.add(doc)
    session.flush()
    return doc


# ---------------------------------------------------------------------------
# test_save_and_get_section_guide
# ---------------------------------------------------------------------------


def test_save_and_get_section_guide(db_session: Session) -> None:
    """Saving and retrieving a section guide returns the saved content."""
    _make_project(db_session)
    _make_doc(db_session, doc_id="module-auth")

    svc = DocService(db_session)
    svc.save_section_guide(
        "test-proj",
        "module-auth",
        "Purpose",
        "## Purpose Guide\n\nThis section explains the purpose.",
    )
    db_session.flush()

    result = svc.get_section_guide("test-proj", "module-auth", "Purpose")
    assert result == "## Purpose Guide\n\nThis section explains the purpose."


def test_list_section_guides_returns_all(db_session: Session) -> None:
    """list_section_guides returns all guides for the document."""
    _make_project(db_session)
    _make_doc(db_session, doc_id="module-auth")

    svc = DocService(db_session)
    svc.save_section_guide("test-proj", "module-auth", "Purpose", "Purpose guide content")
    svc.save_section_guide("test-proj", "module-auth", "Architecture", "Architecture guide content")
    svc.save_section_guide("test-proj", "module-auth", "Usage", "Usage guide content")
    db_session.flush()

    guides = svc.list_section_guides("test-proj", "module-auth")
    assert len(guides) == 3
    assert {g.section_name for g in guides} == {"Purpose", "Architecture", "Usage"}


def test_delete_section_guide_returns_false_when_not_found(db_session: Session) -> None:
    """Deleting a non-existent section guide returns False without raising."""
    _make_project(db_session)
    _make_doc(db_session, doc_id="module-auth")

    svc = DocService(db_session)
    result = svc.delete_section_guide("test-proj", "nonexistent-doc", "Purpose")
    assert result is False


# ---------------------------------------------------------------------------
# test_save_section_guide_updates_existing
# ---------------------------------------------------------------------------


def test_save_section_guide_updates_existing(db_session: Session) -> None:
    """Calling save_section_guide twice updates the existing row, not duplicates."""
    _make_project(db_session)
    _make_doc(db_session, doc_id="module-auth")

    svc = DocService(db_session)
    svc.save_section_guide("test-proj", "module-auth", "Purpose", "First version")
    db_session.flush()

    svc.save_section_guide("test-proj", "module-auth", "Purpose", "Second version")
    db_session.flush()

    guides = svc.list_section_guides("test-proj", "module-auth")
    assert len(guides) == 1
    assert guides[0].guide_md == "Second version"

    result = svc.get_section_guide("test-proj", "module-auth", "Purpose")
    assert result == "Second version"


# ---------------------------------------------------------------------------
# test_section_guides_snapshot_captured_at_job_creation
# ---------------------------------------------------------------------------


def test_section_guides_snapshot_captured_at_job_creation(db_session: Session) -> None:
    """section_guides_snapshot in the created job reflects all section guides at creation time."""
    _make_project(db_session)
    _make_doc(db_session, doc_id="module-auth")

    svc = DocService(db_session)
    svc.save_section_guide("test-proj", "module-auth", "Purpose", "Purpose guide")
    svc.save_section_guide("test-proj", "module-auth", "Architecture", "Architecture guide")
    db_session.flush()

    job = svc.create_doc_job("test-proj", "module-auth")
    db_session.flush()

    assert job.section_guides_snapshot == {
        "Purpose": "Purpose guide",
        "Architecture": "Architecture guide",
    }


# ---------------------------------------------------------------------------
# test_section_guides_snapshot_none_when_no_guides
# ---------------------------------------------------------------------------


def test_section_guides_snapshot_none_when_no_guides(db_session: Session) -> None:
    """If no section guides exist, section_guides_snapshot is None in the job."""
    _make_project(db_session)
    _make_doc(db_session, doc_id="module-auth")

    svc = DocService(db_session)
    job = svc.create_doc_job("test-proj", "module-auth")
    db_session.flush()

    assert job.section_guides_snapshot is None


# ---------------------------------------------------------------------------
# test_section_guides_snapshot_uses_document_key
# ---------------------------------------------------------------------------


def test_section_guides_snapshot_uses_document_key(db_session: Session) -> None:
    """When a section guide with section_name='Document' exists, the snapshot key is 'Document'.

    This covers the case where a document has no H2 headings, so the guide is stored
    under the sentinel section name 'Document'.
    """
    _make_project(db_session)
    _make_doc(db_session, doc_id="module-auth", content="# Auth Module\n\nNo H2 headings here.")

    svc = DocService(db_session)
    svc.save_section_guide(
        "test-proj", "module-auth", "Document", "## Document Guide\n\nTop-level guide."
    )
    db_session.flush()

    job = svc.create_doc_job("test-proj", "module-auth")
    db_session.flush()

    assert job.section_guides_snapshot == {"Document": "## Document Guide\n\nTop-level guide."}
