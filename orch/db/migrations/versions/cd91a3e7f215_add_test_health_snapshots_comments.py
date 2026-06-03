"""add_test_health_snapshots_comments

Revision ID: cd91a3e7f215
Revises: 3448ea03937d
Create Date: 2026-06-03 00:00:00.000000

Adds PostgreSQL column comments and a table comment to the
``test_health_snapshots`` table.  The original
``ea7f8a0d065f_add_test_health_snapshots_table`` migration created the table
without comments; the ORM model (``orch/db/models.py``) defines them.  Fixes
the ``alembic check`` drift detected in CI.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd91a3e7f215"
down_revision: str | None = "3448ea03937d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "test_health_snapshots",
        "id",
        existing_type=sa.BigInteger(),
        comment="Auto-incrementing primary key",
        existing_comment=None,
        existing_nullable=False,
    )
    op.alter_column(
        "test_health_snapshots",
        "project_id",
        existing_type=sa.Text(),
        comment="FK to projects.id; cascades on project deletion",
        existing_comment=None,
        existing_nullable=False,
    )
    op.alter_column(
        "test_health_snapshots",
        "ts",
        existing_type=sa.DateTime(timezone=True),
        comment="UTC timestamp of this snapshot (truncated to minute for idempotency)",
        existing_comment=None,
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "test_health_snapshots",
        "metric",
        existing_type=sa.Text(),
        comment=(
            "Metric name: 'mutation_score', 'coverage_pct', "
            "'flaky_test_count', or 'assertion_baseline_size'"
        ),
        existing_comment=None,
        existing_nullable=False,
    )
    op.alter_column(
        "test_health_snapshots",
        "value",
        existing_type=sa.Float(),
        comment="Numeric value of the metric at snapshot time",
        existing_comment=None,
        existing_nullable=False,
    )
    op.alter_column(
        "test_health_snapshots",
        "meta",
        existing_type=JSONB(),
        comment=(
            "Run metadata: commit_sha, run_id, source_path, raw_counts, etc. "
            "Empty object when no additional context is available."
        ),
        existing_comment=None,
        existing_nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
    )
    op.create_table_comment(
        "test_health_snapshots",
        "Time-series test-health metric snapshots (CR-00086)",
        existing_comment=None,
        schema=None,
    )


def downgrade() -> None:
    op.drop_table_comment(
        "test_health_snapshots",
        existing_comment="Time-series test-health metric snapshots (CR-00086)",
        schema=None,
    )
    op.alter_column(
        "test_health_snapshots",
        "meta",
        existing_type=JSONB(),
        comment=None,
        existing_comment=(
            "Run metadata: commit_sha, run_id, source_path, raw_counts, etc. "
            "Empty object when no additional context is available."
        ),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
    )
    op.alter_column(
        "test_health_snapshots",
        "value",
        existing_type=sa.Float(),
        comment=None,
        existing_comment="Numeric value of the metric at snapshot time",
        existing_nullable=False,
    )
    op.alter_column(
        "test_health_snapshots",
        "metric",
        existing_type=sa.Text(),
        comment=None,
        existing_comment=(
            "Metric name: 'mutation_score', 'coverage_pct', "
            "'flaky_test_count', or 'assertion_baseline_size'"
        ),
        existing_nullable=False,
    )
    op.alter_column(
        "test_health_snapshots",
        "ts",
        existing_type=sa.DateTime(timezone=True),
        comment=None,
        existing_comment="UTC timestamp of this snapshot (truncated to minute for idempotency)",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "test_health_snapshots",
        "project_id",
        existing_type=sa.Text(),
        comment=None,
        existing_comment="FK to projects.id; cascades on project deletion",
        existing_nullable=False,
    )
    op.alter_column(
        "test_health_snapshots",
        "id",
        existing_type=sa.BigInteger(),
        comment=None,
        existing_comment="Auto-incrementing primary key",
        existing_nullable=False,
    )
