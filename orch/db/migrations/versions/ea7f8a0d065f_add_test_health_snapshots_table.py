"""add_test_health_snapshots_table

Revision ID: ea7f8a0d065f
Revises: a3f1c9e2b7d4
Create Date: 2026-05-28 08:25:04.047279

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "ea7f8a0d065f"
down_revision: str | tuple[str, ...] | None = "a3f1c9e2b7d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_health_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column(
            "ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("meta", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_test_health_snapshots_project_metric_ts",
        "test_health_snapshots",
        ["project_id", "metric", sa.text("ts DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_test_health_snapshots_project_metric_ts",
        table_name="test_health_snapshots",
    )
    op.drop_table("test_health_snapshots")
