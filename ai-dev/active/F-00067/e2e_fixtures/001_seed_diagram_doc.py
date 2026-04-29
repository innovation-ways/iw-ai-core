"""F-00067 S17 fixture: seed architecture-map with diagram-architecture doc.

Seeds the docs needed for browser verifications V1/V2 (diagram semantic colors
and "why" paragraph) in the E2E stack. The diagram-architecture doc is created
with a purpose comment and Mermaid DSL containing classDef semantic colors,
so the /code page renders #code-arch-diagram with arch_purpose.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from orch.db.models import (
    CodeIndexJob,
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    ProjectDoc,
)

_MERMAID_WITH_COLORS = """\
graph TD
  CLI[iw CLI]:::api
  Daemon[Orchestration Daemon]:::worker
  Dashboard[FastAPI Dashboard]:::ui
  DB[(PostgreSQL)]:::data
  LanceDB[(LanceDB)]:::data
  Ollama[Ollama LLM]:::external

  CLI --> Daemon
  Daemon --> DB
  Daemon --> Dashboard
  Dashboard --> DB
  Daemon --> LanceDB
  Daemon --> Ollama
  Dashboard --> Ollama

  classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F
  classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46
  classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F
  classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151
  classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764
  classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D
"""


def seed(db: Session) -> None:
    project_id = "iw-ai-core"

    diag_pk = f"{project_id}:diagram-architecture"
    existing = db.get(ProjectDoc, diag_pk)
    if existing is None:
        db.add(
            ProjectDoc(
                id=diag_pk,
                project_id=project_id,
                doc_id="diagram-architecture",
                title="IW AI Core — Architecture Diagram",
                slug=f"{project_id}-diagram-architecture",
                doc_type=DocType.diagram,
                tier=DocTier.fully_automated,
                editorial_category=EditorialCategory.technical,
                status=DocStatus.published,
                content=(
                    "<!-- purpose: This diagram shows the top-level "
                    "architecture of the IW AI Core orchestration platform "
                    "— its daemon, dashboard, CLI bridge, and data "
                    "stores. -->\n" + _MERMAID_WITH_COLORS
                ),
                version=1,
            )
        )
        # Flush the INSERT before any FK reference to this doc (session has autoflush=False)
        db.flush()

    now = datetime.now(UTC)
    from sqlalchemy import select

    existing_job = db.scalar(
        select(CodeIndexJob).where(
            CodeIndexJob.project_id == project_id,
            CodeIndexJob.status == "completed",
        )
    )
    if existing_job is None:
        db.add(
            CodeIndexJob(
                project_id=project_id,
                status="completed",
                provider="local",
                llm_model="stub:latest",
                embed_model="stub:latest",
                index_tier="fast",
                files_discovered=42,
                files_indexed=42,
                chunks_created=100,
                languages_detected=["python"],
                doc_id=diag_pk,
                triggered_at=now,
                completed_at=now,
            )
        )
    else:
        existing_job.doc_id = diag_pk
        existing_job.completed_at = now

    db.flush()
