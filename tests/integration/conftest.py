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

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

from orch.db.models import FTS_FUNCTION_SQL, FTS_TRIGGER_SQL, Base, Project

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from sqlalchemy import Engine
    from sqlalchemy.orm import Session


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

    # Create all tables defined in the ORM models
    Base.metadata.create_all(engine)

    # Install the FTS trigger (DDL not captured by metadata.create_all)
    with engine.connect() as conn:
        conn.execute(text(FTS_FUNCTION_SQL))
        conn.execute(text(FTS_TRIGGER_SQL))
        conn.commit()

    return engine


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Provide a transactional DB session that rolls back after each test.

    Each test gets a clean database state without needing to truncate tables.
    The transaction wraps the entire test body and is rolled back on teardown.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    # Bind the session to this connection so all operations share the transaction
    session_factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session: Session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


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
def cli_get_session(db_session: Session) -> Callable[[], contextmanager]:  # type: ignore[type-arg]
    """Return a get_session factory that yields the test db_session.

    Inject into CLI commands via ctx.obj['get_session'] so tests never
    touch orch.db.session (which would load .env and the live engine).
    """

    @contextmanager  # type: ignore[arg-type]
    def _get_session() -> Generator[Session, None, None]:
        yield db_session

    return _get_session  # type: ignore[return-value]
