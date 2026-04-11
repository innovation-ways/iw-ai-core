"""add run_type to test_runs

Revision ID: 8e995f56934c
Revises: 7e8f9a0b1c2d
Create Date: 2026-04-11 17:47:30.531666

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8e995f56934c"
down_revision: str | None = "7e8f9a0b1c2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "test_runs",
        sa.Column(
            "run_type",
            sa.Text(),
            server_default=sa.text("'test'"),
            nullable=False,
            comment="Discriminator: test or quality",
        ),
    )
    op.create_index(
        "idx_test_runs_run_type",
        "test_runs",
        ["project_id", "run_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_test_runs_run_type", table_name="test_runs")
    op.drop_column("test_runs", "run_type")
