"""make id_sequences global (remove project_id)

Revision ID: f7a8b9c0d1e2
Revises: 293ee95242af
Create Date: 2026-04-09 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "293ee95242af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Consolidate per-project sequences into a temp table with MAX(next_number)
    op.execute(
        """
        CREATE TEMP TABLE _id_seq_consolidated AS
        SELECT prefix, MAX(next_number) AS next_number
        FROM id_sequences
        GROUP BY prefix
        """
    )

    # 2. Drop the existing table (has composite PK with project_id)
    op.drop_table("id_sequences")

    # 3. Recreate with prefix as sole PK
    op.create_table(
        "id_sequences",
        sa.Column(
            "prefix",
            sa.Text(),
            primary_key=True,
            comment="ID prefix: 'F' (Feature), 'I' (Issue), 'CR' (ChangeRequest), 'BATCH'",
        ),
        sa.Column(
            "next_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Next number to allocate (incremented atomically via FOR UPDATE)",
        ),
        comment="Global atomic sequential ID allocation per prefix",
    )

    # 4. Restore consolidated data
    op.execute(
        """
        INSERT INTO id_sequences (prefix, next_number)
        SELECT prefix, next_number FROM _id_seq_consolidated
        """
    )

    # 5. Clean up
    op.execute("DROP TABLE _id_seq_consolidated")


def downgrade() -> None:
    # Downgrade re-adds project_id but cannot restore per-project counters.
    # Each project will get the global counter value (some numbers skipped).
    op.execute(
        """
        CREATE TEMP TABLE _id_seq_backup AS
        SELECT prefix, next_number FROM id_sequences
        """
    )

    op.drop_table("id_sequences")

    op.create_table(
        "id_sequences",
        sa.Column("project_id", sa.Text(), primary_key=True),
        sa.Column(
            "prefix",
            sa.Text(),
            primary_key=True,
            comment="ID prefix: 'F' (Feature), 'I' (Issue), 'CR' (ChangeRequest), 'BATCH'",
        ),
        sa.Column(
            "next_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Next number to allocate (incremented atomically via FOR UPDATE)",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        comment="Atomic sequential ID allocation per project and type",
    )

    # Re-insert for all existing projects with the global counter
    op.execute(
        """
        INSERT INTO id_sequences (project_id, prefix, next_number)
        SELECT p.id, b.prefix, b.next_number
        FROM projects p
        CROSS JOIN _id_seq_backup b
        """
    )

    op.execute("DROP TABLE _id_seq_backup")
