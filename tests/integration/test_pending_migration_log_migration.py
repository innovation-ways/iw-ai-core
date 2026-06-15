"""Integration tests for the pending_migration_log migration.

Tests:
- Table exists with correct columns and types after alembic upgrade
- CHECK constraints enforce valid enum values (direction, phase)
- Indexes exist: (batch_id, started_at DESC), (revision, phase)
- batch_id column accepts values (note: DB-level FK not enforced due to
  batches.id being TEXT while batch_id is BIGINT — see design doc)
- Round-trip: alembic downgrade drops table, alembic upgrade re-creates empty
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from sqlalchemy import Engine


@pytest.fixture
def migrated_engine(db_engine: Engine) -> Engine:
    """Per-test PostgreSQL clone, already migrated to head.

    Backed by the conftest ``db_engine`` (R-00077 template-clone): every test
    gets its own isolated database, so a downgrade or row insert in one test
    never leaks into another regardless of ``pytest-randomly`` order.

    Args:
        db_engine: Function-scoped per-test clone from the integration conftest.

    Returns:
        The same per-test engine, named ``migrated_engine`` for readability.
    """
    return db_engine


def test_table_exists_with_columns(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'pending_migration_log'
                ORDER BY ordinal_position
            """)
        )
        cols = {row[0]: {"type": row[1], "nullable": row[2]} for row in result}

    assert "id" in cols
    assert cols["id"]["type"] == "bigint"
    assert cols["id"]["nullable"] == "NO"

    assert "revision" in cols
    assert cols["revision"]["type"] == "text"
    assert cols["revision"]["nullable"] == "NO"

    assert "direction" in cols
    assert cols["direction"]["type"] == "text"
    assert cols["direction"]["nullable"] == "NO"

    assert "phase" in cols
    assert cols["phase"]["type"] == "text"
    assert cols["phase"]["nullable"] == "NO"

    assert "batch_id" in cols
    assert cols["batch_id"]["type"] == "bigint"
    assert cols["batch_id"]["nullable"] == "YES"

    assert "started_at" in cols
    assert cols["started_at"]["type"] == "timestamp with time zone"
    assert cols["started_at"]["nullable"] == "NO"

    assert "completed_at" in cols
    assert cols["completed_at"]["type"] == "timestamp with time zone"
    assert cols["completed_at"]["nullable"] == "YES"

    assert "success" in cols
    assert cols["success"]["type"] == "boolean"
    assert cols["success"]["nullable"] == "YES"

    assert "stdout_tail" in cols
    assert cols["stdout_tail"]["type"] == "text"
    assert cols["stdout_tail"]["nullable"] == "YES"

    assert "stderr_tail" in cols
    assert cols["stderr_tail"]["type"] == "text"
    assert cols["stderr_tail"]["nullable"] == "YES"

    assert "error_message" in cols
    assert cols["error_message"]["type"] == "text"
    assert cols["error_message"]["nullable"] == "YES"

    assert "created_at" in cols
    assert cols["created_at"]["type"] == "timestamp with time zone"
    assert cols["created_at"]["nullable"] == "NO"


def _insert_invalid_direction(conn):
    conn.execute(
        text(
            "INSERT INTO pending_migration_log "
            "(revision, direction, phase) "
            "VALUES ('rev1', 'invalid_dir', 'dry_run')"
        )
    )
    conn.commit()


def _insert_invalid_phase(conn):
    conn.execute(
        text(
            "INSERT INTO pending_migration_log "
            "(revision, direction, phase) "
            "VALUES ('rev2', 'upgrade', 'invalid_phase')"
        )
    )
    conn.commit()


def test_direction_check_constraint(migrated_engine: Engine) -> None:
    """The direction CHECK constraint rejects a value outside the allowed enum."""
    with migrated_engine.connect() as conn, pytest.raises(IntegrityError):
        _insert_invalid_direction(conn)


def test_phase_check_constraint(migrated_engine: Engine) -> None:
    """The phase CHECK constraint rejects a value outside the allowed enum."""
    with migrated_engine.connect() as conn, pytest.raises(IntegrityError):
        _insert_invalid_phase(conn)


def test_valid_enum_values_accepted(migrated_engine: Engine) -> None:
    """All valid (direction, phase) enum combinations are accepted by the table."""
    with migrated_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO pending_migration_log "
                "(id, revision, direction, phase) "
                "VALUES (DEFAULT, 'test_rev_1', 'upgrade', 'dry_run')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO pending_migration_log "
                "(id, revision, direction, phase) "
                "VALUES (DEFAULT, 'test_rev_2', 'downgrade', 'apply')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO pending_migration_log "
                "(id, revision, direction, phase) "
                "VALUES (DEFAULT, 'test_rev_3', 'upgrade', 'rollback')"
            )
        )
        conn.commit()

        result = conn.execute(
            text(
                "SELECT COUNT(*) FROM pending_migration_log "
                "WHERE phase IN ('dry_run', 'apply', 'rollback')"
            )
        )
        assert result.scalar() == 3


def test_indexes_exist(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT indexname, indexdef "
                "FROM pg_indexes "
                "WHERE tablename = 'pending_migration_log'"
            )
        )
        indexes = {row[0]: row[1] for row in result}

    index_names = set(indexes.keys())
    assert "ix_pending_migration_log_batch" in index_names
    assert "ix_pending_migration_log_revision" in index_names

    batch_index_def = indexes["ix_pending_migration_log_batch"]
    assert "batch_id" in batch_index_def
    assert "started_at" in batch_index_def
    assert "DESC" in batch_index_def

    revision_index_def = indexes["ix_pending_migration_log_revision"]
    assert "revision" in revision_index_def
    assert "phase" in revision_index_def


def test_batch_id_accepts_values(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO pending_migration_log "
                "(id, revision, direction, phase, batch_id) "
                "VALUES (DEFAULT, 'test_rev', 'upgrade', 'dry_run', NULL)"
            )
        )
        conn.commit()

        result = conn.execute(
            text("SELECT id, batch_id FROM pending_migration_log WHERE revision = 'test_rev'")
        )
        row = result.fetchone()
        assert row is not None
        log_id = row[0]

        conn.execute(
            text("UPDATE pending_migration_log SET batch_id = 999 WHERE id = :log_id"),
            {"log_id": log_id},
        )
        conn.commit()

        result = conn.execute(
            text("SELECT batch_id FROM pending_migration_log WHERE id = :log_id"),
            {"log_id": log_id},
        )
        assert result.scalar() == 999


def test_downgrade_drops_table(migrated_engine: Engine) -> None:
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option(
        "sqlalchemy.url", migrated_engine.url.render_as_string(hide_password=False)
    )

    # Downgrade specifically to the revision before this migration so the
    # test continues to work after later migrations are added on top.
    command.downgrade(alembic_cfg, "2bd86f8c105c")

    with migrated_engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1 FROM pg_tables WHERE tablename = 'pending_migration_log'")
        )
        assert result.fetchone() is None


def test_upgrade_recreates_table_empty(migrated_engine: Engine) -> None:
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option(
        "sqlalchemy.url", migrated_engine.url.render_as_string(hide_password=False)
    )

    # Downgrade first so the upgrade genuinely recreates the table fresh and empty.
    command.downgrade(alembic_cfg, "2bd86f8c105c")
    command.upgrade(alembic_cfg, "head")

    with migrated_engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1 FROM pg_tables WHERE tablename = 'pending_migration_log'")
        )
        assert result.fetchone() is not None

        count_result = conn.execute(text("SELECT COUNT(*) FROM pending_migration_log"))
        assert count_result.scalar() == 0
