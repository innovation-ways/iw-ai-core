"""Revision-skew regression test — reproduces the I-00075 / I-00076 failure class.

Background
----------
An Alembic migration created by an agent in a worktree may be UNCOMMITTED when
the worktree's per-worktree DB is pg_dump-restored from production.  When the
daemon later tries to run `alembic upgrade head` in that worktree, Alembic finds
that the DB's alembic_version row points to a revision that does not exist in
the migration graph (because the revision file is uncommitted).  Alembic raises
a resolution error with the message:

    "Can't locate revision identified by '<rev>'"

The daemon's E2E compose stack (which depends on that DB) fails as a result.

This test reproduces that exact failure mode without modifying any production
code.  It is a PURE REGRESSION TEST — it asserts that the characteristic error
message appears when alembic_version points at a revision that does not exist
in the script directory.

Design
------
1. Spin a fresh testcontainer PostgreSQL.
2. Run `alembic upgrade head` to bring the DB to a known valid head.
3. Overwrite alembic_version with a BOGUS revision ID (one that is absent
   from the repo's migration graph).  This recreates the I-00075/I-00076
   state: "DB at rev X, but the checked-out migration files don't contain X".
4. Run `alembic upgrade head` again and assert that it raises
   CommandError / resolution error whose message contains
   "Can't locate revision identified by".

Note that stamping the DB at an *older but valid* revision would NOT reproduce
the bug — that is the normal "DB behind head" case that Alembic handles fine.
The key is that the revision ID must be completely absent from the graph.

CR constraint
-------------
No production code is touched.  This is a pure regression pin.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

if TYPE_CHECKING:
    from sqlalchemy import Engine


SCRIPT_LOCATION = "orch/db/migrations"


@pytest.fixture
def pg_container() -> PostgresContainer:
    """Dedicated postgres container for this module — not shared with conftest."""
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture
def migrated_engine(pg_container: PostgresContainer, monkeypatch: pytest.MonkeyPatch) -> Engine:
    """Bring the DB to alembic head, then hand back the engine."""
    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://"))
    monkeypatch.setenv("IW_CORE_DB_HOST", str(parsed.hostname))
    monkeypatch.setenv("IW_CORE_DB_PORT", str(parsed.port))
    monkeypatch.setenv("IW_CORE_DB_NAME", parsed.path.lstrip("/"))
    monkeypatch.setenv("IW_CORE_DB_USER", str(parsed.username))
    monkeypatch.setenv("IW_CORE_DB_PASSWORD", str(parsed.password))

    engine = create_engine(url, pool_pre_ping=True)

    cfg = Config()
    cfg.set_main_option("script_location", SCRIPT_LOCATION)
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    command.upgrade(cfg, "head")

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
    cfg.set_main_option("script_location", SCRIPT_LOCATION)
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    return cfg


def test_upgrade_head_fails_on_bogus_revision(migrated_engine: Engine) -> None:
    """When alembic_version points at a revision absent from the graph, upgrade head raises.

    Reproduces: I-00075, I-00076.
    Expected message: "Can't locate revision identified by '<rev>'"
    """
    cfg = _alembic_config(migrated_engine)

    # 1. Read the current (valid) head revision
    with migrated_engine.connect() as conn:
        valid_head = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert valid_head, "alembic_version must be populated after upgrade head"

    # 2. Stamp the DB at a BOGUS revision — one that definitely does not exist
    #    in the script directory.  A random UUID-prefixed string has extremely
    #    low probability of colliding with a real revision hash.
    bogus_revision = f"bogus{uuid.uuid4().hex[:12]}"

    with migrated_engine.connect() as conn:
        conn.execute(
            text("UPDATE alembic_version SET version_num = :rev"),
            {"rev": bogus_revision},
        )
        conn.commit()

    # 3. Attempting upgrade head should raise the characteristic resolution error.
    #    alembic.command.upgrade surfaces this as alembic.util.exc.CommandError
    #    with a message containing "Can't locate revision identified by".
    with pytest.raises(CommandError) as exc_info:
        command.upgrade(cfg, "head")

    exc_message = str(exc_info.value)
    assert exc_message.startswith("Can't locate revision identified by"), (
        f"Expected the message to start with 'Can't locate revision identified by', "
        f"but got: {exc_message!r}"
    )
    assert bogus_revision in exc_message, (
        f"Expected the bogus revision {bogus_revision!r} to appear in the error, "
        f"but got: {exc_message!r}"
    )


def test_upgrade_head_succeeds_with_valid_head(
    pg_container: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sanity check: a fresh DB with a legitimate (old) revision upgrades cleanly.

    This test confirms that the I-00075/I-00076 failure is specifically about
    ABSENT revisions, not about being "behind head" (which is fine).
    """
    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://"))
    monkeypatch.setenv("IW_CORE_DB_HOST", str(parsed.hostname))
    monkeypatch.setenv("IW_CORE_DB_PORT", str(parsed.port))
    monkeypatch.setenv("IW_CORE_DB_NAME", parsed.path.lstrip("/"))
    monkeypatch.setenv("IW_CORE_DB_USER", str(parsed.username))
    monkeypatch.setenv("IW_CORE_DB_PASSWORD", str(parsed.password))

    engine = create_engine(url, pool_pre_ping=True)

    try:
        cfg = _alembic_config(engine)

        # Upgrade only as far as a known OLD but VALID revision. The schema
        # genuinely IS at this revision afterwards — unlike rewriting
        # alembic_version under a head-schema DB, which would make the second
        # upgrade re-run already-applied CREATE TABLEs and fail spuriously.
        # A specific revision ID keeps the test stable as new migrations land.
        known_old = "824e6e6f34ee"
        command.upgrade(cfg, known_old)

        with engine.connect() as conn:
            stamped = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert stamped == known_old, (
            f"after upgrade to {known_old!r}, alembic_version should be {known_old!r}, "
            f"but it is {stamped!r}"
        )

        # Now "upgrade head" must succeed — the DB is behind head but the
        # revision EXISTS in the graph, so Alembic resolves it and walks
        # forward. This is the normal "DB behind head" case, NOT the skew bug.
        command.upgrade(cfg, "head")

        script_head = ScriptDirectory.from_config(cfg).get_current_head()
        with engine.connect() as conn:
            new_head = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert new_head != known_old, (
            f"upgrade head from the old valid revision {known_old!r} did not advance "
            f"alembic_version — it is still pinned at {new_head!r}"
        )
        assert new_head == script_head, (
            f"After upgrade head, alembic_version should be at the script head "
            f"{script_head!r}, but it is at {new_head!r}"
        )
    finally:
        engine.dispose()
