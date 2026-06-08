"""Integration tests for I-00105 S01 migration: max_output_tokens column.

AC3: regression test asserting the migration applies and backfills correctly:
1. `agent_runtime_options` gains a `max_output_tokens` INTEGER NULL column.
2. The `pi` / `minimax/MiniMax-M2.7` row is backfilled with `max_output_tokens = 131072`.
3. Other runtimes remain NULL (no hardcoded backfill for unknown models).
4. Downgrade drops the column cleanly.
5. ORM can read/write `max_output_tokens`.

Uses the shared pgtestdbpy-backed fixtures from tests/integration/conftest.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# The I-00105 migration (2be8dc12874f) adds max_output_tokens.
# Establish the baseline at its parent revision.
_PREV_REVISION = "3a3dfec7bfbd"


@pytest.fixture(scope="module")
def pg_container() -> PostgresContainer:
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def migrated_engine(pg_container: PostgresContainer) -> Engine:
    """Apply all alembic migrations up to head (includes the I-00105 migration)."""
    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    engine = create_engine(url, pool_pre_ping=True)

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    command.upgrade(alembic_cfg, "head")
    return engine


@pytest.fixture(scope="module")
def db_session_factory(migrated_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=migrated_engine, autocommit=False, autoflush=False)


class TestI00105MaxOutputTokensMigration:
    """Verify I-00105 S01 migration applies correctly."""

    def test_migration_adds_max_output_tokens_column(self, migrated_engine: Engine) -> None:
        """agent_runtime_options gains max_output_tokens INTEGER NULL."""
        inspector = inspect(migrated_engine)
        cols = {c["name"] for c in inspector.get_columns("agent_runtime_options")}
        assert "max_output_tokens" in cols, (
            "max_output_tokens column must be present in agent_runtime_options"
        )
        col = next(
            c
            for c in inspector.get_columns("agent_runtime_options")
            if c["name"] == "max_output_tokens"
        )
        assert col["nullable"] is True, "max_output_tokens must be nullable (I-00105 spec)"
        assert "INTEGER" in str(col["type"]).upper(), (
            f"max_output_tokens type should be INTEGER, got {col['type']}"
        )

    def test_migration_backfills_pi_minimax(self, migrated_engine: Engine) -> None:
        """pi / minimax MiniMax row has max_output_tokens = 131,072 after upgrade.

        This is the primary backfill target of the I-00105 migration. The row
        was originally seeded as minimax/MiniMax-M2.7; migration 08850d673ff6
        later renamed it to minimax/MiniMax-M3 while preserving the backfilled
        max_output_tokens. At head we therefore assert on the M3 model string.
        MiniMax has a 204,800-token context window but only 131,072-token max
        output, so without this reservation the context gauge would show 64 %
        when the step is actually at or past its effective ceiling (~244 %).
        """
        connection = migrated_engine.connect()
        try:
            result = connection.execute(
                text(
                    """
                    SELECT cli_tool, model, max_output_tokens
                    FROM agent_runtime_options
                    WHERE cli_tool = 'pi'
                      AND model    = 'minimax/MiniMax-M3'
                    """
                )
            )
            rows = list(result.fetchall())
            assert len(rows) == 1, (
                f"Expected exactly one pi/MiniMax-M3 row, got {len(rows)}: {rows}"
            )
            cli_tool, model, max_output = rows[0]
            assert max_output == 131072, (
                f"pi/MiniMax max_output_tokens must be 131072 per I-00105 spec, got {max_output}"
            )
        finally:
            connection.close()

    def test_other_runtimes_remain_null(self, migrated_engine: Engine) -> None:
        """Non-pi/MiniMax runtimes have NULL max_output_tokens (graceful fallback).

        The migration only backfills known models; unknown models fall back to
        NULL so the effective-budget meter degrades to raw-window behaviour
        (the safe fallback, not a crash). The backfilled row is pi/MiniMax-M3 at
        head (renamed from M2.7 by migration 08850d673ff6).
        """
        connection = migrated_engine.connect()
        try:
            result = connection.execute(
                text(
                    """
                    SELECT cli_tool, model, max_output_tokens
                    FROM agent_runtime_options
                    WHERE NOT (cli_tool = 'pi' AND model = 'minimax/MiniMax-M3')
                    ORDER BY cli_tool, model
                    """
                )
            )
            rows = list(result.fetchall())
            null_rows = [(ct, m, v) for ct, m, v in rows if v is None]
            non_null_unexpected = [(ct, m, v) for ct, m, v in rows if v is not None]
            assert len(non_null_unexpected) == 0, (
                f"Only pi/MiniMax-M3 should be backfilled; "
                f"found non-NULL for others: {non_null_unexpected}"
            )
            # At least some rows must exist and be NULL (not all runtimes are unknown)
            assert len(null_rows) >= 1, (
                "Expected at least some other runtime rows to exist and be NULL"
            )
        finally:
            connection.close()

    def test_migration_downgrade_removes_column(self, migrated_engine: Engine) -> None:
        """alembic downgrade to parent drops max_output_tokens cleanly."""
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", "orch/db/migrations")
        alembic_cfg.set_main_option(
            "sqlalchemy.url", migrated_engine.url.render_as_string(hide_password=False)
        )
        # Downgrade to the parent of I-00105 (removes the column only)
        command.downgrade(alembic_cfg, _PREV_REVISION)

        inspector = inspect(migrated_engine)
        aro_cols = {c["name"] for c in inspector.get_columns("agent_runtime_options")}
        assert "max_output_tokens" not in aro_cols, (
            "max_output_tokens must be absent after downgrade"
        )

        # Re-apply migration so subsequent tests in this module can continue
        command.upgrade(alembic_cfg, "head")

    def test_orm_max_output_tokens_read_write(
        self, migrated_engine: Engine, db_session_factory: sessionmaker[Session]
    ) -> None:
        """Can write and read max_output_tokens on AgentRuntimeOption via ORM."""
        from orch.db.models import AgentRuntimeOption

        connection = migrated_engine.connect()
        transaction = connection.begin()
        session = db_session_factory(bind=connection)

        try:
            # Find the pi/MiniMax row (renamed M2.7→M3 by 08850d673ff6; should
            # already have 131072 from the I-00105 backfill, preserved by the swap)
            option = (
                session.query(AgentRuntimeOption)
                .filter_by(cli_tool="pi", model="minimax/MiniMax-M3")
                .first()
            )
            assert option is not None, "pi/MiniMax-M3 row must exist"
            assert option.max_output_tokens == 131072, (
                f"Backfill value should be 131072, got {option.max_output_tokens}"
            )

            # Update via ORM (to an arbitrary value for testing)
            original = option.max_output_tokens
            option.max_output_tokens = 65_536
            session.flush()
            session.expire(option)
            assert option.max_output_tokens == 65_536

            # Restore original
            option.max_output_tokens = original
            session.flush()
            session.expire(option)
            assert option.max_output_tokens == original

            # Set to None (simulate an unknown-model row)
            option.max_output_tokens = None
            session.flush()
            session.expire(option)
            assert option.max_output_tokens is None

            transaction.rollback()
        finally:
            connection.close()

    def test_orm_create_new_runtime_with_max_output_tokens(
        self, migrated_engine: Engine, db_session_factory: sessionmaker[Session]
    ) -> None:
        """Can insert a new AgentRuntimeOption row with max_output_tokens set."""
        from orch.db.models import AgentRuntimeOption

        connection = migrated_engine.connect()
        transaction = connection.begin()
        session = db_session_factory(bind=connection)

        try:
            new_option = AgentRuntimeOption(
                cli_tool="test-cli",
                model="test/model",
                cli_label="Test CLI",
                model_label="Test Model",
                display_name="Test Runtime",
                max_output_tokens=32_768,
            )
            session.add(new_option)
            session.flush()
            session.expire(new_option)

            assert new_option.max_output_tokens == 32_768

            # Re-fetch from DB
            fetched = (
                session.query(AgentRuntimeOption)
                .filter_by(cli_tool="test-cli", model="test/model")
                .first()
            )
            assert fetched is not None
            assert fetched.max_output_tokens == 32_768

            transaction.rollback()
        finally:
            connection.close()
