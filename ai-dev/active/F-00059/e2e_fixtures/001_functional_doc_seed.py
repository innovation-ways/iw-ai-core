"""E2E fixture: seed F-00059 with functional_doc_content for S12 browser verification.

V1: item with populated functional_doc_content (paragraphs + H2 sections).
V2: item with NULL functional_doc_content AND NULL functional_doc_path (empty state).

Exports seed(db: Session) -> None.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from orch.db.models import WorkItem, WorkItemType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"


def seed(db: Session) -> None:
    now = datetime.now(UTC)

    functional_content = """## Why

The Functional Design Document captures the *intent* behind a work item in plain
English — not implementation details, not file paths, not code. It is the high-signal
retrieval context that human stakeholders use to understand why a change was made.

## What Changed (for the User)

A new "Functional Design" tab appears on the work item detail page, immediately after
the existing "Design Document" tab. Users can read the short document to understand
the user-facing behaviour without wading through implementation prompts.

## How It Behaves

The tab renders the markdown content with styled headings (Why, What Changed, How It
Behaves). If no document has been loaded yet, a friendly empty-state message is
shown instead, with a reference to the backfill script for operators.
"""

    # --- V1: Populated functional doc ---
    # F-00059 was never seeded by e2e_seed.py — INSERT it now.
    f059 = db.get(WorkItem, (PROJECT_ID, "F-00059"))
    if f059 is None:
        f059 = WorkItem(
            project_id=PROJECT_ID,
            id="F-00059",
            type=WorkItemType.Feature,
            title="Functional design documents for work items",
            status="approved",
            phase="design",
            functional_doc_content=functional_content,
        )
        db.add(f059)
    else:
        f059.functional_doc_content = functional_content

    db.flush()

    # --- V2: NULL functional doc ---
    # Use I-00001 (already seeded by e2e_seed.py) but ensure it has no functional doc.
    i001 = db.get(WorkItem, (PROJECT_ID, "I-00001"))
    if i001 is not None:
        i001.functional_doc_content = None
        i001.functional_doc_path = None
        db.flush()