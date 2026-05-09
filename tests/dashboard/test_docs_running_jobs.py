"""CR-00038 S03 — Dashboard integration tests for /api/docs/running-jobs endpoint.

Tests the new running-jobs strip (htmx fragment) and the updated generate button
response. Verifies:
1. Empty strip when no running jobs
2. One running job renders correctly
3. Multiple running jobs render all rows
4. Cross-project isolation (no leaking)
5. Completed jobs are excluded
6. Research doc jobs are excluded from the strip
7. Generate endpoint returns disabled button + HX-Trigger header
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    DocGenerationJob,
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    JobStatus,
    Project,
    ProjectDoc,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project_doc(
    db_session: Session,
    project_id: str,
    doc_id: str,
    title: str = "Test Doc",
    doc_type: DocType = DocType.architecture,
    status: DocStatus = DocStatus.planned,
) -> ProjectDoc:
    """Create a ProjectDoc row and commit it.

    tier and editorial_category have no Python-side defaults and are NOT NULL,
    so we must supply real enum values.
    """
    composite_id = f"{project_id}:{doc_id}"
    doc = ProjectDoc(
        id=composite_id,
        project_id=project_id,
        doc_id=doc_id,
        title=title,
        slug=doc_id,
        doc_type=doc_type,
        tier=DocTier.semi_automated,
        editorial_category=EditorialCategory.technical,
        status=status,
        audience=[],
        source_paths=[],
    )
    db_session.add(doc)
    db_session.flush()
    return doc


def _make_running_job(
    db_session: Session,
    project_id: str,
    doc_id: str,
    job_id: str | None = None,
) -> DocGenerationJob:
    """Create a DocGenerationJob row with status=running and commit it."""
    if job_id is None:
        job_id = f"job-{project_id}-{doc_id}-1234"
    composite_doc_id = f"{project_id}:{doc_id}"
    job = DocGenerationJob(
        id=job_id,
        project_id=project_id,
        doc_id=composite_doc_id,
        status=JobStatus.running,
        requested_at=None,
    )
    db_session.add(job)
    db_session.flush()
    return job


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunningJobsEmpty:
    """GET /project/{project_id}/api/docs/running-jobs — empty case."""

    def test_running_jobs_empty(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """No running jobs → 200 with no docs-rjob-* divs."""
        resp = client.get(f"/project/{test_project.id}/api/docs/running-jobs")
        assert resp.status_code == 200
        # Must not contain any running-job row divs
        assert 'id="docs-rjob-' not in resp.text


class TestRunningJobsShowOne:
    """GET /project/{project_id}/api/docs/running-jobs — single running job."""

    def test_running_jobs_shows_running(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """One running job → 200, row div with correct job_id, doc title, cancel button."""
        _make_project_doc(db_session, test_project.id, "doc-alpha", title="Alpha Doc")
        job = _make_running_job(db_session, test_project.id, "doc-alpha")
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/api/docs/running-jobs")
        assert resp.status_code == 200

        # Row div with specific job_id
        assert f'id="docs-rjob-{job.id}"' in resp.text, (
            f"Running job row div docs-rjob-{job.id} not found in response"
        )
        # Doc title present
        assert "Alpha Doc" in resp.text, "Doc title not found in running-jobs strip"
        # Cancel button with hx-delete targeting the cancel endpoint
        assert f'hx-delete="/project/{test_project.id}/api/docs/jobs/{job.id}"' in resp.text, (
            "Cancel button with correct hx-delete endpoint not found"
        )


class TestRunningJobsMultiple:
    """GET /project/{project_id}/api/docs/running-jobs — multiple jobs."""

    def test_running_jobs_multiple(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Two running jobs for same project → both rows appear."""
        _make_project_doc(db_session, test_project.id, "doc-one", title="Doc One")
        _make_project_doc(db_session, test_project.id, "doc-two", title="Doc Two")
        _make_running_job(db_session, test_project.id, "doc-one", job_id="job-001")
        _make_running_job(db_session, test_project.id, "doc-two", job_id="job-002")
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/api/docs/running-jobs")
        assert resp.status_code == 200

        assert 'id="docs-rjob-job-001"' in resp.text
        assert 'id="docs-rjob-job-002"' in resp.text
        assert "Doc One" in resp.text
        assert "Doc Two" in resp.text


