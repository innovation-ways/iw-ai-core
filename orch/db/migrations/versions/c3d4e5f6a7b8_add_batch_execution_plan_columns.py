"""Add execution plan columns to batches table.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-08 12:00:00.000000

Adds execution_plan_md, execution_plan_drawio, execution_plan_png to the
batches table so batch plans and diagrams are stored in the database
rather than on disk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "batches",
        sa.Column(
            "execution_plan_md",
            sa.Text(),
            nullable=True,
            comment="Markdown execution plan with dependency analysis and warnings",
        ),
    )
    op.add_column(
        "batches",
        sa.Column(
            "execution_plan_drawio",
            sa.Text(),
            nullable=True,
            comment="Draw.io XML diagram of the execution plan",
        ),
    )
    op.add_column(
        "batches",
        sa.Column(
            "execution_plan_png",
            sa.LargeBinary(),
            nullable=True,
            comment="PNG image of the execution plan diagram",
        ),
    )


def downgrade() -> None:
    op.drop_column("batches", "execution_plan_png")
    op.drop_column("batches", "execution_plan_drawio")
    op.drop_column("batches", "execution_plan_md")
