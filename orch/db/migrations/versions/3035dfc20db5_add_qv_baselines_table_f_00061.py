"""add qv_baselines table (F-00061)

Revision ID: 3035dfc20db5
Revises: 13014259ab68
Create Date: 2026-04-23 20:44:23.775740

Adds qv_baselines — per-(step, gate, base_sha) failure fingerprint baselines
for baseline QV gates to prevent fix-cycle scope expansion.

iw_core_baseline
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from collections.abc import Sequence


revision: str = "3035dfc20db5"
down_revision: str | None = "13014259ab68"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "qv_baselines",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column(
            "step_id",
            sa.BigInteger(),
            nullable=False,
            comment="FK to workflow_steps.id",
        ),
        sa.Column(
            "gate_name",
            sa.Text(),
            nullable=False,
            comment="Gate identifier matching WorkflowStep.gate (e.g. 'lint', 'unit-tests')",
        ),
        sa.Column(
            "base_sha",
            sa.Text(),
            nullable=False,
            comment="Full git SHA the baseline was computed against (40-char)",
        ),
        sa.Column(
            "fingerprint",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{\"failures\": []}'"),
            comment="Parser-produced canonical failure set",
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "step_id",
            "gate_name",
            "base_sha",
            name="uq_qv_baselines_step_gate_sha",
        ),
        comment="Baseline QV gate fingerprints to prevent fix-cycle scope expansion (F-00061)",
    )
    op.create_index("idx_qv_baselines_step_id", "qv_baselines", ["step_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_qv_baselines_step_id", table_name="qv_baselines")
    op.drop_table("qv_baselines")
