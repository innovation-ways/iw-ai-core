"""Integration test fixtures using testcontainers.

Tests MUST NOT load .env or connect to the live platform database.
All DB configuration comes exclusively from the testcontainer (random port).

Fixture scopes:
- pg_container: session — one PostgreSQL container per pytest run (~2s startup)
- db_engine: session — schema created once, reused across all tests
- db_session: function — each test runs in a transaction that is rolled back
- test_project: function — a Project row inside the db_session transaction
- cli_get_session: function — get_session factory that yields db_session
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    FUNCTIONAL_DOC_FTS_FUNCTION_SQL,
    FUNCTIONAL_DOC_FTS_TRIGGER_SQL,
    PROJECT_DOCS_FTS_FUNCTION_SQL,
    PROJECT_DOCS_FTS_TRIGGER_SQL,
    Base,
    Project,
)

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session


OSS_ENUMS_SQL = """\
DO $$
BEGIN
    DROP TYPE IF EXISTS ossscan_status CASCADE;
    CREATE TYPE ossscan_status AS ENUM ('pending', 'running', 'complete', 'error');

    DROP TYPE IF EXISTS ossscan_mode CASCADE;
    CREATE TYPE ossscan_mode AS ENUM ('scan');

    DROP TYPE IF EXISTS osspill_color CASCADE;
    CREATE TYPE osspill_color AS ENUM ('green', 'yellow', 'red', 'gray');

    DROP TYPE IF EXISTS ossfinding_severity CASCADE;
    CREATE TYPE ossfinding_severity AS ENUM ('MUST', 'SHOULD', 'MAY', 'INFO');

    DROP TYPE IF EXISTS ossfinding_status CASCADE;
    CREATE TYPE ossfinding_status AS ENUM ('pass_status', 'fail', 'skip', 'human_required');

    DROP TYPE IF EXISTS osstoolrun_status CASCADE;
    CREATE TYPE osstoolrun_status AS ENUM ('ok', 'failed', 'missing', 'skipped');

    DROP TYPE IF EXISTS project_oss_job_kind CASCADE;
    CREATE TYPE project_oss_job_kind AS ENUM ('scan', 'install', 'fix');

    DROP TYPE IF EXISTS project_oss_job_status CASCADE;
    CREATE TYPE project_oss_job_status AS ENUM (
        'queued', 'running', 'complete', 'error', 'cancelled'
    );
END$$;
"""

BATCH_ITEM_STATUS_SQL = """\
DO $$
BEGIN
    DROP TYPE IF EXISTS batch_item_status CASCADE;
    CREATE TYPE batch_item_status AS ENUM (
        'pending',
        'setting_up',
        'executing',
        'completed',
        'merging',
        'merged',
        'failed',
        'stalled',
        'skipped',
        'merge_failed',
        'migration_invalid',
        'migration_rolled_back',
        'migration_rebase_failed',
        'setup_failed'
    );
END$$;
"""


@pytest.fixture(scope="session")
def pg_container() -> Generator[PostgresContainer, None, None]:
    """Start a PostgreSQL 15 container for the entire test session.

    The container runs on a random Docker-assigned port — never touches
    the platform database on the port defined in .env.
    """
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_engine(pg_container: PostgresContainer) -> Engine:
    """Create a SQLAlchemy engine connected to the test container.

    Creates all tables via Base.metadata.create_all() and installs the
    FTS trigger (which Alembic would add but metadata.create_all() skips).
    """
    # testcontainers returns a psycopg2 URL; replace with psycopg (v3) driver
    url = pg_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+psycopg://"
    )
    engine = create_engine(url, pool_pre_ping=True)

    # Pre-create OSS ENUM types. SQLAlchemy's create_all() would also create
    # them (create_type=True on the ORM columns), but pre-creating with
    # DROP TYPE IF EXISTS … CASCADE guarantees a clean slate and avoids
    # collisions if a previous session left stale types behind.
    with engine.connect() as conn:
        conn.execute(text(OSS_ENUMS_SQL))
        conn.execute(text(BATCH_ITEM_STATUS_SQL))
        conn.commit()

    # create_all() is idempotent for existing ENUM types (checkfirst=True by default),
    # so the pre-created OSS enums above are reused rather than re-created.
    Base.metadata.create_all(engine)

    # Install the FTS trigger (DDL not captured by metadata.create_all)
    with engine.connect() as conn:
        conn.execute(text(FTS_FUNCTION_SQL))
        conn.execute(text(FTS_TRIGGER_SQL))
        conn.execute(text(PROJECT_DOCS_FTS_FUNCTION_SQL))
        conn.execute(text(PROJECT_DOCS_FTS_TRIGGER_SQL))
        conn.execute(text(FUNCTIONAL_DOC_FTS_FUNCTION_SQL))
        conn.execute(text(FUNCTIONAL_DOC_FTS_TRIGGER_SQL))
        conn.commit()

    return engine


@pytest.fixture
def _db_test_connection(db_engine: Engine):
    """Open a connection on db_engine and start an outer transaction.

    This connection is shared between db_session and db_session_factory so that
    rows flushed by the test fixture are visible to background services that
    look up sessions through the factory, and the whole transaction is rolled
    back on teardown so each test starts from a clean slate.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


@pytest.fixture
def db_session(_db_test_connection) -> Generator[Session, None, None]:
    """Provide a transactional DB session that rolls back after each test.

    Each test gets a clean database state without needing to truncate tables.
    The transaction wraps the entire test body and is rolled back on teardown.
    """
    session_factory = sessionmaker(bind=_db_test_connection, autocommit=False, autoflush=False)
    session: Session = session_factory()

    yield session

    session.close()


@pytest.fixture
def db_session_factory(_db_test_connection):
    """Return a sessionmaker that produces sessions sharing the test transaction.

    Sessions handed out by this factory bind to the same connection as
    db_session, so writes done in the test are visible to code that opens its
    own session via the factory (e.g. background poller threads). The outer
    transaction is rolled back at teardown via _db_test_connection.
    """
    return sessionmaker(bind=_db_test_connection, autocommit=False, autoflush=False)


@pytest.fixture
def test_project(db_session: Session) -> Project:
    """Insert a minimal Project row inside the current test transaction."""
    project = Project(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


@pytest.fixture
def cli_get_session(db_session: Session) -> Callable[[], contextmanager]:  # type: ignore[arg-type]
    """Return a get_session factory that yields the test db_session.

    Inject into CLI commands via ctx.obj['get_session'] so tests never
    touch orch.db.session (which would load .env and the live engine).
    """

    @contextmanager  # type: ignore[arg-type]
    def _get_session() -> Generator[Session, None, None]:
        yield db_session

    return _get_session  # type: ignore[return-value]


@pytest.fixture
def sample_worktree_path(tmp_path) -> Path:
    """Create a real directory that Path.exists() can confirm.

    Used by CLI retry-merge tests to verify the worktree existence check.
    """

    wt = tmp_path / "worktrees" / "F-99999"
    wt.mkdir(parents=True, exist_ok=True)
    # Create a minimal git worktree marker so the path looks real
    (wt / ".git").write_text("gitdir: /real/repo/.git/worktrees/F-99999\n")
    return wt
