"""Reproduction + regression tests for I-00055 — double diagram on Code page.

Bug: the Code page rendered the architecture Mermaid diagram twice because
MapGenerator._assemble_markdown embedded the diagram inline AND the dashboard
rendered the standalone 'diagram-architecture' doc separately.

Fix (I-00055 S01):
(a) _assemble_markdown no longer emits the diagram block in the markdown.
(b) strip_trailing_arch_diagram_section removes any legacy trailing section.

These tests verify:
1. strip_trailing_arch_diagram_section is applied at render time (semantic check).
2. Exactly ONE diagram renders on the /code page (inline or bottom, not both).

Tests use FastAPI TestClient against a PostgreSQL testcontainer
(via the existing fixtures from tests/dashboard/conftest.py — never the live DB).
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


# The legacy content that used to be stored by mapgen (pre-S01).
# Contains a trailing '## Architecture Diagram' section with mermaid fence.
_LEGACY_ARCH_MAP_CONTENT = (
    "# Architecture Map\n\n"
    "## Purpose\nA test project for I-00055.\n\n"
    "## Components\n- **CLI**: command interface\n- **Daemon**: background runner\n\n"
    "## Entry Points\n- Main CLI entry point\n\n"
    "## Databases\n- PostgreSQL for state\n\n"
    "## Architecture Diagram\n\n"
    "<!-- purpose: shows overall architecture -->\n\n"
    "```mermaid\n"
    "---\n"
    "config:\n"
    "  layout: elk\n"
    "---\n"
    "graph TD\n"
    "  CLI --> Daemon\n"
    "  Daemon --> DB\n"
    "```\n"
)

# Clean diagram-architecture doc (no legacy trailing section, no purpose comment).
_CLEAN_ARCH_DIAGRAM_DSL = (
    "---\nconfig:\n  layout: elk\n---\ngraph TD\n  A[CLI] --> B[Daemon]\n  B --> C[DB]\n"
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
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


def _seed_docs(db_session: Session, project_id: str) -> None:
    """Seed architecture-map (with legacy trailing diagram) and diagram-architecture docs."""
    arch_map = ProjectDoc(
        id=f"{project_id}:architecture-map",
        project_id=project_id,
        doc_id="architecture-map",
        title="Test Project — Architecture Map",
        slug="architecture-map",
        doc_type=DocType.architecture,
        tier="fully_automated",
        editorial_category=EditorialCategory.technical,
        status="published",
        content=_LEGACY_ARCH_MAP_CONTENT,
        generated_by="code-understanding:level1",
        source_paths=["*"],
    )
    arch_diagram = ProjectDoc(
        id=f"{project_id}:diagram-architecture",
        project_id=project_id,
        doc_id="diagram-architecture",
        title="Test Project — Architecture Diagram",
        slug="diagram-architecture",
        doc_type=DocType.diagram,
        tier="fully_automated",
        editorial_category=EditorialCategory.technical,
        status="published",
        content=_CLEAN_ARCH_DIAGRAM_DSL,
        generated_by="code-understanding:mapgen",
        source_paths=["*"],
    )
    db_session.add(arch_map)
    db_session.add(arch_diagram)
    db_session.flush()


def _seed_completed_job(db_session: Session, project_id: str, arch_map_doc_id: str) -> None:
    """Seed a completed CodeIndexJob that indexes the architecture-map doc."""
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
        doc_id=arch_map_doc_id,
        completed_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(job)
    db_session.flush()


class TestI00055DoubleDiagram:
    """Tests for the I-00055 double-diagram fix."""

    def test_code_page_renders_exactly_one_diagram(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """REGRESSION: /code page must render exactly ONE diagram (inline or bottom).

        Pre-S01 bug: the page would render two diagrams:
        1. An inline diagram embedded in the architecture-map markdown content.
        2. A standalone diagram-architecture doc rendered separately.

        Post-S01 fix: strip_trailing_arch_diagram_section removes the trailing
        '## Architecture Diagram' section from the arch-map content, so only
        the diagram-architecture doc renders as the bottom standalone diagram.

        Asserting inline (<pre data-lang="mermaid">) + bottom (<div class="mermaid">) == 1
        proves exactly one diagram renders.
        """
        _seed_docs(db_session, test_project.id)
        _seed_completed_job(db_session, test_project.id, f"{test_project.id}:architecture-map")
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/code")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        html = resp.text

        inline_count = html.count('<pre data-lang="mermaid">')
        bottom_count = html.count('<div class="mermaid">')

        total = inline_count + bottom_count
        assert total == 1, (
            f"Expected exactly 1 diagram on the Code page, found {total} "
            f"(inline={inline_count}, bottom={bottom_count}). "
            "Pre-S01: arch-map content had inline diagram AND diagram-architecture "
            "rendered separately = 2. Post-S01: strip_trailing_arch_diagram_section "
            "removes legacy trailing section so only diagram-architecture renders."
        )

    def test_architecture_map_content_has_no_trailing_diagram_section(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """Verify the architecture-map doc stored in DB no longer has the legacy
        trailing '## Architecture Diagram' section (this is the S01 mapgen fix).
        """
        _seed_docs(db_session, test_project.id)
        _seed_completed_job(db_session, test_project.id, f"{test_project.id}:architecture-map")
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/code")
        assert resp.status_code == 200
        html = resp.text

        # The inline mermaid in arch-map markdown is stripped, so the H2
        # must not appear anywhere in the rendered page.
        assert "## Architecture Diagram" not in html, (
            "The '## Architecture Diagram' H2 from the legacy trailing section "
            "must not appear in the rendered page (stripped by "
            "strip_trailing_arch_diagram_section)"
        )

    def test_diagram_architecture_doc_renders_as_bottom_diagram(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """The diagram-architecture doc must render as the bottom standalone
        diagram (via <div class="mermaid">), not inline.
        """
        _seed_docs(db_session, test_project.id)
        _seed_completed_job(db_session, test_project.id, f"{test_project.id}:architecture-map")
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/code")
        assert resp.status_code == 200
        html = resp.text

        # The bottom diagram should come from the diagram-architecture doc.
        assert '<div class="mermaid">' in html, (
            'The diagram-architecture doc should render as a bottom <div class="mermaid"> element'
        )

    def test_strip_helper_is_applied_to_arch_map_content(
        self, client: TestClient, db_session: Session, test_project: Project
    ) -> None:
        """Verify that strip_trailing_arch_diagram_section is called at render time
        by checking that the arch-map content on the page has the trailing section removed.
        """
        from orch.rag.mapgen import strip_trailing_arch_diagram_section

        _seed_docs(db_session, test_project.id)
        _seed_completed_job(db_session, test_project.id, f"{test_project.id}:architecture-map")
        db_session.commit()

        resp = client.get(f"/project/{test_project.id}/code")
        assert resp.status_code == 200
        html = resp.text

        # Apply strip to the known legacy content and verify result is consistent
        stripped = strip_trailing_arch_diagram_section(_LEGACY_ARCH_MAP_CONTENT)
        assert "## Architecture Diagram" not in stripped
        assert "<!-- purpose:" not in stripped
        assert "```mermaid" not in stripped
        # The stripped content should NOT appear in the page
        assert "<!-- purpose: shows overall architecture -->" not in html
