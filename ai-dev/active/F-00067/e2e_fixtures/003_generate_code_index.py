"""F-00067 S17 fixture: generate the code-index document.

Seeds the code-index ProjectDoc for V5 (index page exists). This fixture
calls generate_index_page() directly — the same function the daemon calls
after a CodeIndexJob completes — so the index doc is present in the E2E DB.

Must run AFTER 001_seed_diagram_doc.py (which seeds the diagram-architecture
doc that index_gen.py references) and AFTER 002_seed_callout_docs.py (which
seeds module docs).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def seed(db: Session) -> None:
    from orch.rag.index_gen import generate_index_page

    generate_index_page(project_id="iw-ai-core", session=db)
    db.commit()
