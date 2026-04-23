"""Integration tests for the iw_core_instance migration.

Tests:
- Table exists with exactly one row after alembic upgrade
- instance_id is a valid UUID v4
- CHECK constraint prevents a second row
- alembic downgrade drops the table
- alembic upgrade re-creates with a new UUID
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from testcontainers.postgres import PostgresContainer

if TYPE_CHECKING:
    from sqlalchemy import Engine


@pytest.fixture(scope="module")
def pg_container() -> PostgresContainer:
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def db_engine(pg_container: PostgresContainer) -> Engine:
    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://"))
    os.environ["IW_CORE_DB_HOST"] = str(parsed.hostname)
    os.environ["IW_CORE_DB_PORT"] = str(parsed.port)
    os.environ["IW_CORE_DB_NAME"] = parsed.path.lstrip("/")
    os.environ["IW_CORE_DB_USER"] = str(parsed.username)
    os.environ["IW_CORE_DB_PASSWORD"] = str(parsed.password)

    return create_engine(url, pool_pre_ping=True)


@pytest.fixture(scope="module")
def migrated_engine(db_engine: Engine) -> Engine:
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option("sqlalchemy.url", db_engine.url.render_as_string())

    command.upgrade(alembic_cfg, "head")
    return db_engine


def test_table_created_and_seeded(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        result = conn.execute(text("SELECT id, instance_id, created_at FROM iw_core_instance"))
        rows = list(result)
        assert len(rows) == 1, f"Expected exactly 1 row, got {len(rows)}"

        row = rows[0]
        assert row.id == 1

        uuid_val = row.instance_id
        assert isinstance(uuid_val, uuid.UUID), f"instance_id is not a UUID: {type(uuid_val)}"
        assert uuid_val.version == 4, f"instance_id is not UUID v4: {uuid_val}"

        assert row.created_at is not None


def test_check_constraint_prevents_second_row(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn, pytest.raises(IntegrityError):
        conn.execute(
            text("INSERT INTO iw_core_instance (id, instance_id) VALUES (2, gen_random_uuid())")
        )


def test_downgrade_and_upgrade_round_trip(migrated_engine: Engine) -> None:
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option("sqlalchemy.url", migrated_engine.url.render_as_string())

    # Target the specific revision before this migration so the test is stable
    # regardless of later migrations added on top.
    command.downgrade(alembic_cfg, "824e6e6f34ee")

    with migrated_engine.connect() as conn:
        result = conn.execute(text("SELECT 1 FROM pg_tables WHERE tablename = 'iw_core_instance'"))
        assert result.fetchone() is None, "Table should be dropped after downgrade"

    command.upgrade(alembic_cfg, "head")

    with migrated_engine.connect() as conn:
        result = conn.execute(text("SELECT id, instance_id FROM iw_core_instance"))
        rows = list(result)
        assert len(rows) == 1
        assert rows[0].id == 1
        assert isinstance(rows[0].instance_id, uuid.UUID)
