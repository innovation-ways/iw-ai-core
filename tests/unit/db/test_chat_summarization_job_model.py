"""Unit tests for ChatSummarizationJob ORM model (F-00077).

RED phase: tests verify the expected schema behavior before models exist.
These tests should FAIL until ChatSummarizationJob is added to models.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from orch.db.models import FTS_FUNCTION_SQL, FTS_TRIGGER_SQL, Base, Project


@pytest.fixture(scope="session")
def pg_engine():
    """Start a PostgreSQL container for this test module."""
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
        id="test-proj-f77",
        display_name="Test Project F-00077",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


class TestChatSummarizationJobDefaults:
    """Test ChatSummarizationJob column defaults."""

    def test_default_status_is_queued(self, db_session, test_project):
        """Insert without specifying status; assert default 'queued'."""
        from orch.db.models import ChatConversation, ChatSummarizationJob

        conv = ChatConversation(
            project_id=test_project.id,
            session_id="session-abc",
        )
        db_session.add(conv)
        db_session.flush()

        job = ChatSummarizationJob(
            conversation_id=conv.id,
            triggered_at=datetime.now(UTC),
        )
        db_session.add(job)
        db_session.flush()

        db_session.expire(job)
        result = db_session.query(ChatSummarizationJob).filter_by(conversation_id=conv.id).first()
        assert result is not None
        assert result.status == "queued"


class TestChatSummarizationJobConstraints:
    """Test ChatSummarizationJob unique partial index constraint.

    NOTE: The unique partial index (uq_chat_summarization_jobs_one_in_flight) is
    created by the alembic migration and enforced in the actual database.
    This unit test verifies the intent but requires the migration to be applied
    to actually enforce the constraint at the DB level. The real enforcement is
    verified by the integration test test_F00077_migration.py.
    """

    def test_unique_partial_in_flight_constraint(self, db_session, test_project):
        """At most one in-flight (queued/running) job per conversation.

        NOTE: This test verifies the SQLAlchemy model behavior but the DB-level
        unique partial index constraint enforcement is covered in the integration
        test suite
        (test_F00077_migration.py::test_unique_in_flight_constraint_blocks_concurrent_jobs).
        """
        pytest.skip(
            "Unique partial index enforcement requires the alembic migration. "
            "Verified in integration test test_F00077_migration.py::"
            "test_unique_in_flight_constraint_blocks_concurrent_jobs."
        )
