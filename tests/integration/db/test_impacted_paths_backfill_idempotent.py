"""Integration test for F-00076 — impacted_paths backfill is idempotent.

Runs the F-00076 migration twice (downgrade → upgrade → downgrade → upgrade)
and verifies that impacted_paths values are identical after both runs,
with no duplicate rows or other schema corruption.

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
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from orch.batch_planner import extract_affected_files
from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    Project,
    WorkItem,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


# The migration under test
MIGRATION_REV = "4876b3246ff2"
PREV_REVISION = "a9861af32872"


def _raw_insert(
    pid: str,
    iid: str,
    title: str,
    status: str,
    phase: str,
    ddc: str,
) -> str:
    # Hardcoded column list; values are test-controlled constants — safe.
    # noqa: S608
    return (
        "INSERT INTO work_items "
        "(project_id, id, type, title, status, phase, config, "
        "depends_on, blocks, design_doc_content) "
        "VALUES ('"
        + pid
        + "', '"
        + iid
        + "', 'Feature', '"
        + title
        + "', '"
        + status
        + "', '"
        + phase
        + "', "
        "'{}', '{}', '{}', :ddc)"
    )


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
        return create_engine(url, pool_pre_ping=True)


@pytest.fixture(scope="module")
def migrated_engine(db_engine: Engine) -> Engine:
    """Apply all alembic migrations up to head."""
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option(
        "sqlalchemy.url", db_engine.url.render_as_string(hide_password=False)
    )
    command.upgrade(alembic_cfg, "head")

    # Install FTS triggers after migrations (tables now exist)
    with db_engine.connect() as conn:
        conn.execute(text(FTS_FUNCTION_SQL))
        conn.execute(text(FTS_TRIGGER_SQL))
        conn.commit()

    return db_engine


@pytest.fixture(scope="module")
def db_session_factory(migrated_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=migrated_engine, autocommit=False, autoflush=False)


def _upgrade_to_f76(session_factory: sessionmaker[Session]) -> None:
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option(
        "sqlalchemy.url",
        "postgresql+psycopg://test:test@localhost:5433/test",
    )
    command.upgrade(cfg, MIGRATION_REV)


def _downgrade_to_prev(session_factory: sessionmaker[Session]) -> None:
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option(
        "sqlalchemy.url",
        "postgresql+psycopg://test:test@localhost:5433/test",
    )
    command.downgrade(cfg, PREV_REVISION)


def test_backfill_idempotent(
    migrated_engine: Engine,
    db_session_factory: sessionmaker[Session],
) -> None:
    """impacted_paths is identical after two upgrade/downgrade cycles.

    Run: upgrade → downgrade → upgrade
    Assert: impacted_paths values match after both upgrades.
    Assert: no duplicate rows.
    """
    design_doc_a = """
# Test Feature A

## Description
Modify orch/foo.py and orch/bar/baz.py.

## Out of Scope
Irrelevant.

## Impacted Paths
- orch/foo.py
- orch/bar/baz.py
"""
    design_doc_b = """
# Test Feature B

## Description
Change tests/test_core.py and lib/utils.py for the feature.

