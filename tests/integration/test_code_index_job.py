"""Integration tests for CodeIndexJob ORM model."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError

from orch.db.models import CodeIndexJob, Project, ProjectDoc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestCodeIndexJobDefaults:
    def test_create_code_index_job_defaults(
        self, db_session: Session, test_project: Project
    ) -> None:
        """Given: a valid project_id from test_project fixture
        When: a CodeIndexJob is inserted with only project_id
        Then: status='queued', provider='local', files_discovered=0,
              files_indexed=0, chunks_created=0, languages_detected=[],
              errors=[], id is auto-generated (non-null UUID string)
        """
        job = CodeIndexJob(project_id=test_project.id)
        db_session.add(job)
        db_session.flush()

        assert job.id is not None
        assert len(job.id) > 0
        assert job.status == "queued"
        assert job.provider == "local"
        assert job.files_discovered == 0
        assert job.files_indexed == 0
        assert job.chunks_created == 0
        assert job.languages_detected == []
        assert job.errors == []


class TestCodeIndexJobAllFields:
    def test_create_code_index_job_all_fields(
        self, db_session: Session, test_project: Project
    ) -> None:
        """Given: valid project_id and a valid doc_id (create a minimal ProjectDoc first)
        When: CodeIndexJob inserted with all fields populated
        Then: all values read back correctly
        """
        doc = ProjectDoc(
            id=f"{test_project.id}:test-doc",
            project_id=test_project.id,
            doc_id="test-doc",
            title="Test Doc",
            slug="test-doc",
            doc_type="module",
            tier="fully_automated",
            editorial_category="technical",
            status="planned",
        )
        db_session.add(doc)
        db_session.flush()

        job = CodeIndexJob(
            project_id=test_project.id,
            status="running",
            provider="local",
            llm_model="gemma4:26b",
            embed_model="qwen3-embedding:8b",
            index_tier="balanced",
            files_discovered=42,
            files_indexed=40,
            chunks_created=120,
            languages_detected=["python", "typescript"],
            errors=[],
            doc_id=doc.id,
        )
        db_session.add(job)
        db_session.flush()

        assert job.id is not None
        assert job.project_id == test_project.id
        assert job.status == "running"
        assert job.provider == "local"
        assert job.llm_model == "gemma4:26b"
        assert job.embed_model == "qwen3-embedding:8b"
        assert job.index_tier == "balanced"
        assert job.files_discovered == 42
        assert job.files_indexed == 40
        assert job.chunks_created == 120
        assert job.languages_detected == ["python", "typescript"]
        assert job.errors == []
        assert job.doc_id == doc.id


class TestCodeIndexJobStatusTransitions:
    def test_code_index_job_status_transitions(
        self, db_session: Session, test_project: Project
    ) -> None:
        """Given: a CodeIndexJob with status='queued'
        When: status updated to 'running', then to 'completed' with completed_at set
        Then: each read-back reflects the new value
        """
        job = CodeIndexJob(project_id=test_project.id)
        db_session.add(job)
        db_session.flush()
        assert job.status == "queued"
        assert job.completed_at is None

        job.status = "running"
        db_session.flush()
        assert job.status == "running"

        job.status = "completed"
        job.completed_at = datetime.now(UTC).replace(tzinfo=None)
        db_session.flush()
        assert job.status == "completed"
        assert job.completed_at is not None


class TestCodeIndexJobFKConstraints:
    def test_code_index_job_fk_invalid_project(self, db_session: Session) -> None:
        """Given: a project_id that does not exist in the projects table
        When: CodeIndexJob insert is attempted
        Then: IntegrityError is raised
        """
        job = CodeIndexJob(project_id="nonexistent-project")
        db_session.add(job)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestCodeIndexJobDocIdNull:
    def test_code_index_job_doc_id_null(self, db_session: Session, test_project: Project) -> None:
        """Given: a CodeIndexJob with doc_id=None
        When: inserted and read back
        Then: doc_id is None
        """
        job = CodeIndexJob(project_id=test_project.id, doc_id=None)
        db_session.add(job)
        db_session.flush()

        assert job.doc_id is None


class TestCodeIndexJobLanguagesDetected:
    def test_code_index_job_languages_detected_jsonb(
        self, db_session: Session, test_project: Project
    ) -> None:
        """Given: a CodeIndexJob
        When: languages_detected is set to ["python", "typescript"]
        Then: it reads back as a Python list ["python", "typescript"]
        """
        job = CodeIndexJob(
            project_id=test_project.id,
            languages_detected=["python", "typescript"],
        )
        db_session.add(job)
        db_session.flush()

        assert job.languages_detected == ["python", "typescript"]


class TestCodeIndexJobErrors:
    def test_code_index_job_errors_jsonb(self, db_session: Session, test_project: Project) -> None:
        """Given: a CodeIndexJob
        When: errors is set to [{"file": "foo.py", "msg": "parse error"}]
        Then: it reads back as the same Python dict structure
        """
        error_entry = [{"file": "foo.py", "msg": "parse error"}]
        job = CodeIndexJob(
            project_id=test_project.id,
            errors=error_entry,
        )
        db_session.add(job)
        db_session.flush()

        assert job.errors == error_entry
        assert job.errors[0]["file"] == "foo.py"
        assert job.errors[0]["msg"] == "parse error"
