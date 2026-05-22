"""add manifest_digest to work_items (I-00102)

Revision ID: aeb0e4106b55
Revises: 891343247f66
Create Date: 2026-05-21 21:14:26.613454

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aeb0e4106b55"
down_revision: str | Sequence[str] | None = "891343247f66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "work_items",
        sa.Column(
            "manifest_digest",
            sa.Text(),
            nullable=True,
            comment=(
                "SHA-256 hex digest of the canonicalized steps array from "
                "workflow-manifest.json at register/approve time. NULL for "
                "pre-I-00102 items. Used by iw approve to detect on-disk "
                "manifest drift and auto-refresh workflow_steps when the "
                "item is still in draft. See I-00102."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("work_items", "manifest_digest")
