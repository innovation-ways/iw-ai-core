"""E2E fixture for I-00055 browser verification.

Seeds the architecture-map (with legacy trailing diagram section) and
diagram-architecture docs so the /code page can be verified for the
double-diagram fix.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from orch.db.models import CodeIndexJob, DocType, EditorialCategory, ProjectDoc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Legacy content: architecture-map with embedded trailing diagram block.
# This is the shape stored before S01 mapgen fix.
_LEGACY_ARCH_MAP_CONTENT = (
    "# Architecture Map\n\n"
    "## Purpose\nIW AI Core is an orchestration platform.\n\n"
    "## Components\n- **CLI**: command interface via `iw` bridge\n- **Daemon**: background polling and job orchestration\n- **Dashboard**: FastAPI web UI served at port 9900\n\n"
    "## Data Flow\nThe daemon reads approved batches from PostgreSQL and launches\nagents in isolated git worktrees.\n\n"
    "## Architecture Diagram\n\n"
    "<!-- purpose: shows overall architecture -->\n\n"
    "```mermaid\n"
    "---\n"
    "config:\n"
    "  layout: elk\n"
    "---\n"
    "graph TD\n"
    "  CLI --> Daemon\n"
    "  Daemon --> DB[(PostgreSQL)]\n"
    "  Daemon --> Dashboard\n"
    "```\n"
)

# Clean diagram-architecture doc (no purpose comment, no YAML frontmatter in content).
_CLEAN_ARCH_DIAGRAM_DSL = (
    "---\nconfig:\n  layout: elk\n---\ngraph TD\n  CLI --> Daemon\n  Daemon --> DB[(PostgreSQL)]\n  Daemon --> Dashboard\n"
)


def seed(db: Session) -> None:
    """Idempotent seed for I-00055 browser verification.

    Seeds:
    - architecture-map ProjectDoc (legacy shape with trailing mermaid block)
    - diagram-architecture ProjectDoc (clean DSL)
    - completed CodeIndexJob pointing at the architecture-map doc
    """
    project_id = "iw-ai-core"

    # Seed architecture-map doc (legacy content with trailing diagram section)
    arch_map_id = f"{project_id}:architecture-map"
    existing_arch_map = db.get(ProjectDoc, arch_map_id)
    if not existing_arch_map:
        arch_map = ProjectDoc(
            id=arch_map_id,
            project_id=project_id,
            doc_id="architecture-map",
            title="IW AI Core — Architecture Map",
            slug="architecture-map",
            doc_type=DocType.architecture,
            tier="fully_automated",
            editorial_category=EditorialCategory.technical,
            status="published",
            content=_LEGACY_ARCH_MAP_CONTENT,
            generated_by="code-understanding:level1",
            source_paths=["*"],
        )
        db.add(arch_map)

    # Seed diagram-architecture doc (clean DSL)
    arch_diagram_id = f"{project_id}:diagram-architecture"
    existing_diagram = db.get(ProjectDoc, arch_diagram_id)
    if not existing_diagram:
        arch_diagram = ProjectDoc(
            id=arch_diagram_id,
            project_id=project_id,
            doc_id="diagram-architecture",
            title="IW AI Core — Architecture Diagram",
            slug="diagram-architecture",
            doc_type=DocType.diagram,
            tier="fully_automated",
            editorial_category=EditorialCategory.technical,
            status="published",
            content=_CLEAN_ARCH_DIAGRAM_DSL,
            generated_by="code-understanding:mapgen",
            source_paths=["*"],
        )
        db.add(arch_diagram)

    # Seed completed CodeIndexJob for this project pointing at arch-map doc
    existing_job = (
        db.query(CodeIndexJob)
        .filter(CodeIndexJob.project_id == project_id, CodeIndexJob.doc_id == arch_map_id)
        .first()
    )
    if not existing_job:
        job = CodeIndexJob(
            project_id=project_id,
            status="completed",
            provider="local",
            llm_model="gemma4:e4b",
            embed_model="qwen3-embedding:8b",
            index_tier="balanced",
            files_discovered=42,
            files_indexed=40,
            chunks_created=100,
            languages_detected=["python"],
            errors=[],
            doc_id=arch_map_id,
            completed_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(job)

    db.flush()
