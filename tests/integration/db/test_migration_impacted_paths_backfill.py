"""Integration test for F-00076 migration backfill of impacted_paths.

Verifies that the alembic migration correctly backfills impacted_paths for
actionable work items (status NOT IN ('completed', 'archived')) using
extract_affected_files(), and skips terminal-status items.

The test uses the Alembic Python API. The container starts empty; we
upgrade to PREV_REVISION (schema before this migration), insert raw rows,
upgrade to MIGRATION_REV (which adds the column AND backfills), and then
inspect the column. Each test gets its own container so tests can mutate
the schema freely without polluting siblings.

IMPORTANT: Never downgrade with `-1` in migration tests; use a specific
revision ID so the test stays stable as new migrations land above.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from orch.batch_planner import extract_affected_files

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.engine import Engine

# The migration under test adds the impacted_paths column to work_items.
MIGRATION_REV = "4876b3246ff2"  # F-00076
PREV_REVISION = "a9861af32872"


@pytest.fixture
def pg_container() -> Iterator[PostgresContainer]:
    """Each test gets a fresh container so migrations can run upgrade/downgrade
    without interfering with other tests."""
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture
def db_engine(pg_container: PostgresContainer) -> Iterator[Engine]:
    """Create a SQLAlchemy engine pointed at the testcontainer DB with env vars set.

    Args:
        pg_container: The running PostgreSQL testcontainer.

    Yields:
        A configured SQLAlchemy engine; disposes after the test completes.
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
        engine = create_engine(url, pool_pre_ping=True)
        yield engine
        engine.dispose()


def _alembic_config(engine: Engine) -> Config:
    """Build an Alembic Config pointing at the given engine's URL.

    Args:
        engine: The SQLAlchemy engine whose URL will be used.

    Returns:
        An Alembic Config object ready for upgrade/downgrade calls.
    """
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    return cfg


def _insert_work_item(
    engine: Engine,
    project_id: str,
    item_id: str,
    title: str,
    status: str,
    phase: str,
    design_doc_content: str,
) -> None:
    """Insert a work_items row at PREV_REVISION schema (no impacted_paths column)."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO work_items "
                "(project_id, id, type, title, status, phase, config, depends_on, blocks, "
                "design_doc_content) "
                "VALUES (:pid, :iid, 'Feature', :title, :status, :phase, "
                "'{}', '{}', '{}', :ddc)"
            ),
            {
                "pid": project_id,
                "iid": item_id,
                "title": title,
                "status": status,
                "phase": phase,
                "ddc": design_doc_content,
            },
        )


def test_migration_backfill_impacted_paths(db_engine: Engine) -> None:
    """Backfill populates impacted_paths for actionable items only.

    1. Apply migrations up to PREV_REVISION (no impacted_paths column yet).
    2. Insert work items with design_doc_content via raw SQL.
    3. Upgrade to MIGRATION_REV — this adds the column AND backfills it.
    4. Verify impacted_paths values for actionable and terminal-status items.
    """
    alembic_cfg = _alembic_config(db_engine)

    command.upgrade(alembic_cfg, PREV_REVISION)

    project_id = "f76-test-proj"
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO projects (id, display_name, repo_root, config) "
                "VALUES (:pid, 'F-00076 Test Project', '/repos/f76-test', '{}')"
            ),
            {"pid": project_id},
        )

    design_doc_production_only = """
# Test Feature

## Description
Modify orch/foo.py and orch/bar/baz.py for the new feature.

## Out of Scope
Some notes.

## Impacted Paths
- orch/foo.py
- orch/bar/baz.py
"""
    design_doc_with_test_path = """
# Test Feature With Tests

## Description
Change orch/core/main.py and tests/test_core.py for the feature.

## Impacted Paths
- orch/core/main.py
- tests/test_core.py
"""
    design_doc_completed = """
# Completed Feature

## Description
Archived feature touching dashboard/index.html only.
"""

    _insert_work_item(
        db_engine,
        project_id,
        "I-00001",
        "Active Feature",
        "draft",
        "active",
        design_doc_production_only,
    )
    _insert_work_item(
        db_engine,
        project_id,
        "I-00002",
        "In-Progress Feature",
        "in_progress",
        "work",
        design_doc_with_test_path,
    )
    _insert_work_item(
        db_engine,
        project_id,
        "I-00003",
        "Completed Feature",
        "completed",
        "done",
        design_doc_completed,
    )

    # Apply the migration under test — it adds the column AND backfills it.
    command.upgrade(alembic_cfg, MIGRATION_REV)

    with db_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, impacted_paths FROM work_items WHERE project_id = :pid ORDER BY id"),
            {"pid": project_id},
        ).all()

    paths_by_id = {r.id: list(r.impacted_paths) for r in rows}
    assert set(paths_by_id) == {"I-00001", "I-00002", "I-00003"}

    expected1 = extract_affected_files(design_doc_production_only)
    assert paths_by_id["I-00001"] == expected1, (
        f"I-00001 impacted_paths mismatch: got {paths_by_id['I-00001']}, expected {expected1}"
    )

    expected2 = extract_affected_files(design_doc_with_test_path)
    assert paths_by_id["I-00002"] == expected2, (
        f"I-00002 impacted_paths mismatch: got {paths_by_id['I-00002']}, expected {expected2}"
    )

    # I-00003 is completed → backfill skipped → default []
    assert paths_by_id["I-00003"] == [], (
        f"I-00003 impacted_paths should be [] (completed), got {paths_by_id['I-00003']}"
    )
