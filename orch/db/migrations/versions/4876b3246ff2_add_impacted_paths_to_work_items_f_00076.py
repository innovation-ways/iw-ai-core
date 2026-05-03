"""Add impacted_paths to work_items (F-00076)

Revision ID: 4876b3246ff2
Revises: a9861af32872
Create Date: 2026-05-03 00:56:11.857863

"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4876b3246ff2"
down_revision: str | None = "a9861af32872"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    # Ensure 'archived' is in the work_item_status enum before the backfill query.
    # PostgreSQL requires new enum values to be committed before they can be used
    # in subsequent statements. We end the current transaction (committing just the
    # enum change) and start a new one for the rest of the migration.
    # IF NOT EXISTS makes this safe to re-run.
    op.execute("ALTER TYPE work_item_status ADD VALUE IF NOT EXISTS 'archived'")
    op.execute(sa.text("COMMIT"))
    op.execute(sa.text("BEGIN"))

    op.add_column(
        "work_items",
        sa.Column(
            "impacted_paths",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )

    # Backfill impacted_paths for actionable items using extract_affected_files().
    # Backfill scope: items NOT in terminal states ('completed', 'archived').
    from orch.batch_planner import extract_affected_files

    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT project_id, id, design_doc_content "
            "FROM work_items "
            "WHERE status NOT IN ('completed', 'archived') "
            "AND design_doc_content IS NOT NULL"
        )
    )
    rows = result.fetchall()

    backfilled = 0
    for project_id, item_id, design_doc_content in rows:
        paths = extract_affected_files(design_doc_content)
        if not paths:
            continue
        bind.execute(
            sa.text(
                "UPDATE work_items "
                "SET impacted_paths = cast(:paths as jsonb) "
                "WHERE project_id = :pid AND id = :iid"
            ),
            {"paths": json.dumps(paths), "pid": project_id, "iid": item_id},
        )
        backfilled += 1

    log.info("Backfilled %d items with impacted_paths (F-00076)", backfilled)


def downgrade() -> None:
    op.drop_column("work_items", "impacted_paths")
    # Remove the 'archived' enum value added in upgrade.
    # PostgreSQL does not support DROP VALUE for enum types, so we leave it.
    # This is acceptable as the value is harmless if unused.
