"""Unit tests for BatchItem worktree compose stack columns (F-00062).

Tests the ORM model attributes only — no database, no subprocess.
"""

from __future__ import annotations

import sqlalchemy as sa


class TestBatchItemWorktreeColumns:
    """Tests for the three new worktree compose stack columns on BatchItem."""

    def test_worktree_db_port_column_exists_and_nullable(self) -> None:
        """worktree_db_port is present on BatchItem and nullable."""
        from orch.db.models import BatchItem

        col = BatchItem.__table__.columns["worktree_db_port"]
        assert col is not None
        assert col.type.python_type is int
        assert col.nullable is True

    def test_worktree_app_port_column_exists_and_nullable(self) -> None:
        """worktree_app_port is present on BatchItem and nullable."""
        from orch.db.models import BatchItem

        col = BatchItem.__table__.columns["worktree_app_port"]
        assert col is not None
        assert col.type.python_type is int
        assert col.nullable is True

    def test_worktree_compose_path_column_exists_and_nullable(self) -> None:
        """worktree_compose_path is present on BatchItem and nullable."""
        from orch.db.models import BatchItem

        col = BatchItem.__table__.columns["worktree_compose_path"]
        assert col is not None
        assert isinstance(col.type, sa.Text)
        assert col.nullable is True

    def test_worktree_db_port_defaults_to_none(self) -> None:
        """Freshly constructed BatchItem has worktree_db_port = None."""
        from orch.db.models import BatchItem

        item = BatchItem(
            project_id="iw-ai-core",
            batch_id="B-001",
            work_item_id="F-00001",
            execution_group=0,
        )
        assert item.worktree_db_port is None

    def test_worktree_app_port_defaults_to_none(self) -> None:
        """Freshly constructed BatchItem has worktree_app_port = None."""
        from orch.db.models import BatchItem

        item = BatchItem(
            project_id="iw-ai-core",
            batch_id="B-001",
            work_item_id="F-00001",
            execution_group=0,
        )
        assert item.worktree_app_port is None

    def test_worktree_compose_path_defaults_to_none(self) -> None:
        """Freshly constructed BatchItem has worktree_compose_path = None."""
        from orch.db.models import BatchItem

        item = BatchItem(
            project_id="iw-ai-core",
            batch_id="B-001",
            work_item_id="F-00001",
            execution_group=0,
        )
        assert item.worktree_compose_path is None

    def test_all_three_default_to_none_together(self) -> None:
        """All three worktree columns default to None simultaneously."""
        from orch.db.models import BatchItem

        item = BatchItem(
            project_id="iw-ai-core",
            batch_id="B-001",
            work_item_id="F-00001",
            execution_group=0,
        )
        assert item.worktree_db_port is None
        assert item.worktree_app_port is None
        assert item.worktree_compose_path is None


class TestBatchItemStatusSetupFailed:
    """Tests for the setup_failed enum value."""

    def test_setup_failed_enum_value_exists(self) -> None:
        """BatchItemStatus has setup_failed as a member."""
        from orch.db.models import BatchItemStatus

        assert hasattr(BatchItemStatus, "setup_failed")
        assert BatchItemStatus.setup_failed.value == "setup_failed"

    def test_setup_failed_is_enum_member(self) -> None:
        """setup_failed is a valid BatchItemStatus enum member."""
        from orch.db.models import BatchItemStatus

        members = list(BatchItemStatus)
        assert BatchItemStatus.setup_failed in members
