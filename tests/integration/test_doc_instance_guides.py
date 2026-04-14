"""Integration tests for DocInstanceGuide CRUD and guide_snapshot override logic.

All tests use the testcontainer PostgreSQL session — never connect to localhost:5433.
Each test is independent and gets a rolled-back transaction.

Tests cover:
- AC1: Instance guide overrides type guide in guide_snapshot
- AC2: Falls back to type guide when no instance override
- AC3: Falls back to None when neither guide exists
- AC4: Instance guide CRUD round-trip
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


_TYPE_GUIDE_MODULE = "# Module Type Guide\nModule-specific editorial guidelines."
_INSTANCE_GUIDE_CONTENT = "# Instance Guide Override\nCustom instance-level content."


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
    doc_id: str = "test-doc",
    doc_type: DocType = DocType.module,
) -> ProjectDoc:
    doc = ProjectDoc(
        id=f"{project_id}:{doc_id}",
        project_id=project_id,
        doc_id=doc_id,
        title="Test Document",
        slug=doc_id.replace("_", "-"),
        doc_type=doc_type,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        status=DocStatus.draft,
        audience=["developers"],
        source_paths=["src/test.rs"],
    )
    session.add(doc)
    session.flush()
    return doc


# ---------------------------------------------------------------------------
# AC1 — Instance guide overrides type guide in snapshot
# ---------------------------------------------------------------------------


def test_instance_guide_overrides_type_guide_in_snapshot(db_session: Session) -> None:
    """When both a type guide and instance guide exist, instance wins."""
    _make_project(db_session)
    _make_doc(db_session, doc_id="arch-overview", doc_type=DocType.module)

    svc = DocService(db_session)
    svc.save_type_guide("module", _TYPE_GUIDE_MODULE)
    db_session.commit()

    svc.save_instance_guide("test-proj", "arch-overview", _INSTANCE_GUIDE_CONTENT)
    db_session.commit()

    job = svc.create_doc_job("test-proj", "arch-overview")
    db_session.commit()

    assert job.guide_snapshot == _INSTANCE_GUIDE_CONTENT
    assert job.guide_snapshot != _TYPE_GUIDE_MODULE


# ---------------------------------------------------------------------------
# AC2 — Falls back to type guide when no instance override
# ---------------------------------------------------------------------------


def test_falls_back_to_type_guide_when_no_instance_override(db_session: Session) -> None:
    """When no instance guide exists, type guide content is snapshotted."""
    _make_project(db_session)
    _make_doc(db_session, doc_id="overview", doc_type=DocType.module)

    svc = DocService(db_session)
    svc.save_type_guide("module", _TYPE_GUIDE_MODULE)
    db_session.commit()

    job = svc.create_doc_job("test-proj", "overview")
    db_session.commit()

    assert job.guide_snapshot == _TYPE_GUIDE_MODULE
    assert job.guide_snapshot != _INSTANCE_GUIDE_CONTENT


# ---------------------------------------------------------------------------
# AC3 — Falls back to None when neither guide exists
# ---------------------------------------------------------------------------


def test_falls_back_to_none_when_neither_guide_exists(db_session: Session) -> None:
    """When no type guide and no instance guide, snapshot is None with no exception."""
    _make_project(db_session)
    _make_doc(db_session, doc_id="unknown-doc", doc_type=DocType.module)

    svc = DocService(db_session)

    job = svc.create_doc_job("test-proj", "unknown-doc")
    db_session.commit()

    assert job.guide_snapshot is None


# ---------------------------------------------------------------------------
# AC4 — Instance guide CRUD round-trip
# ---------------------------------------------------------------------------


def test_instance_guide_crud_round_trip(db_session: Session) -> None:
    """save -> get -> delete -> get returns None after deletion."""
    _make_project(db_session)
    _make_doc(db_session, doc_id="my-doc")

    svc = DocService(db_session)
    svc.save_instance_guide("test-proj", "my-doc", "## My Guide\nCustom content.")
    db_session.commit()

    assert svc.get_instance_guide("test-proj", "my-doc") == "## My Guide\nCustom content."

    deleted = svc.delete_instance_guide("test-proj", "my-doc")
    db_session.commit()

    assert deleted is True
    assert svc.get_instance_guide("test-proj", "my-doc") is None


def test_delete_instance_guide_returns_false_when_not_found(db_session: Session) -> None:
    """delete_instance_guide returns False when no guide exists for the doc."""
    _make_project(db_session)
    _make_doc(db_session, doc_id="doc-without-guide")

    svc = DocService(db_session)

    deleted = svc.delete_instance_guide("test-proj", "doc-without-guide")
    assert deleted is False


def test_save_instance_guide_updates_existing(db_session: Session) -> None:
    """Calling save_instance_guide twice updates the existing row."""
    _make_project(db_session)
    _make_doc(db_session, doc_id="updatable-doc")

    svc = DocService(db_session)
    svc.save_instance_guide("test-proj", "updatable-doc", "Version 1")
    db_session.commit()

    svc.save_instance_guide("test-proj", "updatable-doc", "Version 2")
    db_session.commit()

    assert svc.get_instance_guide("test-proj", "updatable-doc") == "Version 2"
