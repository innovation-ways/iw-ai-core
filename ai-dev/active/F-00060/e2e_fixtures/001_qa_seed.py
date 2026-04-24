"""E2E seed fixture for F-00060 browser verification.

Seeds work items with functional_doc_content and git history so the
hybrid retriever (semantic + FTS + git_log) has meaningful candidates.

IDs use the production-shape ``(F|CR|I)-\\d{5}`` form so
``orch/rag/citation_allowlist.py:WORK_ITEM_ID_PATTERN`` matches them
exactly (no suffix). High numbers (F-99001..) are used to flag them as
synthetic and avoid collision with any real work-item sequence.

Items created:
  - F-99001  : original feature that introduced a button
  - CR-99001 : recolored the button blue
  - CR-99002 : changed button from circle to rounded-rect
  - F-99002  : NULL functional_doc_content to exercise AC4 fallback

Git history: each item has Merge F-/CR- lines so git_log_resolver finds them.

Run via: uv run python scripts/e2e_seed.py (automatically discovered)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from orch.db.models import (
    Project,
    WorkItem,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"


def seed(db: Session) -> None:
    now = datetime.now(UTC)

    project = db.get(Project, PROJECT_ID)
    if project is None:
        return

    items = [
        {
            "id": "F-99001",
            "type": WorkItemType.Feature,
            "title": "New project button — original implementation",
            "status": "completed",
            "phase": "done",
            "functional_doc_content": (
                "The New project button enables users to create a new project workspace "
                "from the dashboard. It appears in the top navigation bar and opens a "
                "modal dialog. The button is styled with a green background (#10b981), "
                "white text, rounded corners (6px), and is sized at 36px height for "
                "easy tapping on touch devices. Placement: top-right of the dashboard "
                "header, adjacent to the search box. Purpose: reduces friction for new "
                "project creation from 3 clicks to 1."
            ),
            "summary": "Original New project button implementation",
        },
        {
            "id": "CR-99001",
            "type": WorkItemType.ChangeRequest,
            "title": "Recolor New project button to blue",
            "status": "completed",
            "phase": "done",
            "functional_doc_content": (
                "Change the New project button background colour from green (#10b981) "
                "to blue (#3b82f6) to align with the updated brand palette introduced "
                "in the 2026 brand refresh. All other styling (size, shape, placement, "
                "border-radius) remains unchanged. This recolor applies to the button "
                "in all dashboard views where it appears."
            ),
            "summary": "Recolor New project button to brand-blue",
        },
        {
            "id": "CR-99002",
            "type": WorkItemType.ChangeRequest,
            "title": "Change New project button shape from circle to rounded-rect",
            "status": "completed",
            "phase": "done",
            "functional_doc_content": (
                "Update the New project button shape from a fully rounded pill (border-radius: "
                "9999px) to a standard rounded rectangle (border-radius: 6px) to better "
                "match the other action buttons in the dashboard. The colour (blue #3b82f6 "
                "from CR-99001) and all other properties remain unchanged. This "
                "visual refinement improves visual consistency with the surrounding UI."
            ),
            "summary": "Change button from pill shape to rounded rectangle",
        },
        {
            "id": "F-99002",
            "type": WorkItemType.Feature,
            "title": "Feature with NULL functional doc (AC4 fallback test)",
            "status": "completed",
            "phase": "done",
            "functional_doc_content": None,
            "summary": "This item has NULL functional_doc_content to test fallback to summary",
        },
    ]

    for item_data in items:
        existing = db.get(WorkItem, (PROJECT_ID, item_data["id"]))
        if existing is not None:
            existing.functional_doc_content = item_data["functional_doc_content"]
            existing.summary = item_data["summary"]
            continue
        db.add(
            WorkItem(
                project_id=PROJECT_ID,
                id=item_data["id"],
                type=item_data["type"],
                title=item_data["title"],
                status=item_data["status"],
                phase=item_data["phase"],
                functional_doc_content=item_data["functional_doc_content"],
                summary=item_data["summary"],
                created_at=now,
                updated_at=now,
            )
        )
