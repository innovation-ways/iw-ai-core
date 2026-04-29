"""Diagram docs fixture for F-00065 browser verification.

Inserts ProjectDoc rows with doc_type='diagram' so V1 and V2 can verify
that the diagram display works in the code index and module detail views.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory, ProjectDoc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"

ARCHITECTURE_DIAGRAM_CONTENT = """graph TD
  A[Dashboard] --> B[RAG]
  A --> C[Daemon]
  B --> D[LanceDB]
"""

MODULE_DIAGRAM_CONTENT = """graph TD
  MG[MapGenerator] --> LLM[LLM Client]
  MG --> DB[(ProjectDoc)]
  ModGen[ModuleGenerator] --> LLM
"""


def seed(db: Session) -> None:
    arch_pk = f"{PROJECT_ID}:diagram-architecture"
    existing_arch = db.get(ProjectDoc, arch_pk)
    if existing_arch is None:
        db.add(
            ProjectDoc(
                id=arch_pk,
                project_id=PROJECT_ID,
                doc_id="diagram-architecture",
                title="Architecture Diagram",
                slug=f"{PROJECT_ID}-diagram-architecture",
                doc_type=DocType.diagram,
                tier=DocTier.fully_automated,
                editorial_category=EditorialCategory.technical,
                status=DocStatus.published,
                content=ARCHITECTURE_DIAGRAM_CONTENT,
                version=1,
            )
        )

    module_pk = f"{PROJECT_ID}:diagram-module-orch-rag"
    existing_module = db.get(ProjectDoc, module_pk)
    if existing_module is None:
        db.add(
            ProjectDoc(
                id=module_pk,
                project_id=PROJECT_ID,
                doc_id="diagram-module-orch-rag",
                title="Module Diagram — RAG",
                slug=f"{PROJECT_ID}-diagram-module-orch-rag",
                doc_type=DocType.diagram,
                tier=DocTier.fully_automated,
                editorial_category=EditorialCategory.technical,
                status=DocStatus.published,
                content=MODULE_DIAGRAM_CONTENT,
                version=1,
            )
        )
