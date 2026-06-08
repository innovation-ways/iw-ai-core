"""Integration tests for CR-00066 migration: context_tokens columns.

Verifies that the alembic migration:
1. Adds context_window_tokens to agent_runtime_options.
2. Adds context_tokens_peak and context_tokens_last to step_runs.
3. Seeds the 4 known models with context_window_tokens = 200000.
4. Downgrade drops all three columns cleanly.
5. ORM can read/write the new columns.

Uses the shared pgtestdbpy-backed fixtures from tests/integration/conftest.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# The migration under test adds context_tokens columns.
# We need to apply all migrations up to the PREV_REVISION to establish the
# baseline schema, then apply the CR-00066 migration.
PREV_REVISION = "8263c6b7746b"  # parent of cr00066_add_context_tokens_columns


@pytest.fixture(scope="module")
def pg_container() -> PostgresContainer:
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def db_engine(pg_container: PostgresContainer) -> Engine:
    """Use the exact URL construction that works in test_F00077_migration.py."""
    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("IW_CORE_DB_HOST", str(parsed.hostname))
        mp.setenv("IW_CORE_DB_PORT", str(parsed.port))
        mp.setenv("IW_CORE_DB_NAME", parsed.path.lstrip("/"))
        mp.setenv("IW_CORE_DB_USER", str(parsed.username))
        mp.setenv("IW_CORE_DB_PASSWORD", str(parsed.password))
        yield create_engine(url, pool_pre_ping=True)


@pytest.fixture(scope="module")
def migrated_engine(db_engine: Engine) -> Engine:
    """Apply all alembic migrations up to head (includes the CR-00066 migration)."""
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option(
        "sqlalchemy.url", db_engine.url.render_as_string(hide_password=False)
    )
    command.upgrade(alembic_cfg, "head")
    return db_engine


@pytest.fixture(scope="module")
def db_session_factory(migrated_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=migrated_engine, autocommit=False, autoflush=False)


class TestContextTokensMigration:
    """Verify CR-00066 migration applied correctly."""

    def test_migration_adds_context_window_tokens_column(self, migrated_engine: Engine) -> None:
        """agent_runtime_options gains context_window_tokens INT NULL after upgrade."""
        inspector = inspect(migrated_engine)
        cols = {c["name"] for c in inspector.get_columns("agent_runtime_options")}
        assert "context_window_tokens" in cols
        col = next(
            c
            for c in inspector.get_columns("agent_runtime_options")
            if c["name"] == "context_window_tokens"
        )
        assert col["nullable"] is True
        assert str(col["type"]) == "INTEGER"

    def test_migration_adds_step_run_token_columns(self, migrated_engine: Engine) -> None:
        """step_runs gains context_tokens_peak and context_tokens_last INT NULL."""
        inspector = inspect(migrated_engine)
        cols = {c["name"] for c in inspector.get_columns("step_runs")}
        assert "context_tokens_peak" in cols
        assert "context_tokens_last" in cols
        for col_name in ("context_tokens_peak", "context_tokens_last"):
            col = next(c for c in inspector.get_columns("step_runs") if c["name"] == col_name)
            assert col["nullable"] is True
            assert str(col["type"]) == "INTEGER"

    def test_migration_seeds_known_models(self, migrated_engine: Engine) -> None:
        """After upgrade, the seeded Claude models keep 200000 and minimax M3 is 1M.

        Note: some models appear multiple times with different cli_tools
        (e.g. claude-opus-4-7 with both opencode and claude). That's valid —
        we just verify ALL rows for a model have the expected value. The minimax
        row is seeded as M2.7/200000 by CR-00066, renamed to M3 by 08850d673ff6,
        then raised to a 1,000,000-token window by 53e45cb21742; so at head the
        Claude models stay at 200000 while minimax/MiniMax-M3 is 1,000,000.
        """
        connection = migrated_engine.connect()
        try:
            result = connection.execute(
                text(
                    """
                    SELECT model, context_window_tokens
                    FROM agent_runtime_options
                    WHERE model IN (
                        'claude-opus-4-7',
                        'claude-sonnet-4-6',
                        'claude-haiku-4-5-20251001'
                    )
                    ORDER BY model
                    """
                )
            )
            rows = list(result.fetchall())
            assert len(rows) >= 3, f"Expected at least 3 seeded model rows, got {len(rows)}: {rows}"
            for model, tokens in rows:
                assert tokens == 200000, (
                    f"Model {model} expected context_window_tokens=200000, got {tokens}"
                )

            m3_rows = connection.execute(
                text(
                    """
                    SELECT model, context_window_tokens
                    FROM agent_runtime_options
                    WHERE model = 'minimax/MiniMax-M3'
                    """
                )
            ).fetchall()
            assert len(m3_rows) >= 1, "Expected at least one minimax/MiniMax-M3 row"
            for model, tokens in m3_rows:
                assert tokens == 1000000, (
                    f"Model {model} expected context_window_tokens=1000000 (M3 1M window), "
                    f"got {tokens}"
                )
        finally:
            connection.close()

    def test_unknown_models_have_null_context_window(self, migrated_engine: Engine) -> None:
        """Models not in the seed list have NULL context_window_tokens."""
        connection = migrated_engine.connect()
        try:
            result = connection.execute(
                text(
                    """
                    SELECT model, context_window_tokens
                    FROM agent_runtime_options
                    WHERE model NOT IN (
                        'claude-opus-4-7',
                        'claude-opus-4-8',
                        'claude-sonnet-4-6',
                        'claude-haiku-4-5-20251001',
                        'minimax/MiniMax-M3'
                    )
                    """
                )
            )
            rows = list(result.fetchall())
            # All non-seeded rows must be NULL
            nulls = [(m, t) for m, t in rows if t is None]
            assert len(nulls) == len(rows), (
                f"All non-seeded models must have NULL context_window_tokens; "
                f"found non-NULL: {[m for m, t in rows if t is not None]}"
            )
        finally:
            connection.close()

    def test_migration_downgrade_removes_columns(self, migrated_engine: Engine) -> None:
        """alembic downgrade -1 drops all three columns cleanly."""
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", "orch/db/migrations")
        alembic_cfg.set_main_option(
            "sqlalchemy.url", migrated_engine.url.render_as_string(hide_password=False)
        )
        # Downgrade to the parent of CR-00066 (removes the 3 new columns only)
        command.downgrade(alembic_cfg, PREV_REVISION)

        # Verify columns are gone
        inspector = inspect(migrated_engine)
        aro_cols = {c["name"] for c in inspector.get_columns("agent_runtime_options")}
        assert "context_window_tokens" not in aro_cols

        sr_cols = {c["name"] for c in inspector.get_columns("step_runs")}
        assert "context_tokens_peak" not in sr_cols
        assert "context_tokens_last" not in sr_cols

        # Re-apply migration so other tests can continue
        command.upgrade(alembic_cfg, "head")

    def test_orm_context_tokens_read_write(
        self, migrated_engine: Engine, db_session_factory: sessionmaker[Session]
    ) -> None:
        """Can write and read context_tokens_peak / context_tokens_last via ORM."""
        from orch.db.models import (
            Project,
            StepRun,
            WorkItem,
            WorkItemType,
        )

        connection = migrated_engine.connect()
        transaction = connection.begin()
        session = db_session_factory(bind=connection)

        # Create a minimal project and work-item + step so we can insert a StepRun
        project = Project(
            id="cr00066-orm-test-proj",
            display_name="CR-00066 ORM Test",
            repo_root="/repos/cr00066-orm-test",
            config={},
        )
        session.add(project)
        session.flush()

        item = WorkItem(
            project_id=project.id,
            id="cr00066-orm-test-item",
            title="CR-00066 ORM test item",
            type=WorkItemType.Feature,
        )
        session.add(item)
        session.flush()

        from orch.db.models import WorkflowStep

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item.id,
            step_number=1,
            step_id="S01",
            agent_label="test-agent",
            step_type="implementation",
        )
        session.add(step)
        session.flush()

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status="running",
            context_tokens_peak=150000,
            context_tokens_last=148000,
        )
        session.add(run)
        session.flush()

        # Verify values round-trip
        assert run.context_tokens_peak == 150000
        assert run.context_tokens_last == 148000

        # Update via ORM
        run.context_tokens_peak = 155000
        run.context_tokens_last = 152000
        session.flush()

        session.expire(run)
        assert run.context_tokens_peak == 155000
        assert run.context_tokens_last == 152000

        transaction.rollback()
        connection.close()

    def test_orm_context_window_tokens_read_write(
        self, migrated_engine: Engine, db_session_factory: sessionmaker[Session]
    ) -> None:
        """Can write and read context_window_tokens on AgentRuntimeOption via ORM."""
        from orch.db.models import AgentRuntimeOption

        connection = migrated_engine.connect()
        transaction = connection.begin()
        session = db_session_factory(bind=connection)

        # Find an existing row to update
        option = session.query(AgentRuntimeOption).first()
        assert option is not None

        original = option.context_window_tokens

        # Write new value
        option.context_window_tokens = 100000
        session.flush()
        session.expire(option)

        assert option.context_window_tokens == 100000

        # Set back to original (or None if it was None)
        option.context_window_tokens = original
        session.flush()

        transaction.rollback()
        connection.close()
