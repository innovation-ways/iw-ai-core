"""I-00062 AC5: migration adds the four columns and is reversible.

Verifies the alembic migration:
  - upgrade: adds worktree_db_host/name/user/password (all nullable)
  - downgrade: drops all four columns

IMPORTANT: Never downgrade with `-1` in migration tests; use a specific
revision ID so the test stays stable as new migrations land above.

Uses the Alembic Python API (same pattern as test_migration_impacted_paths_backfill.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


# The migration under test
MIGRATION_REV = "4cc043748e92"
PREV_REVISION = "4876b3246ff2"  # head before I-00062 migration


@pytest.fixture
def migrated_engine(db_engine: Engine) -> Engine:
    """Per-test PostgreSQL clone, already migrated to head (includes I-00062).

    Backed by the conftest ``db_engine`` (R-00077 template-clone): every test
    gets its own isolated database, so the downgrade round-trips below never
    leak schema state into sibling tests regardless of ``pytest-randomly`` order.

    Args:
        db_engine: Function-scoped per-test clone from the integration conftest.

    Returns:
        The same per-test engine, named ``migrated_engine`` for readability.
    """
    return db_engine


@pytest.mark.integration
class TestI00062MigrationRoundTrip:
    """Covers upgrade/downgrade round-trip for the I-00062 worktree DB columns migration."""

    def test_upgrade_adds_four_columns(self, migrated_engine: Engine) -> None:
        """After alembic upgrade head, batch_items has the four new columns, all nullable."""
        inspector = inspect(migrated_engine)
        cols = {c["name"]: c for c in inspector.get_columns("batch_items")}

        assert "worktree_db_host" in cols, (
            f"worktree_db_host missing. Available: {list(cols.keys())}"
        )
        assert "worktree_db_name" in cols
        assert "worktree_db_user" in cols
        assert "worktree_db_password" in cols

        # All four nullable
        assert cols["worktree_db_host"]["nullable"] is True, (
            f"worktree_db_host not nullable: {cols['worktree_db_host']}"
        )
        assert cols["worktree_db_name"]["nullable"] is True
        assert cols["worktree_db_user"]["nullable"] is True
        assert cols["worktree_db_password"]["nullable"] is True

    def test_downgrade_drops_four_columns(self, db_engine: Engine, migrated_engine: Engine) -> None:
        """After alembic downgrade to PREV_REVISION (before I-00062), the four
        columns are gone.

        Uses PREV_REVISION (not -1) so the test is stable regardless of how
        many migrations land above I-00062.
        """
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", "orch/db/migrations")
        alembic_cfg.set_main_option(
            "sqlalchemy.url", migrated_engine.url.render_as_string(hide_password=False)
        )
        # Downgrade to the revision BEFORE I-00062
        command.downgrade(alembic_cfg, PREV_REVISION)

        inspector = inspect(db_engine)
        cols = {c["name"]: c for c in inspector.get_columns("batch_items")}

        assert "worktree_db_host" not in cols, (
            f"worktree_db_host still present after downgrade. Available: {list(cols.keys())}"
        )
        assert "worktree_db_name" not in cols
        assert "worktree_db_user" not in cols
        assert "worktree_db_password" not in cols

    def test_upgrade_idempotent(self, db_engine: Engine, migrated_engine: Engine) -> None:
        """Re-running upgrade is idempotent — columns already exist, no error."""
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", "orch/db/migrations")
        alembic_cfg.set_main_option(
            "sqlalchemy.url", migrated_engine.url.render_as_string(hide_password=False)
        )
        # Running upgrade again from current head should be a no-op
        command.upgrade(alembic_cfg, "head")

        inspector = inspect(db_engine)
        cols = {c["name"]: c for c in inspector.get_columns("batch_items")}
        assert "worktree_db_host" in cols
        assert "worktree_db_name" in cols
        assert "worktree_db_user" in cols
        assert "worktree_db_password" in cols

    def test_re_upgrade_after_downgrade(self, db_engine: Engine) -> None:
        """Full round-trip: downgrade then re-upgrade restores all four columns."""
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", "orch/db/migrations")
        alembic_cfg.set_main_option(
            "sqlalchemy.url", db_engine.url.render_as_string(hide_password=False)
        )

        # Downgrade
        command.downgrade(alembic_cfg, PREV_REVISION)

        # Re-upgrade
        command.upgrade(alembic_cfg, MIGRATION_REV)

        inspector = inspect(db_engine)
        cols = {c["name"]: c for c in inspector.get_columns("batch_items")}
        assert "worktree_db_host" in cols
        assert "worktree_db_name" in cols
        assert "worktree_db_user" in cols
        assert "worktree_db_password" in cols
