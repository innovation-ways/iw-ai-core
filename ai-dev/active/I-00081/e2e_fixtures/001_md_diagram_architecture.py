"""E2E fixture: add a 'diagram-architecture' ProjectDoc in the Markdown-doc form.

This is the content shape produced by the iw-doc-generator skill — a full
Markdown document with an H1, HTML comments, blockquotes, and two fenced
mermaid blocks (each with a YAML front-matter block).

This form was the root cause of I-00081: the old code passed the raw Markdown
to the Mermaid renderer directly, which threw "Syntax error in text —
mermaid version 11.14.0" because the markdown prose is not valid DSL.

The fix (in dashboard/routers/code_ui.py:_render_arch_diagram) detects the
fenced-block form and processes each block through _preprocess_mermaid +
render_markdown so every fence becomes a <pre data-lang="mermaid"> that
client-side Mermaid can upgrade to an SVG.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import (
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    ProjectDoc,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"
DOC_ID = "diagram-architecture"
PK = f"{PROJECT_ID}:{DOC_ID}"

CONTENT = """\
# IW AI Core — Architecture Diagram

<!-- generated: 2026-05-11T22:00:00Z -->

> **Why this diagram?** The high-level flow diagram shows how the daemon, \
dashboard, and CLI interact with PostgreSQL and agent worktrees.

```mermaid
---
config:
  layout: elk
---
flowchart TB
    CLI["iw CLI"] --> DB[("PostgreSQL")]
    DAEMON["Daemon"] --> DB
    DASHBOARD["Dashboard"] --> DB
    CLI --> DAEMON
    DAEMON --> WORKTREE["Agent Worktrees"]
```

> **Why this diagram?** The entity-relationship diagram shows the core data \
model: projects own work items, batches, and code-index jobs.

```mermaid
---
config:
  layout: elk
---
erDiagram
    Project ||--o{ WorkItem : "owns"
    Project ||--o{ Batch : "groups"
    Project ||--o{ CodeIndexJob : "indexes"
    Batch ||--o{ BatchItem : "contains"
    BatchItem }o--|| WorkItem : "references"
```
"""


def seed(db: Session) -> None:
    """Idempotently insert the diagram-architecture ProjectDoc."""
    existing = db.get(ProjectDoc, PK)
    if existing is not None:
        existing.content = CONTENT
        return
    db.add(
        ProjectDoc(
            id=PK,
            project_id=PROJECT_ID,
            doc_id=DOC_ID,
            title="IW AI Core — Architecture Diagram",
            slug=f"{PROJECT_ID}-diagram-architecture",
            doc_type=DocType.diagram,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            status=DocStatus.published,
            generated_by="skill:iw-doc-generator",
            source_paths=["docs/"],
            content=CONTENT,
            version=1,
        )
    )
