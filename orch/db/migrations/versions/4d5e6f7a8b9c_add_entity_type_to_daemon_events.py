"""Add entity_type column to daemon_events.

Revision ID: 4d5e6f7a8b9c_add_entity_type_to_daemon_events
Revises: fb7e5859d479
Create Date: 2026-04-20 00:00:00.000000

Adds a nullable entity_type TEXT column to daemon_events to disambiguate
the polymorphic entity_id foreign key. This allows the dashboard Recent
Activity feed to route links correctly: batch IDs → /batch/, work-item
IDs → /item/, everything else → plain text.

Allowed values: 'work_item', 'batch', 'step', 'doc_job', NULL.
Legacy rows retain NULL and render as plain text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4d5e6f7a8b9c"
down_revision: str | None = "fb7e5859d479"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "daemon_events",
        sa.Column(
            "entity_type",
            sa.Text(),
            nullable=True,
            comment="Type of entity_id: work_item, batch, step, doc_job, or NULL",
        ),
    )


def downgrade() -> None:
    op.drop_column("daemon_events", "entity_type")
