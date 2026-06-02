"""Integration test for F-00076 — impacted_paths backfill is idempotent.

Runs the F-00076 migration twice (downgrade → upgrade → downgrade → upgrade)
and verifies that impacted_paths values are identical after both runs,
with no duplicate rows or other schema corruption.

IMPORTANT: Never downgrade with `-1` in migration tests; use a specific
revision ID so the test stays stable as new migrations land above.

Each test starts a dedicated container so it can freely upgrade/downgrade.
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


MIGRATION_REV = "4876b3246ff2"
PREV_REVISION = "a9861af32872"


@pytest.fixture
def pg_container() -> Iterator[PostgresContainer]:
    """Provide a fresh PostgreSQL testcontainer per test for isolated migration runs."""
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
    """Insert a work_items row at PREV_REVISION schema (no impacted_paths column).

    Args:
        engine: Database engine to use for the insert.
        project_id: Foreign key to an existing projects row.
        item_id: Unique identifier for the work item.
        title: Human-readable title of the work item.
        status: Initial status string (e.g. 'draft', 'completed').
        phase: Phase string (e.g. 'active', 'work').
        design_doc_content: Raw markdown content for the design document.
    """
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


def _read_paths(engine: Engine, project_id: str) -> dict[str, list[str]]:
    """Read the impacted_paths column for all work items belonging to a project.

    Args:
        engine: Database engine to query.
        project_id: Project whose work items should be fetched.

    Returns:
        A mapping of item ID to its list of impacted path strings.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, impacted_paths FROM work_items WHERE project_id = :pid ORDER BY id"),
            {"pid": project_id},
        ).all()
    return {r.id: list(r.impacted_paths) for r in rows}


def test_backfill_idempotent(db_engine: Engine) -> None:
    """impacted_paths is identical after two upgrade/downgrade cycles.

    Run: PREV → upgrade(MIGRATION_REV) → downgrade(PREV) → upgrade(MIGRATION_REV)
    Assert: impacted_paths values match after both upgrades.
    Assert: no duplicate rows.
    """
    alembic_cfg = _alembic_config(db_engine)

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

    project_id = "f76-idempotent"

    # ---- Phase 1: stand up PREV_REVISION schema and seed work items ----
    command.upgrade(alembic_cfg, PREV_REVISION)
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO projects (id, display_name, repo_root, config) "
                "VALUES (:pid, 'F-00076 Idempotency', '/repos/f76-idempotent', '{}')"
            ),
            {"pid": project_id},
        )
    _insert_work_item(
        db_engine, project_id, "I-00011", "Feature A", "in_progress", "work", design_doc_a
    )
    _insert_work_item(
        db_engine, project_id, "I-00012", "Feature B", "draft", "active", design_doc_b
    )

    # ---- Phase 2: first upgrade triggers backfill ----
    command.upgrade(alembic_cfg, MIGRATION_REV)
    paths_after_first = _read_paths(db_engine, project_id)

    # ---- Phase 3: downgrade drops the column ----
    command.downgrade(alembic_cfg, PREV_REVISION)

    # ---- Phase 4: second upgrade re-backfills against same data ----
    command.upgrade(alembic_cfg, MIGRATION_REV)
    paths_after_second = _read_paths(db_engine, project_id)

    expected_a = extract_affected_files(design_doc_a)
    assert paths_after_first["I-00011"] == expected_a
    assert paths_after_second["I-00011"] == expected_a

    expected_b = extract_affected_files(design_doc_b)
    assert paths_after_first["I-00012"] == expected_b
    assert paths_after_second["I-00012"] == expected_b

    assert len(paths_after_first) == len(paths_after_second) == 2, (
        f"Row count mismatch: first={len(paths_after_first)}, second={len(paths_after_second)}"
    )


def test_no_duplicate_rows_after_double_upgrade(db_engine: Engine) -> None:
    """Running upgrade twice in a row (no downgrade between) must be a no-op
    on the column shape and must not duplicate rows.
    """
    alembic_cfg = _alembic_config(db_engine)
    project_id = "f76-dup-test"

    command.upgrade(alembic_cfg, PREV_REVISION)
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO projects (id, display_name, repo_root, config) "
                "VALUES (:pid, 'F-00076 Dup', '/repos/f76-dup-test', '{}')"
            ),
            {"pid": project_id},
        )

    command.upgrade(alembic_cfg, MIGRATION_REV)
    # Second upgrade is a no-op (already at target revision); alembic will exit
    # cleanly without re-running the migration script. We assert no duplicate
    # project rows after the round-trip.
    command.upgrade(alembic_cfg, MIGRATION_REV)

    with db_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM projects WHERE id = :pid"),
            {"pid": project_id},
        ).scalar_one()
    assert count == 1, f"Duplicate project rows: {count}"
