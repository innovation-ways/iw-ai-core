"""Integration tests for orch.db.alembic_guard — testcontainer roundtrip.

These tests spin up a real PostgreSQL container, run alembic migrations,
then selectively downgrade to verify the guard detects the mismatch.

We bypass the live-db guard by patching safe_migrate.current_revision and
list_pending_revisions to read directly from the testcontainer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from orch.db.alembic_guard import (
    DBBehindHeadError,
    assert_db_at_head,
    check_db_at_head,
)

if TYPE_CHECKING:
    from sqlalchemy import Engine


class FakeRevision:
    """Minimal fake for safe_migrate.Revision."""

    id: str

    def __init__(self, id_: str) -> None:
        self.id = id_


@pytest.fixture(scope="module")
def pg_container():
    """PostgreSQL 15 testcontainer, module-scoped."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def migrated_engine(pg_container):
    """SQLAlchemy engine connected to testcontainer, with alembic migrations run to head.

    Sets IW_CORE_DB_* env vars so alembic connects to the testcontainer, not the
    real platform DB. Env vars are scoped via MonkeyPatch.context() and restored
    on teardown.
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


@pytest.fixture
def db_session(migrated_engine: Engine):
    """Provide a transactional session that rolls back after each test."""
    conn = migrated_engine.connect()
    tx = conn.begin()
    factory = sessionmaker(bind=conn, autocommit=False, autoflush=False)
    session = factory()
    yield session
    session.close()
    tx.rollback()


def _get_head_rev(engine: Engine) -> str:
    """Return the current head revision by upgrading to head and reading alembic_version."""
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        return row[0] if row else ""


def _get_current_rev(engine: Engine) -> str:
    """Read the current alembic_version from the DB."""
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        return row[0] if row else ""


def _downgrade_by_one(engine: Engine) -> None:
    """Downgrade by one revision using specific target (not -1) per CLAUDE.md rule 4a.

    When the current head is a merge revision, ``rev.down_revision`` is a
    tuple of parent revision IDs and ``alembic.command.downgrade`` rejects
    non-string targets. Pick the first parent — alembic will walk both
    parents' lineages to put the database at that specific target, which
    is enough for the guard tests (they only need ``current_rev != head_rev``).
    """
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        pytest.skip("Cannot test downgrade with multiple heads")
    head = heads[0]
    rev = script.get_revision(head)
    down_rev: str | tuple[str, ...] | None = (
        rev.down_revision if rev and rev.down_revision else None
    )
    if down_rev is None:
        pytest.skip("Cannot downgrade further — already at base")
    if isinstance(down_rev, tuple):
        down_rev = down_rev[0]
    command.downgrade(cfg, down_rev)


def _run_alembic_upgrade_head(engine: Engine) -> None:
    """Run alembic upgrade head (for re-syncing after downgrade)."""
    cfg = Config()
    cfg.set_main_option("script_location", "orch/db/migrations")
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    command.upgrade(cfg, "head")


class TestGuardAtHead:
    def test_guard_passes_at_head(self, migrated_engine: Engine) -> None:  # noqa: assertion-scanner
        """assert_db_at_head() does not raise when DB is at head."""
        current_rev = _get_current_rev(migrated_engine)
        head_rev = _get_head_rev(migrated_engine)

        with (
            patch("orch.db.alembic_guard.current_revision", return_value=current_rev),
            patch("orch.db.alembic_guard._get_head_revisions", return_value=(head_rev, [])),
            patch("orch.db.alembic_guard.list_pending_revisions", return_value=[]),
        ):
            assert_db_at_head()  # must not raise


class TestGuardBehindHead:
    def test_guard_fails_when_behind_one_revision(self, migrated_engine: Engine) -> None:
        """DBBehindHeadError raised with head_rev and current_rev in message."""
        _run_alembic_upgrade_head(migrated_engine)

        head_rev = _get_head_rev(migrated_engine)

        _downgrade_by_one(migrated_engine)
        new_rev = _get_current_rev(migrated_engine)
        assert new_rev != head_rev

        with (
            patch("orch.db.alembic_guard.current_revision", return_value=new_rev),
            patch("orch.db.alembic_guard._get_head_revisions", return_value=(head_rev, [])),
            patch(
                "orch.db.alembic_guard.list_pending_revisions",
                return_value=[FakeRevision(new_rev)],
            ),
        ):
            with pytest.raises(DBBehindHeadError) as exc_info:
                assert_db_at_head()

            msg = str(exc_info.value)
            assert head_rev in msg, f"head_rev '{head_rev}' not in: {msg}"
            assert new_rev in msg, f"new_rev '{new_rev}' not in: {msg}"
            assert "make db-migrate" in msg, f"'make db-migrate' not in: {msg}"


class TestCheckDbAtHead:
    def test_check_db_at_head_ok_at_head(self, migrated_engine: Engine) -> None:
        """check_db_at_head() returns ok=True when at head."""
        current_rev = _get_current_rev(migrated_engine)
        head_rev = _get_head_rev(migrated_engine)

        with (
            patch("orch.db.alembic_guard.current_revision", return_value=current_rev),
            patch("orch.db.alembic_guard._get_head_revisions", return_value=(head_rev, [])),
            patch("orch.db.alembic_guard.list_pending_revisions", return_value=[]),
        ):
            status = check_db_at_head()
            assert status.ok is True
            assert status.current_rev == current_rev
            assert status.head_rev == head_rev
            assert status.pending == []
            assert status.multiple_heads == []

    def test_check_db_at_head_not_ok_when_behind(self, migrated_engine: Engine) -> None:
        """check_db_at_head() returns ok=False with pending revisions when behind."""
        _run_alembic_upgrade_head(migrated_engine)
        head_rev = _get_head_rev(migrated_engine)

        _downgrade_by_one(migrated_engine)
        new_rev = _get_current_rev(migrated_engine)

        with (
            patch("orch.db.alembic_guard.current_revision", return_value=new_rev),
            patch("orch.db.alembic_guard._get_head_revisions", return_value=(head_rev, [])),
            patch(
                "orch.db.alembic_guard.list_pending_revisions",
                return_value=[FakeRevision(new_rev)],
            ),
        ):
            status = check_db_at_head()
            assert status.ok is False
            assert status.head_rev == head_rev
            assert status.current_rev == new_rev
            assert new_rev in status.pending
