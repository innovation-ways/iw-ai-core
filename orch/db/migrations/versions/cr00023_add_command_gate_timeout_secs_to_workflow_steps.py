"""CR-00023: add command/gate/timeout_secs to workflow_steps

Revision ID: cr00023workflow
Revises: c062b6bf5eb3
Create Date: 2026-04-27 19:30:00.000000

Promotes per-step runtime fields (command/gate/timeout) from the on-disk
workflow-manifest.json into the workflow_steps table so that
`iw item-status --json` becomes a true superset of the manifest. All three
columns are nullable; legacy rows registered before this CR keep NULL and
the daemon falls back to manifest read.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cr00023workflow"
down_revision: str | Sequence[str] | None = "c062b6bf5eb3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow_steps",
        sa.Column(
            "command",
            sa.Text(),
            nullable=True,
            comment=(
                "Shell command for qv-gate steps (e.g., 'make lint'). NULL for "
                "non-gate steps and for items registered before CR-00023."
            ),
        ),
    )
    op.add_column(
        "workflow_steps",
        sa.Column(
            "gate",
            sa.Text(),
            nullable=True,
            comment=(
                "Gate name for qv-gate steps (e.g., 'lint', 'format', 'typecheck'). "
                "NULL for non-gate steps and for items registered before CR-00023."
            ),
        ),
    )
    op.add_column(
        "workflow_steps",
        sa.Column(
            "timeout_secs",
            sa.Integer(),
            nullable=True,
            comment=(
                "Per-step timeout override in seconds. NULL = use project default. "
                "Sourced from the manifest's 'timeout' field at registration."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("workflow_steps", "timeout_secs")
    op.drop_column("workflow_steps", "gate")
    op.drop_column("workflow_steps", "command")
