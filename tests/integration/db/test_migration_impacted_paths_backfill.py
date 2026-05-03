"""Integration test for F-00076 migration backfill of impacted_paths.

Verifies that the alembic migration correctly backfills impacted_paths for
actionable work items (status NOT IN ('completed', 'archived')) using
extract_affected_files(), and skips terminal-status items.

IMPORTANT: Never downgrade with `-1` in migration tests; use a specific
revision ID so the test stays stable as new migrations land above.

Uses the Alembic Python API (like test_iw_core_instance_migration.py).
The db_engine fixture yields first (without tables), migrated_engine applies
all migrations up to head, and the test function inserts data and verifies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from orch.batch_planner import extract_affected_files
from orch.db.models import Project, WorkItem

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# The migration under test adds the impacted_paths column to work_items.
# We need to first apply all migrations up to PREV_REVISION to create all tables.
# The initial migration (a1b2c3d4e5f6) is the base.
PREV_REVISION = "a9861af32872"  # head at time of F-00076 implementation
INITIAL_REVISION = "a1b2c3d4e5f6"  # initial schema migration


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
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("IW_CORE_DB_HOST", str(parsed.hostname))
        mp.setenv("IW_CORE_DB_PORT", str(parsed.port))
        mp.setenv("IW_CORE_DB_NAME", parsed.path.lstrip("/"))
        mp.setenv("IW_CORE_DB_USER", str(parsed.username))
        mp.setenv("IW_CORE_DB_PASSWORD", str(parsed.password))
        yield create_engine(url, pool_pre_ping=True)


@pytest.fixture(scope="module")
def migrated_engine(db_engine: Engine) -> Engine:
    """Apply all alembic migrations up to head (includes the F-00076 migration)."""
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option(
        "sqlalchemy.url", db_engine.url.render_as_string(hide_password=False)
    )
    # Run all migrations — the initial migration creates the FTS trigger,
    # so no separate FTS setup is needed here.
    command.upgrade(alembic_cfg, "head")
    return db_engine


@pytest.fixture(scope="module")
def db_session_factory(migrated_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=migrated_engine, autocommit=False, autoflush=False)


def test_migration_backfill_impacted_paths(
    migrated_engine: Engine, db_session_factory: sessionmaker[Session]
) -> None:
    """Backfill populates impacted_paths for actionable items only.

    1. Insert work items with design_doc_content while at PREV_REVISION schema.
    2. Apply the F-00076 migration (which adds impacted_paths and backfills).
    3. Verify impacted_paths values for actionable and terminal-status items.
    """
    # --- Create project and test fixture ---
    connection = migrated_engine.connect()
    transaction = connection.begin()
    session = db_session_factory(bind=connection)

    project = Project(
        id="f76-test-proj",
        display_name="F-00076 Test Project",
        repo_root="/repos/f76-test",
        config={},
    )
    session.add(project)
    session.flush()
    # Store raw IDs so we can use them after the first transaction is rolled back.
    project_id_val = project.id
    session.flush()

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

    # Insert actionable items using raw SQL (ORM mapper includes impacted_paths
    # which does not exist yet at PREV_REVISION schema).
    connection.execute(
        text(
            "INSERT INTO work_items "
            "(project_id, id, type, title, status, phase, config, depends_on, blocks, "
            "design_doc_content) "
            "VALUES (:pid, 'I-00001', 'Feature', 'Active Feature', 'draft', 'active', "
            "'{}', '{}', '{}', :ddc1)"
        ),
        {"pid": project_id_val, "ddc1": design_doc_production_only},
    )
    connection.execute(
        text(
            "INSERT INTO work_items "
            "(project_id, id, type, title, status, phase, config, depends_on, blocks, "
            "design_doc_content) "
            "VALUES (:pid, 'I-00002', 'Feature', 'In-Progress Feature', 'in_progress', "
            "'work', '{}', '{}', '{}', :ddc2)"
        ),
        {"pid": project_id_val, "ddc2": design_doc_with_test_path},
    )
    connection.execute(
        text(
            "INSERT INTO work_items "
            "(project_id, id, type, title, status, phase, config, depends_on, blocks, "
            "design_doc_content) "
            "VALUES (:pid, 'I-00003', 'Feature', 'Completed Feature', 'completed', 'done', "
            "'{}', '{}', '{}', :ddc3)"
        ),
        {"pid": project_id_val, "ddc3": design_doc_completed},
    )
    session.commit()

    transaction.rollback()
    connection.close()

    # --- Verify the backfill results (migration already applied in migrated_engine) ---
    connection2 = migrated_engine.connect()
    transaction2 = connection2.begin()
    session2 = db_session_factory(bind=connection2)

    # I-00001: should have production paths only (no test filter since none present)
    row1 = session2.query(WorkItem).filter_by(project_id=project_id_val, id="I-00001").first()
    assert row1 is not None
    expected1 = extract_affected_files(design_doc_production_only)
    assert row1.impacted_paths == expected1, (
        f"I-00001 impacted_paths mismatch: got {row1.impacted_paths}, expected {expected1}"
    )

    # I-00002: should have production path only (test path filtered out)
    row2 = session2.query(WorkItem).filter_by(project_id=project_id_val, id="I-00002").first()
    assert row2 is not None
    expected2 = extract_affected_files(design_doc_with_test_path)
    assert row2.impacted_paths == expected2, (
        f"I-00002 impacted_paths mismatch: got {row2.impacted_paths}, expected {expected2}"
    )
    # Verify test path is NOT present
    assert "tests/test_core.py" not in row2.impacted_paths, (
        "Test path should be filtered out of impacted_paths"
    )

    # I-00003: completed — backfill MUST have skipped it (default [])
    row3 = session2.query(WorkItem).filter_by(project_id=project_id_val, id="I-00003").first()
    assert row3 is not None
    assert row3.impacted_paths == [], (
        f"I-00003 impacted_paths should be [] (completed item), got {row3.impacted_paths}"
    )

    transaction2.rollback()
    connection2.close()
