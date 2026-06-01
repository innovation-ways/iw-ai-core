"""TDD RED: test test_health_snapshots round-trip before model+migration exist.

This test lives under ``tests/integration/data_layer/`` per the CR-00086
migration-check QV gate (S02). It verifies that:
  1. The table can be upgraded from an empty DB via alembic.
  2. ``Base.metadata.create_all()`` produces the same schema (drift check).
  3. A ``TestHealthSnapshot`` row can be inserted and read back.
  4. The ``(project_id, metric, ts DESC)`` index is present.
  5. ``downgrade`` + re-``upgrade`` is clean.

The test is designed to FAIL (NoSuchTableError) in the RED phase before the
model and migration are added, confirming the TDD cycle starts from red.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

if TYPE_CHECKING:
    from sqlalchemy import Engine


_SCRIPT_LOCATION = "orch/db/migrations"


@pytest.fixture(scope="module")
def pg_container() -> PostgresContainer:
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


def _sa_url(container: PostgresContainer, dbname: str) -> str:
    base = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
    parsed = urlparse(base.replace("postgresql+psycopg://", "postgresql://"))
    return (
        f"postgresql+psycopg://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port}/{dbname}"
    )


def _bootstrap_engine(container: PostgresContainer) -> Engine:
    url = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
    return create_engine(url, isolation_level="AUTOCOMMIT")


def _fresh_db(container: PostgresContainer, dbname: str) -> Engine:
    eng = _bootstrap_engine(container)
    with eng.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{dbname}"'))
        conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    eng.dispose()
    return create_engine(_sa_url(container, dbname), pool_pre_ping=True)


def _alembic_cfg(engine: Engine) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", _SCRIPT_LOCATION)
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    return cfg


def _set_env(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> None:
    parsed = urlparse(
        engine.url.render_as_string(hide_password=False).replace(
            "postgresql+psycopg://", "postgresql://"
        )
    )
    for key, val in [
        ("IW_CORE_DB_HOST", str(parsed.hostname)),
        ("IW_CORE_DB_PORT", str(parsed.port)),
        ("IW_CORE_DB_NAME", parsed.path.lstrip("/")),
        ("IW_CORE_DB_USER", str(parsed.username)),
        ("IW_CORE_DB_PASSWORD", str(parsed.password)),
    ]:
        monkeypatch.setenv(key, val)


@pytest.mark.usefixtures("pg_container")
def test_health_snapshots_table_upgrades_cleanly(
    pg_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """alembic upgrade head must create test_health_snapshots without errors."""
    engine = _fresh_db(pg_container, "ths_upgrade")
    _set_env(monkeypatch, engine)
    command.upgrade(_alembic_cfg(engine), "head")

    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT tablename FROM pg_tables WHERE tablename = 'test_health_snapshots'")
        ).fetchone(), "test_health_snapshots table not found after upgrade head"

        col_rows = conn.execute(
            text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'test_health_snapshots' ORDER BY ordinal_position"
            )
        ).fetchall()
        col_names = {r[0] for r in col_rows}
        assert "id" in col_names
        assert "project_id" in col_names
        assert "ts" in col_names
        assert "metric" in col_names
        assert "value" in col_names
        assert "meta" in col_names

    engine.dispose()


@pytest.mark.usefixtures("pg_container")
def test_health_snapshots_model_round_trip(
    pg_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TestHealthSnapshot model can insert and read back a row in the testcontainer DB."""
    engine = _fresh_db(pg_container, "ths_model_rt")
    _set_env(monkeypatch, engine)
    command.upgrade(_alembic_cfg(engine), "head")

    from orch.db.models import Base, TestHealthSnapshot  # noqa: PLC0415

    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker

    session_maker = sessionmaker(bind=engine)
    session = session_maker()

    # Insert a project row (required FK)
    session.execute(
        text(
            "INSERT INTO projects (id, display_name, repo_root, config) "
            "VALUES ('test-proj', 'Test', '/tmp', '{}')"
        )
    )

    # Insert a TestHealthSnapshot row
    snapshot = TestHealthSnapshot(
        project_id="test-proj",
        metric="mutation_score",
        value=87.5,
        meta={"commit_sha": "abc1234", "run_id": "run-001"},
    )
    session.add(snapshot)
    session.commit()

    # Read it back
    row = (
        session.query(TestHealthSnapshot)
        .filter_by(project_id="test-proj", metric="mutation_score")
        .first()
    )
    assert row is not None, "TestHealthSnapshot row not found after insert"
    assert row.value == 87.5
    assert row.meta["commit_sha"] == "abc1234"

    session.close()
    engine.dispose()


@pytest.mark.usefixtures("pg_container")
def test_health_snapshots_index_exists(
    pg_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The composite index on (project_id, metric, ts DESC) must exist after upgrade."""
    engine = _fresh_db(pg_container, "ths_index")
    _set_env(monkeypatch, engine)
    command.upgrade(_alembic_cfg(engine), "head")

    with engine.connect() as conn:
        indexes = conn.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'test_health_snapshots'")
        ).fetchall()
        index_names = {r[0] for r in indexes}
        assert any(
            "test_health_snapshots" in n and "project_metric_ts" in n for n in index_names
        ), f"Composite index not found. Indexes: {sorted(index_names)}"

    engine.dispose()


@pytest.mark.usefixtures("pg_container")
def test_health_snapshots_downgrade_then_upgrade(
    pg_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """downgrade past ea7f8a0d065f must drop the table; re-upgrade must recreate it cleanly."""
    engine = _fresh_db(pg_container, "ths_down_up")
    _set_env(monkeypatch, engine)
    cfg = _alembic_cfg(engine)

    command.upgrade(cfg, "head")
    # Downgrade specifically below CR-00086's migration so this test remains
    # stable when newer unrelated migrations are added after it.
    command.downgrade(cfg, "a3f1c9e2b7d4")

    with engine.connect() as conn:
        leftovers = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename = 'test_health_snapshots'"
            )
        ).fetchone()
        assert leftovers is None, "test_health_snapshots still exists after downgrade -1"

    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        version_num = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version_num, "alembic_version empty after re-upgrade"
        assert conn.execute(
            text("SELECT tablename FROM pg_tables WHERE tablename = 'test_health_snapshots'")
        ).fetchone(), "test_health_snapshots not recreated after re-upgrade"

    engine.dispose()
