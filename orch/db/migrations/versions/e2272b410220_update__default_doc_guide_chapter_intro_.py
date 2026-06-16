"""update _default doc guide: chapter intro + no hand-authored chrome

Revision ID: e2272b410220
Revises: 65084ea7e4b4
Create Date: 2026-06-16 09:11:34.048852

Data migration: append the chapter-structure + document-chrome authoring rules to
the ``_default`` doc-type guide so every future doc generation (any project)
opens each chapter with a short intro and does not hand-author the cover / index
/ running header / footer that the shared renderer now adds automatically.

Idempotent: if the rules are already present (they were applied live ahead of
this migration) the upgrade is a no-op. Downgrade strips the appended block.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2272b410220"
down_revision: str | tuple[str, ...] | None = "65084ea7e4b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Start of the appended block (used by downgrade to strip it) and a unique
# marker (used by upgrade for idempotency).
_RULES_HEADER = "## Chapter structure & document layout"
_MARKER = "## Do NOT hand-author document chrome"

_RULES = """

## Chapter structure & document layout

Write the document as a sequence of `##` chapters. Each `##` heading becomes its own chapter: the shared renderer automatically adds a branded chapter title page ("Chapter NN" + the heading) followed by an intro page.

- **Every `##` chapter MUST open with a 1-2 sentence intro paragraph** that plainly summarises what the chapter covers (for example: "This chapter describes every table in the data model and how they relate."). This opening paragraph is lifted onto the chapter's intro page, so it must read as a standalone summary, not as the first sentence of the body.
- Use `#` exactly once, for the document title. Use `##` for chapters and `###`/`####` for subsections.

## Do NOT hand-author document chrome

The shared renderer adds the following automatically for every document and every project. Do NOT write them into the markdown:

- the **cover page** (Innovation Ways palette, logo, and the document title);
- the **table of contents / index**;
- **per-chapter title and intro pages**;
- the **running header** (document name on the left, current chapter on the right);
- the **footer** (Innovation Ways logo + "Innovation Ways <year>" on the left, page number on the right).

Do not write a title page, a contents list, page numbers, or running headers/footers into the document body."""


def upgrade() -> None:
    bind = op.get_bind()
    row = bind.execute(
        sa.text("SELECT guide_md FROM doc_type_guides WHERE doc_type = '_default'")
    ).fetchone()
    if row is None:
        return  # _default guide not present (seed migration not applied) — nothing to do
    guide = row[0] or ""
    if _MARKER in guide:
        return  # already applied (e.g. set live ahead of this migration) — idempotent no-op
    bind.execute(
        sa.text("UPDATE doc_type_guides SET guide_md = :g WHERE doc_type = '_default'").bindparams(
            g=guide + _RULES
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    row = bind.execute(
        sa.text("SELECT guide_md FROM doc_type_guides WHERE doc_type = '_default'")
    ).fetchone()
    if row is None:
        return
    guide = row[0] or ""
    idx = guide.find(_RULES_HEADER)
    if idx == -1:
        return
    trimmed = guide[:idx].rstrip() + "\n"
    bind.execute(
        sa.text("UPDATE doc_type_guides SET guide_md = :g WHERE doc_type = '_default'").bindparams(
            g=trimmed
        )
    )
