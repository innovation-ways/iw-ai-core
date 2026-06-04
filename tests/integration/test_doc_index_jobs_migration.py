"""Integration tests for the doc_index_jobs migration.

Tests:
- Table exists with all expected columns after alembic upgrade
- All column types and defaults match the spec
- Both indexes exist
- INSERT with only required columns succeeds
- alembic downgrade drops table and indexes cleanly
- alembic upgrade re-creates them
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from testcontainers.postgres import PostgresContainer

if TYPE_CHECKING:
    from sqlalchemy import Engine


DOC_INDEX_JOBS_REVISION = "74f9b2350784"
BEFORE_DOC_INDEX_JOBS_REVISION = "1fb2eb17b580"


@pytest.fixture(scope="module")
def pg_container() -> PostgresContainer:
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def db_engine(pg_container: PostgresContainer) -> Engine:
    """Engine pointed at the testcontainer.

    Sets IW_CORE_DB_* env vars so any code that builds its connection from
    `orch.config.get_db_url()` reaches the testcontainer rather than the live
    platform DB. The env vars are restored on teardown so they don't leak to
    other test modules whose unit tests would otherwise try to connect to
    this now-stopped container's port.
    """
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
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option(
        "sqlalchemy.url", db_engine.url.render_as_string(hide_password=False)
    )

    command.upgrade(alembic_cfg, "head")
    return db_engine


def test_table_exists(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        result = conn.execute(text("SELECT 1 FROM pg_tables WHERE tablename = 'doc_index_jobs'"))
        assert result.fetchone() is not None, "doc_index_jobs table should exist"


def _type_name(col: dict) -> str:
    return col["type"].__class__.__name__.upper()


def test_columns_and_types(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    columns = {col["name"]: col for col in inspector.get_columns("doc_index_jobs")}

    assert "id" in columns
    assert _type_name(columns["id"]) == "TEXT"
    assert not columns["id"]["nullable"]

    assert "project_id" in columns
    assert _type_name(columns["project_id"]) == "TEXT"
    assert not columns["project_id"]["nullable"]

    assert "status" in columns
    assert _type_name(columns["status"]) == "TEXT"
    assert not columns["status"]["nullable"]

    assert "provider" in columns
    assert _type_name(columns["provider"]) == "TEXT"
    assert not columns["provider"]["nullable"]

    assert "llm_model" in columns
    assert _type_name(columns["llm_model"]) == "TEXT"
    assert columns["llm_model"]["nullable"]

    assert "embed_model" in columns
    assert _type_name(columns["embed_model"]) == "TEXT"
    assert columns["embed_model"]["nullable"]

    assert "index_tier" in columns
    assert _type_name(columns["index_tier"]) == "TEXT"
    assert columns["index_tier"]["nullable"]

    assert "items_discovered" in columns
    assert _type_name(columns["items_discovered"]) == "INTEGER"
    assert not columns["items_discovered"]["nullable"]

    assert "items_indexed" in columns
    assert _type_name(columns["items_indexed"]) == "INTEGER"
    assert not columns["items_indexed"]["nullable"]

    assert "chunks_created" in columns
    assert _type_name(columns["chunks_created"]) == "INTEGER"
    assert not columns["chunks_created"]["nullable"]

    assert "errors" in columns
    assert _type_name(columns["errors"]) in ("JSON", "JSONB")
    assert not columns["errors"]["nullable"]

    assert "triggered_at" in columns
    assert not columns["triggered_at"]["nullable"]

    assert "started_at" in columns
    assert columns["started_at"]["nullable"]

    assert "completed_at" in columns
    assert columns["completed_at"]["nullable"]

    assert "error_message" in columns
    assert _type_name(columns["error_message"]) == "TEXT"
    assert columns["error_message"]["nullable"]


def test_indexes_exist(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    indexes = {idx["name"] for idx in inspector.get_indexes("doc_index_jobs")}

    assert "idx_doc_index_jobs_project_id" in indexes
    assert "idx_doc_index_jobs_status" in indexes


def test_insert_with_required_columns(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text(
                    "INSERT INTO projects (id, display_name, repo_root) "
                    "VALUES ('test-project', 'Test Project', '/tmp/test')"
                )
            )
            conn.execute(text("INSERT INTO doc_index_jobs (project_id) VALUES ('test-project')"))
        result = conn.execute(
            text("SELECT id, project_id, status, provider FROM doc_index_jobs LIMIT 1")
        )
        rows = list(result)
        assert len(rows) == 1
        row = rows[0]
        assert row.id is not None
        assert row.project_id == "test-project"
        assert row.status == "queued"
        assert row.provider == "local"


def test_downgrade_and_upgrade_round_trip(migrated_engine: Engine) -> None:
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option(
        "sqlalchemy.url", migrated_engine.url.render_as_string(hide_password=False)
    )

    command.downgrade(alembic_cfg, BEFORE_DOC_INDEX_JOBS_REVISION)

    with migrated_engine.connect() as conn:
        result = conn.execute(text("SELECT 1 FROM pg_tables WHERE tablename = 'doc_index_jobs'"))
        assert result.fetchone() is None, "Table should be dropped after downgrade"

    command.upgrade(alembic_cfg, "head")

    with migrated_engine.connect() as conn:
        result = conn.execute(text("SELECT 1 FROM pg_tables WHERE tablename = 'doc_index_jobs'"))
        assert result.fetchone() is not None, "Table should be re-created after upgrade"

        idx_result = conn.execute(
            text(
                "SELECT 1 FROM pg_indexes WHERE tablename = 'doc_index_jobs' "
                "AND indexname = 'idx_doc_index_jobs_project_id'"
            )
        )
        assert idx_result.fetchone() is not None

        idx_result = conn.execute(
            text(
                "SELECT 1 FROM pg_indexes WHERE tablename = 'doc_index_jobs' "
                "AND indexname = 'idx_doc_index_jobs_status'"
            )
        )
        assert idx_result.fetchone() is not None
