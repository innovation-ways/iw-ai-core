"""Integration test: PostgreSQL batch_item_status enum must match Python BatchItemStatus.

Reproduction test for I-00042 — PG enum was missing migration_invalid and
migration_rolled_back, causing InvalidTextRepresentation on every daemon restart.

WHY THIS FILE DOES NOT USE THE SHARED db_engine FIXTURE
--------------------------------------------------------
The shared conftest.py db_engine builds the schema via Base.metadata.create_all().
That call creates the PG batch_item_status enum DIRECTLY from the Python
BatchItemStatus declaration, so the enum always has all 13 labels regardless of
whether any migration exists.  The real production bug occurred because the live
DB was migrated incrementally via Alembic and the I-00042 labels were never added
by a migration.  To catch that class of drift, the test must exercise the
Alembic-built schema — i.e. start from an empty DB and run alembic upgrade head.
Using the shared db_engine would make the test pass both before and after the fix,
rendering it worthless as a regression guard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

from orch.db.models import BatchItemStatus

if TYPE_CHECKING:
    from sqlalchemy import Engine


@pytest.fixture(scope="module")
def pg_container() -> PostgresContainer:
    """Spin up a private PostgreSQL container for this module only.

    This is intentionally separate from the session-scoped pg_container in
    conftest.py — that fixture feeds the shared db_engine which uses
    create_all() rather than Alembic migrations.
    """
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def migrated_engine(pg_container: PostgresContainer) -> Engine:
    """Return an engine backed by a fresh DB that has been brought up to HEAD
    entirely via Alembic migrations (not Base.metadata.create_all()).

    The env vars are patched inside a MonkeyPatch context so that Alembic's
    env.py can resolve the DB URL without touching the live .env credentials.
    The context is torn down at the end of the module scope so the test
    container credentials do not leak to subsequent test modules.
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
        cfg = Config()
        cfg.set_main_option("script_location", "orch/db/migrations")
        cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
        command.upgrade(cfg, "head")
        yield engine


def test_pg_batch_item_status_enum_includes_i_00042_labels(migrated_engine: Engine) -> None:
    """After alembic upgrade head, batch_item_status PG enum must contain
    every value declared in Python BatchItemStatus, including the two labels
    added by the I-00042 migration (migration_invalid, migration_rolled_back).

    Checks are one-directional: every Python value must be in PG.  PG may have
    extra dormant orphan labels (e.g. awaiting_review, discarded from CR-00019)
    without causing a failure — equality is NOT asserted.

    This test is:
    - RED when the I-00042 migration file is absent (alembic upgrade head
      stops at the previous revision and the two labels are never added).
    - GREEN when bd4ed52cad71 is on disk and alembic upgrade head applies it.
    """
    with migrated_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT enumlabel FROM pg_enum "
                "WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname='batch_item_status') "
                "ORDER BY enumsortorder"
            )
        ).fetchall()
    pg_labels = {r[0] for r in rows}

    # Semantic checks — assert the specific values that were missing before I-00042
    assert "migration_invalid" in pg_labels
    assert "migration_rolled_back" in pg_labels

    # Drift-prevention: every Python value must be present in the PG enum.
    # Any future BatchItemStatus addition without a matching ALTER TYPE migration
    # will fail here and surface in CI.
    missing = {e.value for e in BatchItemStatus} - pg_labels
    assert not missing, f"Python BatchItemStatus values missing from PG enum: {sorted(missing)}"
