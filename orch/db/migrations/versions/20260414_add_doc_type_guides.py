"""Add doc_type_guides table.

Revision ID: add_doc_type_guides
Revises: add_section_guides_snapshot_to_jobs
Create Date: 2026-04-14 00:00:00.000000

Per-doc-type editorial guidelines, editable from the UI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "add_doc_type_guides"
down_revision: str | None = "add_section_guides_snapshot_to_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_DEFAULT_GUIDE = """# Global Editorial Guidelines

## Voice & Tone

Innovation Ways documents are written with authority and clarity. We do not hedge.
We do not use filler phrases. Every sentence earns its place.

**Always:**
- Active voice, present tense
- Concrete specifics over vague generalities
- One idea per paragraph
- Short sentences for key points, longer for explanations

**Never:**
- "Leverage" — use "use"
- "Utilize" — use "use"
- "Solution" as a noun standing alone
- "Best-in-class", "world-class", "cutting-edge" without evidence
- Passive voice unless unavoidable
- Nested bullet lists more than one level deep
- Starting a sentence with "This"

## Structure Rules

- Every document starts with a one-paragraph executive summary
- Heading hierarchy: H1 (title only), H2 (sections), H3 (subsections)
- Tables for comparisons — not bullet lists with parallel items
- Diagrams before prose: show the picture, then explain it
- Code blocks always carry a language identifier

## Numbers & Claims

- Round numbers are suspicious: prefer "under 2 seconds" to "2 seconds"
- Every metric must be traceable to a source file or measurement
- Do not invent future capability — only document what exists

## Formatting

- Bold for the first introduction of a key term only
- Italics for titles and emphasis (use sparingly)
- Avoid ALL CAPS except in code
- Em dash (—) for interruptions; en dash (–) for ranges
"""

_MARKETING_GUIDE = """# Marketing Document Editorial Guidelines

Applies to: MKT-* documents (product_overview, one-pagers, promotional)

## Audience

Non-technical stakeholders, executives, engineering managers, potential partners.
Assume familiarity with software development concepts but not implementation details.

## Tone

Confident, not boastful. Specific, not fluffy. The reader is busy — respect their time.
Lead with the problem. Earn the pitch.

## Structure for Product Overview (MKT)

1. **Headline** — One sentence: what the product does and for whom
2. **The Problem** — Two to four sentences. Make the reader feel the pain before offering the cure
3. **What It Is** — One paragraph. Clear, jargon-light description
4. **How It Works** — High-level diagram + two to four sentences. No implementation detail
5. **Key Capabilities** — Table or short list. Name + one-line description each. Max eight items
6. **Why It Matters** — Three to five bullet points. Outcomes, not features
7. **Current Status** — One paragraph on where the platform stands today
8. **Contact / Next Steps** — Optional; include if doc is externally facing

## Do

- Lead with pain points engineers actually feel
- Use the platform's real capability names (daemon, CLI, dashboard) — they signal substance
- One diagram maximum: a clean component overview
- Keep total length under three pages (printed A4)

## Do Not

- Do not describe internal implementation (SQL queries, Python classes, bash scripts)
- Do not mention version numbers, port numbers, or file paths
- Do not use "AI" as a magic word — describe what the AI agents actually do
- Do not write a feature list disguised as prose — use a table
- Do not end with a generic call to action
"""


def upgrade() -> None:
    op.execute(
        """CREATE TABLE doc_type_guides (
            doc_type   TEXT PRIMARY KEY,
            guide_md   TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )"""
    )
    op.execute(
        "COMMENT ON TABLE doc_type_guides IS 'Per-doc-type editorial guidelines, editable from the UI.'"
    )
    op.execute(
        "COMMENT ON COLUMN doc_type_guides.doc_type IS 'DocType enum value (e.g. marketing, module, api).'"
    )
    op.execute(
        "COMMENT ON COLUMN doc_type_guides.guide_md IS 'Markdown editorial guidelines for this doc type.'"
    )
    op.execute("COMMENT ON COLUMN doc_type_guides.updated_at IS 'Timestamp of last guide edit.'")

    op.execute(
        text(
            "INSERT INTO doc_type_guides (doc_type, guide_md) VALUES (:doc_type, :guide_md)"
        ).bindparams(doc_type="_default", guide_md=_DEFAULT_GUIDE)
    )
    op.execute(
        text(
            "INSERT INTO doc_type_guides (doc_type, guide_md) VALUES (:doc_type, :guide_md)"
        ).bindparams(doc_type="marketing", guide_md=_MARKETING_GUIDE)
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS doc_type_guides")