## Impacted Paths
- lib/utils.py
"""

    # --- Phase 1: Insert data at PREV_REVISION schema ---
    connection = migrated_engine.connect()
    transaction = connection.begin()
    session = db_session_factory(bind=connection)

    project = Project(
        id="f76-idempotent",
        display_name="F-00076 Idempotency Test",
        repo_root="/repos/f76-idempotent",
        config={},
    )
    session.add(project)
    session.flush()
    project_id = project.id
    session.flush()

    connection.execute(
        text(_raw_insert(project_id, "I-00011", "Feature A", "in_progress", "work")),
        {"ddc": design_doc_a},
    )
    connection.execute(
        text(_raw_insert(project_id, "I-00012", "Feature B", "draft", "active")),
        {"ddc": design_doc_b},
    )
    session.commit()
    transaction.rollback()
    connection.close()

    # --- Phase 2: first upgrade (migration already applied by fixture) ---
    conn1 = migrated_engine.connect()
    tx1 = conn1.begin()
    sess1 = db_session_factory(bind=conn1)

    rows_after_first_upgrade = (
        sess1.query(WorkItem).filter_by(project_id=project_id).order_by(WorkItem.id).all()
    )
    paths_after_first = {r.id: list(r.impacted_paths) for r in rows_after_first_upgrade}

    tx1.rollback()
    conn1.close()

    # --- Phase 3: downgrade to PREV_REVISION ---
    _downgrade_to_prev(db_session_factory)

    # Delete existing rows so we can re-insert at prev schema
    conn_drop = migrated_engine.connect()
    tx_drop = conn_drop.begin()
    sess_drop = db_session_factory(bind=conn_drop)
    sess_drop.query(WorkItem).filter_by(project_id=project_id).delete()
    sess_drop.commit()
    tx_drop.rollback()
    conn_drop.close()

    # Re-insert at prev schema
    conn_reinsert = migrated_engine.connect()
    tx_reinsert = conn_reinsert.begin()
    sess_reinsert = db_session_factory(bind=conn_reinsert)
    sess_reinsert.execute(
        text(_raw_insert(project_id, "I-00011", "Feature A", "in_progress", "work")),
        {"ddc": design_doc_a},
    )
    sess_reinsert.execute(
        text(_raw_insert(project_id, "I-00012", "Feature B", "draft", "active")),
        {"ddc": design_doc_b},
    )
    sess_reinsert.commit()
    tx_reinsert.rollback()
    conn_reinsert.close()

    # --- Phase 4: second upgrade ---
    _upgrade_to_f76(db_session_factory)

    # --- Phase 5: verify after second upgrade ---
    conn2 = migrated_engine.connect()
    tx2 = conn2.begin()
    sess2 = db_session_factory(bind=conn2)

    rows_after_second_upgrade = (
        sess2.query(WorkItem).filter_by(project_id=project_id).order_by(WorkItem.id).all()
    )
    paths_after_second = {r.id: list(r.impacted_paths) for r in rows_after_second_upgrade}

    tx2.rollback()
    conn2.close()

    # --- Assertions ---
    expected_a = extract_affected_files(design_doc_a)
    assert paths_after_first["I-00011"] == expected_a, (
        f"I-00011 after first: {paths_after_first['I-00011']} != expected {expected_a}"
    )
    assert paths_after_second["I-00011"] == expected_a, (
        f"I-00011 after second: {paths_after_second['I-00011']} != expected {expected_a}"
    )

    expected_b = extract_affected_files(design_doc_b)
    assert paths_after_first["I-00012"] == expected_b
    assert paths_after_second["I-00012"] == expected_b

    count_after_first = len(rows_after_first_upgrade)
    count_after_second = len(rows_after_second_upgrade)
    assert count_after_first == count_after_second == 2, (
        f"Row count mismatch: first={count_after_first}, second={count_after_second}"
    )


def test_no_duplicate_rows_after_double_upgrade(
    migrated_engine: Engine,
    db_session_factory: sessionmaker[Session],
) -> None:
    """After two sequential upgrades (no downgrade between), no duplicate rows exist.

    This can happen if the upgrade is accidentally run twice without a prior downgrade.
    The column addition must be idempotent (IF NOT EXISTS semantics).
    """
    conn = migrated_engine.connect()
    tx = conn.begin()
    sess = db_session_factory(bind=conn)

    project = Project(
        id="f76-dup-test",
        display_name="F-00076 Dup Test",
        repo_root="/repos/f76-dup-test",
        config={},
    )
    sess.add(project)
    sess.flush()
    pid = project.id
    sess.commit()
    tx.rollback()
    conn.close()

    # Run upgrade twice — second should be idempotent
    _upgrade_to_f76(db_session_factory)
    _upgrade_to_f76(db_session_factory)

    conn2 = migrated_engine.connect()
    tx2 = conn2.begin()
    sess2 = db_session_factory(bind=conn2)

    project_count = sess2.query(Project).filter_by(id=pid).count()
    assert project_count == 1, f"Duplicate project rows: {project_count}"

    tx2.rollback()
    conn2.close()
