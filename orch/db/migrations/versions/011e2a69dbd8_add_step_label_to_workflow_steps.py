"""Add step_label to workflow_steps

Revision ID: 011e2a69dbd8
Revises: f7a8b9c0d1e2
Create Date: 2026-04-09 22:31:39.936021

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011e2a69dbd8"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow_steps",
        sa.Column(
            "step_label",
            sa.Text(),
            nullable=True,
            comment="Short human-readable label for the step (e.g., 'ruff lint', 'unit tests')",
        ),
    )

    # Backfill: derive short labels from existing description text.
    # QV gates: "QV gate: ruff check (lint)" → "ruff check (lint)"
    # Others: take first 50 chars of description as-is.
    op.execute(
        """
        UPDATE workflow_steps
        SET step_label = CASE
            WHEN description LIKE 'QV gate:%'
                THEN TRIM(SUBSTRING(description FROM 10))
            WHEN description IS NOT NULL
                THEN LEFT(description, 50)
            ELSE NULL
        END
        WHERE step_label IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("workflow_steps", "step_label")
