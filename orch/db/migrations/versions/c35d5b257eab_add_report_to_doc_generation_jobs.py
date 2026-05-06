"""add report column to doc_generation_jobs

Revision ID: c35d5b257eab
Revises: 4cc043748e92
Create Date: 2026-05-05 22:51:00.000000

Adds a nullable JSONB 'report' column to doc_generation_jobs for structured
post-mortem execution reports (outcome, duration, skill_used, cli_tool,
command_issued, log stats, tool calls, diagnosis).

Schema-only change. No data backfill. Reversible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c35d5b257eab"
down_revision: str | None = "4cc043748e92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "doc_generation_jobs",
        sa.Column(
            "report",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Structured post-mortem of the doc-generation job: outcome, "
                "duration_seconds, skill_used, cli_tool, command_issued, "
                "log_size_bytes, log_line_count, tool_calls, "
                "doc_update_invocations, lint_warning_count, diagnosis."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("doc_generation_jobs", "report")
