"""I-00080 E2E fixture: diagram docs for browser verification.

Seeds two ProjectDoc rows for the iw-ai-core project:
  - i00080-fenced-diagram   : a doc_type=diagram doc with a fenced ```mermaid block
  - i00080-raw-dsl-diagram  : a doc_type=diagram doc with bare DSL (no fence)

Both are used by V1-V4 browser verifications.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import DocStatus, DocTier, DocType, EditorialCategory, ProjectDoc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def seed(db: Session) -> None:
    project_id = "iw-ai-core"
    doc_id_1 = "i00080-fenced-diagram"
    doc_id_2 = "i00080-raw-dsl-diagram"

    # --- Doc 1: fenced mermaid block ---
    doc1_content = """# Fenced Diagram Doc

Here is a diagram:

```mermaid
graph TD;
    CLI["iw CLI"] --> DB[("PostgreSQL")];
    DAEMON["daemon"] --> DB;
    CLI --> DAEMON;
```

The end.
"""
    pk1 = f"{project_id}:{doc_id_1}"
    doc1 = db.get(ProjectDoc, pk1)
    if doc1 is None:
        doc1 = ProjectDoc(
            id=pk1,
            project_id=project_id,
            doc_id=doc_id_1,
            title="Fenced Diagram Doc",
            slug="i00080-fenced-diagram",
            doc_type=DocType.diagram,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.published,
            content=doc1_content,
        )
        db.add(doc1)
    else:
        doc1.doc_type = DocType.diagram
        doc1.status = DocStatus.published
        doc1.content = doc1_content

    # --- Doc 2: raw DSL (no fence) ---
    doc2_content = """<!-- purpose: i00080 raw-dsl check -->
---
config:
  layout: elk
---
graph TD
  A[Foo] --> B[Bar]
"""
    pk2 = f"{project_id}:{doc_id_2}"
    doc2 = db.get(ProjectDoc, pk2)
    if doc2 is None:
        doc2 = ProjectDoc(
            id=pk2,
            project_id=project_id,
            doc_id=doc_id_2,
            title="Raw DSL Diagram Doc",
            slug="i00080-raw-dsl-diagram",
            doc_type=DocType.diagram,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.published,
            content=doc2_content,
        )
        db.add(doc2)
    else:
        doc2.doc_type = DocType.diagram
        doc2.status = DocStatus.published
        doc2.content = doc2_content

    db.flush()