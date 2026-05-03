"""Unit tests for WorkItem.impacted_paths column (F-00076).

These tests verify SQLAlchemy model behavior only (no testcontainer needed).
The db_session fixture provides a real PostgreSQL session so we can
exercise the NOT NULL constraint and defaults.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from orch.db.models import (
    FTS_FUNCTION_SQL,
    FTS_TRIGGER_SQL,
    Base,
    Project,
    WorkItem,
    WorkItemType,
)


@pytest.fixture(scope="session")
def pg_engine():
    """Start a PostgreSQL container for this test module.

    We use a session-scoped container so the engine is reused across tests.
    FTS triggers are installed after create_all().
    """
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:15-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
        engine = create_engine(url, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            conn.execute(text(FTS_FUNCTION_SQL))
            conn.execute(text(FTS_TRIGGER_SQL))
            conn.commit()
        yield engine


@pytest.fixture
def db_session(pg_engine):
    """Each test gets a transactional session that rolls back after the test."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = factory()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_project(db_session) -> Project:
    """Insert a Project row inside the current transaction."""
    project = Project(
        id="test-proj-f76",
        display_name="Test Project F-00076",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


class TestWorkItemImpactedPathsDefault:
    """Test that the SQLAlchemy default of [] is applied correctly."""

    def test_impacted_paths_defaults_to_empty_list(self, db_session, test_project):
        """When no impacted_paths is specified the column defaults to [].

        SQLAlchemy maps the server_default='[]' JSONB default to an empty list.
        """
        item = WorkItem(
            project_id=test_project.id,
            id="I-00001",
            type=WorkItemType.Feature,
            title="Test item",
            status="draft",
            phase="active",
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(item)
        db_session.flush()

        db_session.expire(item)
        result = (
            db_session.query(WorkItem).filter_by(project_id=test_project.id, id="I-00001").first()
        )
        assert result is not None
        assert result.impacted_paths == []

    def test_impacted_paths_can_be_set_explicitly(self, db_session, test_project):
        """impacted_paths can be set to a list of glob strings and round-trips."""
        item = WorkItem(
            project_id=test_project.id,
            id="I-00002",
            type=WorkItemType.Feature,
            title="Test item with paths",
            status="draft",
            phase="active",
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=["orch/foo.py", "orch/bar/**/*.js"],
        )
        db_session.add(item)
        db_session.flush()

        db_session.expire(item)
        result = (
            db_session.query(WorkItem).filter_by(project_id=test_project.id, id="I-00002").first()
        )
        assert result is not None
        assert result.impacted_paths == ["orch/foo.py", "orch/bar/**/*.js"]

    def test_impacted_paths_not_null_constraint(self, db_session, test_project):
        """Inserting with impacted_paths=None raises IntegrityError (NOT NULL).

        Uses a raw SQL insert to bypass SQLAlchemy's Python-side defaults and
        verify the PostgreSQL NOT NULL constraint fires.
        """
        from sqlalchemy.exc import IntegrityError

        # Single-statement wrapper so pytest.raises can follow PT012
        def _try_insert_null() -> None:
            db_session.execute(
                text(
                    "INSERT INTO work_items "
                    "(project_id, id, type, title, status, phase, config, "
                    "depends_on, blocks, impacted_paths) "
                    "VALUES "
                    "(:pid, :iid, 'Feature', 'Null paths test', 'draft', 'active', "
                    "'{}'::jsonb, '{}'::text[], '{}'::text[], NULL)"
                ),
                {"pid": test_project.id, "iid": "I-00003"},
            )
            db_session.commit()

        with pytest.raises(IntegrityError):
            _try_insert_null()
