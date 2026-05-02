"""Regression tests for I-00056 — chip strip on Code page.

Tests verify:
1. The chips endpoint returns one link per parsed module.
2. The chip-strip slot appears in DOM order before the prose body.

Uses FastAPI TestClient + PostgreSQL testcontainer (db_session fixture).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import CodeIndexJob, DocType, EditorialCategory, Project, ProjectDoc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


_ARCH_MAP_CONTENT_WITH_MODULES = (
    "# Architecture Map\n"
    "## Purpose\n"
    "A test project for I-00056.\n\n"
    "## Components\n"
    "- **Daemon (`orch/daemon/`)**: background runner\n"
    "- **Dashboard (`dashboard/`)**: web UI\n\n"
    "## Entry Points\n"
    "- Main CLI entry point\n"
)


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a TestClient that overrides get_db to use the test db_session."""
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


def _seed_project_doc(
    db_session: Session,
    project_id: str,
    doc_id: str,
    doc_type: DocType,
    content: str,
) -> ProjectDoc:
    """Seed a single ProjectDoc for the test project."""
    doc = ProjectDoc(
        id=f"{project_id}:{doc_id}",
        project_id=project_id,
        doc_id=doc_id,
        title=f"Test — {doc_id}",
        slug=doc_id,
        doc_type=doc_type,
        tier="fully_automated",
        editorial_category=EditorialCategory.technical,
        status="published",
        content=content,
        generated_by="code-understanding:level1",
        source_paths=["*"],
    )
    db_session.add(doc)
    db_session.flush()
    return doc


def _seed_completed_code_index_job(db_session: Session, project_id: str, doc_id: str) -> None:
    """Seed a completed CodeIndexJob pointing at the architecture-map doc."""
    job = CodeIndexJob(
        project_id=project_id,
        status="completed",
        provider="local",
        llm_model="gemma4:e4b",
        embed_model="qwen3-embedding:8b",
        index_tier="balanced",
        files_discovered=10,
        files_indexed=8,
        chunks_created=25,
        languages_detected=["python"],
        errors=[],
        doc_id=f"{project_id}:{doc_id}",
        completed_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(job)
    db_session.flush()


class TestChipsEndpoint:
    """Tests for GET /api/projects/{project_id}/code/modules/chips."""

    def test_chips_endpoint_returns_one_link_per_module(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Endpoint must return one chip link per module parsed from the arch map."""
        _seed_project_doc(
            db_session,
            project_id=test_project.id,
            doc_id="architecture-map",
            doc_type=DocType.architecture,
            content=_ARCH_MAP_CONTENT_WITH_MODULES,
        )
        _seed_completed_code_index_job(db_session, test_project.id, doc_id="architecture-map")
        db_session.commit()

        resp = client.get(f"/api/projects/{test_project.id}/code/modules/chips")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        html = resp.text
        assert 'id="code-component-chips"' in html, (
            "Chips wrapper div must have id='code-component-chips'"
        )
        # Two modules: orch-daemon and dashboard
        assert html.count('hx-target="#code-detail-panel"') == 2, (
            f"Expected 2 htmx chip links, got {html.count('hx-target="#code-detail-panel"')}"
        )
        assert "/code/modules/orch-daemon" in html, "Expected chip link for orch-daemon module"
        assert "/code/modules/dashboard" in html, "Expected chip link for dashboard module"


class TestChipsSlotBeforeProse:
    """Tests for chip-strip-before-prose DOM ordering on the /code page."""

    def test_chips_slot_renders_before_prose_body(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """The chips slot must appear in DOM order before the prose body.

        This is the primary regression test for I-00056: the user must land
        on navigation (chips) before encountering the prose. The chip strip
        itself is loaded asynchronously by htmx, so we assert on the slot
        element (hx-trigger load), not the async-loaded chips div.
        """
        _seed_project_doc(
            db_session,
            project_id=test_project.id,
            doc_id="architecture-map",
            doc_type=DocType.architecture,
            content=_ARCH_MAP_CONTENT_WITH_MODULES,
        )
        _seed_completed_code_index_job(db_session, test_project.id, doc_id="architecture-map")
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/code")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

        html = resp.text
        chips_idx = html.find('id="code-component-chips-slot"')
        prose_idx = html.find('class="prose-doc')

        assert chips_idx >= 0, (
            "Chip slot element (id='code-component-chips-slot') is missing from page"
        )
        assert prose_idx >= 0, "Prose body element (class='prose-doc') is missing from page"
        assert chips_idx < prose_idx, (
            f"Chip slot (index {chips_idx}) must precede prose body (index {prose_idx})"
        )

    def test_i00056_chip_strip_renders_before_prose_body(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """RED reproduction test — chip strip must appear before prose body in DOM order."""
        _seed_project_doc(
            db_session,
            project_id=test_project.id,
            doc_id="architecture-map",
            doc_type=DocType.architecture,
            content=_ARCH_MAP_CONTENT_WITH_MODULES,
        )
        _seed_completed_code_index_job(db_session, test_project.id, doc_id="architecture-map")
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/code")
        assert resp.status_code == 200

        html = resp.text
        # The chip strip itself is loaded asynchronously via htmx; the page
        # initially contains the htmx slot that triggers the load.
        chips_idx = html.find('id="code-component-chips-slot"')
        prose_idx = html.find('class="prose-doc')
        assert chips_idx >= 0, "chip strip slot missing"
        assert prose_idx >= 0, "prose body missing"
        assert chips_idx < prose_idx, "chip strip must appear before prose body"
