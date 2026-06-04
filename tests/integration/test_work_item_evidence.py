"""Integration tests for WorkItemEvidence model against a real PostgreSQL testcontainer.

Tests verify:
- WorkItemEvidence can be inserted and queried back
- EvidencePhase enum values work correctly
- BLOB content can be stored and retrieved
- Unique constraint uq_evidence_per_file enforces (project_id, work_item_id, phase, filename)
- FK to work_items without cascade — evidences survive work_item deletion
- Index ix_evidence_project_item_phase works
- Invalid EvidencePhase values are rejected
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError

from orch.db.models import (
    EvidencePhase,
    Project,
    WorkItem,
    WorkItemEvidence,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def make_project(project_id: str = "test-proj") -> Project:
    return Project(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
    )


def make_work_item(
    project_id: str = "test-proj",
    item_id: str = "F-00001",
    title: str = "My Feature",
) -> WorkItem:
    return WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Feature,
        title=title,
    )


def make_evidence(
    project_id: str = "test-proj",
    work_item_id: str = "F-00001",
    phase: EvidencePhase = EvidencePhase.pre,
    filename: str = "screenshot.png",
    content: bytes = b"fake PNG bytes",
    content_type: str = "image/png",
) -> WorkItemEvidence:
    return WorkItemEvidence(
        project_id=project_id,
        work_item_id=work_item_id,
        phase=phase,
        filename=filename,
        content_type=content_type,
        content=content,
        size_bytes=len(content),
    )


class TestEvidencePhaseEnum:
    def test_evidence_phase_has_pre_value(self) -> None:
        assert EvidencePhase.pre.value == "pre"

    def test_evidence_phase_has_post_value(self) -> None:
        assert EvidencePhase.post.value == "post"

    def test_evidence_phase_count(self) -> None:
        assert len(EvidencePhase) == 2


class TestWorkItemEvidenceInsert:
    def test_insert_and_query_pre_phase(self, db_session: Session, test_project: Project) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        evidence = make_evidence(phase=EvidencePhase.pre)
        db_session.add(evidence)
        db_session.flush()

        result = (
            db_session.query(WorkItemEvidence)
            .filter_by(
                project_id="test-proj",
                work_item_id="F-00001",
                phase=EvidencePhase.pre,
                filename="screenshot.png",
            )
            .one()
        )

        assert result is not None
        assert result.content_type == "image/png"
        assert result.size_bytes == len(b"fake PNG bytes")
        assert result.step_id is None

    def test_insert_and_query_post_phase(self, db_session: Session, test_project: Project) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        evidence = make_evidence(
            phase=EvidencePhase.post,
            filename="post-verify.png",
            content=b"post verification bytes",
        )
        db_session.add(evidence)
        db_session.flush()

        result = (
            db_session.query(WorkItemEvidence)
            .filter_by(
                project_id="test-proj",
                work_item_id="F-00001",
                phase=EvidencePhase.post,
                filename="post-verify.png",
            )
            .one()
        )

        assert result is not None
        assert result.phase == EvidencePhase.post
        assert result.content == b"post verification bytes"

    def test_blob_content_stored_and_retrieved(
        self, db_session: Session, test_project: Project
    ) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        evidence = make_evidence(content=png_content)
        db_session.add(evidence)
        db_session.flush()

        result = (
            db_session.query(WorkItemEvidence)
            .filter_by(
                project_id="test-proj",
                work_item_id="F-00001",
                filename="screenshot.png",
            )
            .one()
        )

        assert result.content == png_content
        assert result.size_bytes == len(png_content)

    def test_multiple_evidences_same_work_item_different_phase(
        self, db_session: Session, test_project: Project
    ) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        pre_evidence = make_evidence(phase=EvidencePhase.pre, filename="pre.png")
        post_evidence = make_evidence(phase=EvidencePhase.post, filename="post.png")
        db_session.add(pre_evidence)
        db_session.add(post_evidence)
        db_session.flush()

        evidences = (
            db_session.query(WorkItemEvidence)
            .filter_by(project_id="test-proj", work_item_id="F-00001")
            .all()
        )
        assert len(evidences) == 2
        phases = {e.phase for e in evidences}
        assert phases == {EvidencePhase.pre, EvidencePhase.post}

    def test_multiple_evidences_same_phase_different_filename(
        self, db_session: Session, test_project: Project
    ) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        evidence1 = make_evidence(phase=EvidencePhase.pre, filename="screenshot1.png")
        evidence2 = make_evidence(phase=EvidencePhase.pre, filename="screenshot2.png")
        db_session.add(evidence1)
        db_session.add(evidence2)
        db_session.flush()

        evidences = (
            db_session.query(WorkItemEvidence)
            .filter_by(project_id="test-proj", work_item_id="F-00001", phase=EvidencePhase.pre)
            .all()
        )
        assert len(evidences) == 2
        filenames = {e.filename for e in evidences}
        assert filenames == {"screenshot1.png", "screenshot2.png"}

    def test_step_id_is_optional(self, db_session: Session, test_project: Project) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        evidence = make_evidence()
        assert evidence.step_id is None
        db_session.add(evidence)
        db_session.flush()

        result = db_session.query(WorkItemEvidence).one()
        assert result.step_id is None

    def test_step_id_can_be_set(self, db_session: Session, test_project: Project) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        evidence = make_evidence()
        evidence.step_id = "S07"
        db_session.add(evidence)
        db_session.flush()

        result = db_session.query(WorkItemEvidence).one()
        assert result.step_id == "S07"

    def test_captured_at_defaults_to_now(self, db_session: Session, test_project: Project) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        evidence = make_evidence()
        db_session.add(evidence)
        db_session.flush()

        assert evidence.captured_at is not None


class TestWorkItemEvidenceUniqueConstraint:
    def test_duplicate_project_work_item_phase_filename_rejected(
        self, db_session: Session, test_project: Project
    ) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        evidence1 = make_evidence(phase=EvidencePhase.pre, filename="screenshot.png")
        db_session.add(evidence1)
        db_session.flush()

        evidence2 = make_evidence(phase=EvidencePhase.pre, filename="screenshot.png")
        db_session.add(evidence2)
        with pytest.raises((IntegrityError, Exception)):  # noqa: B017
            db_session.flush()

    def test_same_filename_different_phase_allowed(
        self, db_session: Session, test_project: Project
    ) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        evidence1 = make_evidence(phase=EvidencePhase.pre, filename="screenshot.png")
        evidence2 = make_evidence(phase=EvidencePhase.post, filename="screenshot.png")
        db_session.add(evidence1)
        db_session.add(evidence2)
        db_session.flush()

        evidences = (
            db_session.query(WorkItemEvidence)
            .filter_by(project_id="test-proj", work_item_id="F-00001")
            .all()
        )
        assert len(evidences) == 2


class TestWorkItemEvidenceFKNoCascade:
    def test_work_item_deletion_blocked_when_evidence_exists(
        self, db_session: Session, test_project: Project
    ) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        evidence = make_evidence()
        db_session.add(evidence)
        db_session.flush()

        with pytest.raises((IntegrityError, Exception)):  # noqa: B017
            db_session.execute(
                text(
                    "DELETE FROM work_items WHERE project_id = :project_id AND id = :work_item_id"
                ),
                {"project_id": "test-proj", "work_item_id": "F-00001"},
            )

    def test_work_item_deletable_when_no_evidence(
        self, db_session: Session, test_project: Project
    ) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        db_session.execute(
            text("DELETE FROM work_items WHERE project_id = :project_id AND id = :work_item_id"),
            {"project_id": "test-proj", "work_item_id": "F-00001"},
        )
        db_session.commit()

        found = db_session.query(WorkItem).filter_by(project_id="test-proj", id="F-00001").all()
        assert len(found) == 0

    def test_work_item_deletable_after_evidence_removed(
        self, db_session: Session, test_project: Project
    ) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        evidence = make_evidence()
        db_session.add(evidence)
        db_session.flush()
        evidence_id = evidence.id

        db_session.delete(evidence)
        db_session.flush()

        db_session.execute(
            text("DELETE FROM work_items WHERE project_id = :project_id AND id = :work_item_id"),
            {"project_id": "test-proj", "work_item_id": "F-00001"},
        )
        db_session.commit()

        work_items = (
            db_session.query(WorkItem).filter_by(project_id="test-proj", id="F-00001").all()
        )
        assert len(work_items) == 0

        found = db_session.query(WorkItemEvidence).filter_by(id=evidence_id).all()
        assert len(found) == 0


class TestWorkItemEvidenceIndex:
    def test_index_on_project_work_item_phase(
        self, db_session: Session, test_project: Project
    ) -> None:
        db_session.add(make_work_item())
        db_session.flush()

        for phase in EvidencePhase:
            for i in range(3):
                db_session.add(
                    make_evidence(
                        phase=phase,
                        filename=f"file_{phase.value}_{i}.png",
                    )
                )
        db_session.flush()

        results = (
            db_session.query(WorkItemEvidence)
            .filter_by(project_id="test-proj", work_item_id="F-00001", phase=EvidencePhase.pre)
            .all()
        )
        assert len(results) == 3
        for r in results:
            assert r.phase == EvidencePhase.pre


class TestWorkItemEvidenceEnumConstraint:
    def test_invalid_evidence_phase_rejected(
        self, db_session: Session, test_project: Project
    ) -> None:
        with pytest.raises(DataError):
            db_session.execute(
                text(
                    "INSERT INTO work_item_evidences "
                    "(project_id, work_item_id, phase, filename, "
                    "content_type, content, size_bytes) "
                    "VALUES ('test-proj', 'F-00001', 'invalid_phase', "
                    "'x.png', 'image/png', 'x', 1)"
                )
            )
