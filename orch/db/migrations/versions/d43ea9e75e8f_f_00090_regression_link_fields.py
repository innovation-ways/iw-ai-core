"""F-00090 regression link fields

Revision ID: d43ea9e75e8f
Revises: 42be5962ebf7
Create Date: 2026-05-27 11:48:24.712462

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "d43ea9e75e8f"
down_revision: str | tuple[str, ...] | None = "42be5962ebf7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create the PG ENUM type (F-00090)
    op.execute(
        "CREATE TYPE regression_classification_enum AS ENUM "
        "('regression', 'pre_existing', 'unknown')"
    )

    # Add regression-link columns to work_items (F-00090)
    op.add_column(
        "work_items",
        sa.Column(
            "introduced_by_work_item_id",
            sa.Text(),
            nullable=True,
            comment=(
                "ID of the work item whose merge introduced the regression this Incident "
                "reports. NULL when not yet classified or when the classification is "
                "pre-existing/unknown. Indexed for badge-count rollups on Batches/History "
                "views (F-00090)."
            ),
        ),
    )
    op.add_column(
        "work_items",
        sa.Column(
            "introduced_by_commit_sha",
            sa.Text(),
            nullable=True,
            comment=(
                "Optional commit SHA the operator pasted alongside the introducing work item; "
                "used when the operator knows the exact commit (F-00090)."
            ),
        ),
    )
    op.add_column(
        "work_items",
        sa.Column(
            "regression_classification",
            sa.Enum("regression", "pre_existing", "unknown", name="regression_classification_enum"),
            nullable=True,
            comment=(
                "How this Incident relates to a prior merge: regression / pre_existing / unknown. "
                "NULL means not yet classified (F-00090)."
            ),
        ),
    )
    op.add_column(
        "work_items",
        sa.Column(
            "classified_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC timestamp when the regression classification was last persisted (F-00090).",
        ),
    )
    op.add_column(
        "work_items",
        sa.Column(
            "classified_by",
            sa.Text(),
            nullable=True,
            comment=(
                "Identity that performed the classification — 'operator:<user>' for UI submissions, "
                "'heuristic:auto' when the operator accepted the heuristic's top suggestion (F-00090)."
            ),
        ),
    )

    # Index on introduced_by_work_item_id for badge-count rollups (F-00090)
    op.create_index(
        "ix_work_items_introduced_by_work_item_id",
        "work_items",
        ["introduced_by_work_item_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop index (F-00090)
    op.drop_index(
        "ix_work_items_introduced_by_work_item_id",
        table_name="work_items",
    )

    # Drop regression-link columns (F-00090)
    op.drop_column("work_items", "classified_by")
    op.drop_column("work_items", "classified_at")
    op.drop_column("work_items", "regression_classification")
    op.drop_column("work_items", "introduced_by_commit_sha")
    op.drop_column("work_items", "introduced_by_work_item_id")

    # Drop PG ENUM type (F-00090)
    op.execute("DROP TYPE regression_classification_enum")
