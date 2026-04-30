"""Latest-3 migration roundtrip test — F-00072.

For each of the last 3 revisions (oldest → newest):
  downgrade base          — reset to empty (ensures clean state per parametrized case)
  upgrade <rev>           — apply up to this revision
  downgrade <parent_rev>  — step back one via EXPLICIT parent revision ID (rule 4a)
  upgrade head            — restore to head

Asserts each alembic.command call completes without raising.
After the final upgrade head, verifies the schema contains all Base.metadata tables.

Test reads alembic history at collection time — adding a new revision auto-shifts
the window with no edits to this file.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from testcontainers.postgres import PostgresContainer

from orch.db.models import Base

REPO_ROOT = Path(__file__).resolve().parents[2]


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _ordered_revisions() -> list[str]:
    """Return revision IDs topologically, oldest first."""
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    script = ScriptDirectory.from_config(cfg)
    revs = list(script.walk_revisions(base="base", head="heads"))
    revs.reverse()  # oldest → newest
    return [rev.revision for rev in revs]


def _latest_n(n: int = 3) -> list[str]:
    revs = _ordered_revisions()
    return revs[-n:] if len(revs) >= n else revs


def _parent_rev(revision: str) -> str | None:
    """Look up the explicit parent revision ID (rule 4a: never use -1)."""
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    script = ScriptDirectory.from_config(cfg)
    rev_obj = script.get_revision(revision)
    parent = rev_obj.down_revision if rev_obj else None
    if isinstance(parent, tuple):
        parent = parent[0]
    return parent  # None means base (no parent)


# Module-scoped container — one spin-up for all parametrized cases.
# (Mirroring test_iw_core_instance_migration.py pattern.)
@pytest.fixture(scope="module")
def roundtrip_pg():
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def roundtrip_db_url(roundtrip_pg: PostgresContainer) -> str:
    return roundtrip_pg.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )


@pytest.mark.integration
@pytest.mark.parametrize("revision", _latest_n(3), ids=lambda r: r[:8])
def test_migration_roundtrip(revision: str, roundtrip_db_url: str) -> None:
    """For each of the latest 3 revs: reset → upgrade(rev) → downgrade(parent) → upgrade head."""
    db_url = roundtrip_db_url
    parsed = urlparse(db_url.replace("postgresql+psycopg://", "postgresql://"))

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("IW_CORE_DB_HOST", str(parsed.hostname))
        mp.setenv("IW_CORE_DB_PORT", str(parsed.port))
        mp.setenv("IW_CORE_DB_NAME", parsed.path.lstrip("/"))
        mp.setenv("IW_CORE_DB_USER", str(parsed.username))
        mp.setenv("IW_CORE_DB_PASSWORD", str(parsed.password))

        alembic_cfg = _alembic_cfg(db_url)

        # 1. Reset to empty — ensures clean state regardless of prior test's final state
        command.downgrade(alembic_cfg, "base")

        # 2. Upgrade to target revision
        command.upgrade(alembic_cfg, revision)

        # 3. Downgrade to explicit parent (rule 4a: never use -1)
        parent = _parent_rev(revision)
        if parent is not None:
            command.downgrade(alembic_cfg, parent)
        # else: base revision has no parent; skip downgrade step

        # 4. Restore to head
        command.upgrade(alembic_cfg, "head")

    # 5. Verify final schema has all expected tables
    engine = create_engine(db_url, pool_pre_ping=True)
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())
    actual_tables.discard("alembic_version")
    expected_tables = set(Base.metadata.tables.keys())
    missing = expected_tables - actual_tables
    assert not missing, (
        f"After upgrade head, missing tables: {missing} (revision under test: {revision[:8]})"
    )
    engine.dispose()