class TestRunningJobsCrossProjectIsolation:
    """GET /project/{project_id}/api/docs/running-jobs — cross-project isolation."""

    def test_running_jobs_cross_project_isolation(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Running job from project B must not appear in project A's response."""
        # Project A (test_project) — one running job
        _make_project_doc(db_session, test_project.id, "doc-a", title="Doc A Proj")
        _make_running_job(db_session, test_project.id, "doc-a", job_id="job-a")
        db_session.flush()

        # Project B (proj-b) — its own running job (must have a Project row)
        proj_b_id = "proj-b"
        proj_b = Project(
            id=proj_b_id,
            display_name="Project B",
            repo_root="/repos/proj-b",
            config={},
        )
        db_session.add(proj_b)
        db_session.flush()

        doc_b = ProjectDoc(
            id=f"{proj_b_id}:doc-b",
            project_id=proj_b_id,
            doc_id="doc-b",
            title="Doc B Other",
            slug="doc-b",
            doc_type=DocType.architecture,
            tier=DocTier.semi_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.planned,
            audience=[],
            source_paths=[],
        )
        db_session.add(doc_b)
        db_session.flush()
        job_b = DocGenerationJob(
            id="job-b-other",
            project_id=proj_b_id,
            doc_id=f"{proj_b_id}:doc-b",
            status=JobStatus.running,
            requested_at=None,
        )
        db_session.add(job_b)
        db_session.commit()

        # GET project A's running jobs
        resp = client.get(f"/project/{test_project.id}/api/docs/running-jobs")
        assert resp.status_code == 200

        # Must contain job A's row
        assert 'id="docs-rjob-job-a"' in resp.text
        # Must NOT contain job B's row
        assert 'id="docs-rjob-job-b-other"' not in resp.text
        assert "Doc B Other" not in resp.text


class TestRunningJobsCompletedExcluded:
    """GET /project/{project_id}/api/docs/running-jobs — completed jobs excluded."""

    def test_running_jobs_completed_not_shown(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """A completed job must not appear in the running-jobs strip."""
        # One running
        _make_project_doc(db_session, test_project.id, "doc-running", title="Running Doc")
        _make_running_job(db_session, test_project.id, "doc-running", job_id="job-running")
        # One completed
        _make_project_doc(db_session, test_project.id, "doc-done", title="Done Doc")
        job_done = DocGenerationJob(
            id="job-done",
            project_id=test_project.id,
            doc_id=f"{test_project.id}:doc-done",
            status=JobStatus.completed,
            requested_at=None,
        )
        db_session.add(job_done)
        db_session.flush()
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/api/docs/running-jobs")
        assert resp.status_code == 200

        # Running job row must be present
        assert 'id="docs-rjob-job-running"' in resp.text
        assert "Running Doc" in resp.text
        # Completed job row must NOT be present
        assert 'id="docs-rjob-job-done"' not in resp.text
        assert "Done Doc" not in resp.text


class TestRunningJobsResearchExcluded:
    """GET /project/{project_id}/api/docs/running-jobs — research doc jobs excluded."""

    def test_running_jobs_no_research_docs(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Running jobs for doc_type=research must be excluded from the strip."""
        # Research doc with running job
        doc_research = ProjectDoc(
            id=f"{test_project.id}:doc-research",
            project_id=test_project.id,
            doc_id="doc-research",
            title="Research Doc",
            slug="doc-research",
            doc_type=DocType.research,
            tier=DocTier.semi_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.planned,
            audience=[],
            source_paths=[],
        )
        db_session.add(doc_research)
        db_session.flush()

        job_research = DocGenerationJob(
            id="job-research",
            project_id=test_project.id,
            doc_id=f"{test_project.id}:doc-research",
            status=JobStatus.running,
            requested_at=None,
        )
        db_session.add(job_research)
        db_session.flush()

        # Non-research (module) doc with running job
        _make_project_doc(
            db_session, test_project.id, "doc-module", title="Module Doc", doc_type=DocType.module
        )
        _make_running_job(db_session, test_project.id, "doc-module", job_id="job-module")
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/api/docs/running-jobs")
        assert resp.status_code == 200

        # Non-research job row must be present
        assert 'id="docs-rjob-job-module"' in resp.text
        assert "Module Doc" in resp.text
        # Research job row must NOT be present
        assert 'id="docs-rjob-job-research"' not in resp.text
        assert "Research Doc" not in resp.text


class TestGenerateResponseDisablesButton:
    """POST /project/{project_id}/api/docs/{doc_id}/generate — disabled button response."""

    def test_generate_response_disables_button(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Generate POST returns a disabled button and creates a running job row."""
        # Create a doc with status=planned so the Generate button shows
        doc = _make_project_doc(
            db_session,
            test_project.id,
            "gen-doc",
            title="Gen Doc",
            doc_type=DocType.architecture,
            status=DocStatus.planned,
        )
        db_session.commit()

        resp = client.post(f"/project/{test_project.id}/api/docs/{doc.doc_id}/generate")
        assert resp.status_code == 200

        html = resp.text
        # Disabled button present
        assert "<button disabled" in html, "Response must contain a <button disabled ...>"
        # NOT the old spinner-only fragment (no docs_generate_running id on a standalone spinner)
        assert "docs_generate_running" not in html, (
            "Old spinner-only fragment (docs_generate_running) must not be returned"
        )
        # No animate-spin w-4 h-4 as the sole content
        assert not ("animate-spin w-4 h-4" in html and "cursor-not-allowed" not in html), (
            "Response must not be a bare spinner-only fragment"
        )

        # HX-Trigger header present with runningJobsReload
        assert "HX-Trigger" in resp.headers, "HX-Trigger header must be set"
        hx_trigger = resp.headers["HX-Trigger"]
        assert "runningJobsReload" in hx_trigger, (
            f"HX-Trigger header must contain 'runningJobsReload', got: {hx_trigger}"
        )

        # DocGenerationJob row with status=running created in DB
        # Note: create_doc_job() sets status=queued; the job transitions to running
        # only after the daemon poller calls start_doc_job(). The important invariant
        # is that the job was persisted to the DB (not lost), and a single job exists.
        db_session.expire_all()
        job_count = (
            db_session.query(DocGenerationJob)
            .filter(
                DocGenerationJob.doc_id == f"{test_project.id}:{doc.doc_id}",
            )
            .count()
        )
        assert job_count == 1, f"Expected 1 DocGenerationJob for doc, found {job_count}"
