"""Integration tests for GET /project/{project_id}/jobs and detail routes.

These tests verify the full HTTP round-trip using FastAPI's TestClient
against a PostgreSQL testcontainer (never the live DB).

Routes tested:
  GET /project/{project_id}/jobs
  GET /project/{project_id}/jobs/fragment/table
  GET /project/{project_id}/jobs/{job_type}/{job_id}

All four job sources are seeded: code_index_jobs, doc_generation_jobs,
batches, project_docs (doc_type=research).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchStatus,
    CodeIndexJob,
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
    from collections.abc import Generator

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    import os

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
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_all_sources(db_session: Session, project_id: str) -> dict[str, str]:
    """Seed one row in each of the four job sources. Returns IDs."""
    now = datetime.now(UTC)

    cij = CodeIndexJob(
        id="cij-test-001",
        project_id=project_id,
        status="completed",
        provider="local",
        llm_model="gemma4:31b",
        embed_model="manutic/nomic-embed-code",
        index_tier="balanced",
        files_discovered=10,
        files_indexed=9,
        chunks_created=120,
        languages_detected=["Python"],
        errors=[],
        triggered_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=1),
    )
    db_session.add(cij)
    db_session.flush()  # triggers before_insert → allocates public_id
    cij_id = cij.public_id or cij.id

    doc_id_for_dgj = f"{project_id}:doc-test-001"
    db_session.add(
        ProjectDoc(
            id=doc_id_for_dgj,
            project_id=project_id,
            doc_id="doc-test-001",
            title="Test Document",
            slug="test-doc",
            doc_type=DocType.architecture,
            tier=DocTier.semi_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.published,
            audience=[],
            source_paths=[],
            created_at=now - timedelta(hours=3),
            updated_at=now - timedelta(hours=1),
        )
    )
    db_session.flush()

    dgj = DocGenerationJob(
        id="dgj-test-001",
        project_id=project_id,
        doc_id=doc_id_for_dgj,
        status=JobStatus.completed,
        requested_at=now - timedelta(hours=3),
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=1),
        skill_used="skill:iw-doc-generator",
        trigger_reason="manual",
        duration_seconds=3600,
        created_at=now - timedelta(hours=3),
    )
    db_session.add(dgj)
    db_session.flush()  # triggers before_insert → allocates public_id
    dgj_id = dgj.public_id or dgj.id

    batch_id = "B-TEST-001"
    db_session.add(
        Batch(
            id=batch_id,
            project_id=project_id,
            status=BatchStatus.completed,
            max_parallel=4,
            cli_tool="opencode",
            auto_publish=False,
            created_at=now - timedelta(hours=4),
            completed_at=now - timedelta(hours=2),
        )
    )

    res_doc_id = "res-test-001"
    db_session.add(
        ProjectDoc(
            id=f"{project_id}:res-test-001",
            project_id=project_id,
            doc_id=res_doc_id,
            title="Research: Test",
            slug="research-test",
            doc_type=DocType.research,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.published,
            audience=[],
            source_paths=[],
            content="# Research Content",
            version=1,
            generated_at=now - timedelta(hours=1),
            generated_by="skill:iw-research",
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=1),
        )
    )

    db_session.flush()
    return {
        "cij_id": cij_id,
        "dgj_id": dgj_id,
        "batch_id": batch_id,
        "res_doc_id": res_doc_id,
        "doc_id": doc_id_for_dgj,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_jobs_list_returns_200_and_job_ids(
    client: TestClient, db_session: Session, test_project: Project
) -> None:
    """GET /project/{p}/jobs returns HTTP 200 and HTML containing each seeded job's id."""
    ids = _seed_all_sources(db_session, test_project.id)
    db_session.commit()

    resp = client.get(f"/project/{test_project.id}/jobs")
    assert resp.status_code == 200
    html = resp.text
    assert ids["cij_id"] in html
    assert ids["dgj_id"] in html
    assert ids["batch_id"] in html
    assert ids["res_doc_id"] in html


def test_jobs_list_type_filter_excludes_other_types(
    client: TestClient, db_session: Session, test_project: Project
) -> None:
    """GET /project/{p}/jobs?type=code_mapping returns HTML with code_mapping rows only."""
    ids = _seed_all_sources(db_session, test_project.id)
    db_session.commit()

    resp = client.get(f"/project/{test_project.id}/jobs?type=code_mapping")
    assert resp.status_code == 200
    html = resp.text
    assert ids["cij_id"] in html
    assert ids["batch_id"] not in html
    assert ids["dgj_id"] not in html
    assert ids["res_doc_id"] not in html


def test_jobs_fragment_table_returns_no_html_body_tags(
    client: TestClient, db_session: Session, test_project: Project
) -> None:
    """GET /project/{p}/jobs/fragment/table returns an htmx fragment — no <html> or <body>."""
    _seed_all_sources(db_session, test_project.id)
    db_session.commit()

    resp = client.get(f"/project/{test_project.id}/jobs/fragment/table")
    assert resp.status_code == 200
    html = resp.text
    assert "<html>" not in html
    assert "<body" not in html


def test_code_mapping_job_detail_returns_200(
    client: TestClient, db_session: Session, test_project: Project
) -> None:
    """GET /project/{p}/jobs/code_mapping/{job_id} returns HTTP 200 with job fields."""
    cij = CodeIndexJob(
        id="cij-detail-001",
        project_id=test_project.id,
        status="completed",
        provider="local",
        llm_model="gemma4:31b",
        embed_model="manutic/nomic-embed-code",
        index_tier="balanced",
        files_discovered=10,
        files_indexed=9,
        chunks_created=120,
        languages_detected=["Python"],
        errors=[],
        triggered_at=datetime.now(UTC) - timedelta(hours=2),
        completed_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(cij)
    db_session.flush()  # triggers before_insert → allocates public_id
    db_session.commit()
    cij_public_id = cij.public_id or cij.id

    resp = client.get(f"/project/{test_project.id}/jobs/code_mapping/{cij_public_id}")
    assert resp.status_code == 200
    html = resp.text
    assert "gemma4:31b" in html
    assert "balanced" in html


def test_code_mapping_job_detail_bogus_id_returns_404(
    client: TestClient, db_session: Session, test_project: Project
) -> None:
    """GET /project/{p}/jobs/code_mapping/bogus-id returns HTTP 404."""
    resp = client.get(f"/project/{test_project.id}/jobs/code_mapping/bogus-id")
    assert resp.status_code == 404


def test_jobs_invalid_type_returns_422(
    client: TestClient, db_session: Session, test_project: Project
) -> None:
    """GET /project/{p}/jobs/invalid_type/{job_id} returns HTTP 422 for unknown job type."""
    resp = client.get(f"/project/{test_project.id}/jobs/invalid_type/some-id")
    assert resp.status_code == 422


def test_jobs_bogus_project_returns_404(
    client: TestClient, db_session: Session, test_project: Project
) -> None:
    """GET /project/bogus-project/jobs returns HTTP 404 when project does not exist."""
    resp = client.get("/project/bogus-project/jobs")
    assert resp.status_code == 404
