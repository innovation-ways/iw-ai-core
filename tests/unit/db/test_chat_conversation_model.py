"""Unit tests for ChatConversation ORM model (F-00077).

RED phase: tests verify the expected schema behavior before models exist.
These tests should FAIL until ChatConversation is added to models.py.
"""

from __future__ import annotations

from datetime import UTC

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
def test_project(db_session) -> Project:  # noqa: assertion-scanner
    """Insert a project row for use by other tests in this module."""
    project = Project(
        id="test-proj-f77",
        display_name="Test Project F-00077",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


class TestChatConversationDefaults:
    """Test ChatConversation column defaults."""

    def test_chat_conversation_default_archived_at_is_none(self, db_session, test_project):
        """Insert without specifying archived_at; assert NULL."""
        from orch.db.models import ChatConversation

        conv = ChatConversation(
            project_id=test_project.id,
            session_id="session-abc",
        )
        db_session.add(conv)
        db_session.flush()

        db_session.expire(conv)
        result = (
            db_session.query(ChatConversation)
            .filter_by(project_id=test_project.id, session_id="session-abc")
            .first()
        )
        assert result is not None
        assert result.archived_at is None

    def test_chat_conversation_default_context_level_is_architecture(
        self, db_session, test_project
    ):
        """Insert without specifying context_level; assert default 'architecture'."""
        from orch.db.models import ChatConversation

        conv = ChatConversation(
            project_id=test_project.id,
            session_id="session-abc",
        )
        db_session.add(conv)
        db_session.flush()

        db_session.expire(conv)
        result = (
            db_session.query(ChatConversation)
            .filter_by(project_id=test_project.id, session_id="session-abc")
            .first()
        )
        assert result is not None
        assert result.context_level == "architecture"


class TestChatConversationIndexes:
    """Test ChatConversation indexes."""

    def test_partial_index_excludes_archived(self, db_session, test_project):
        """Insert two rows, archive one, query the index-backed predicate.

        The partial index idx_chat_conversations_project_session_recent should
        exclude the archived row when querying WHERE archived_at IS NULL.
        """
        from datetime import datetime, timedelta

        from orch.db.models import ChatConversation

        # Insert two active conversations
        now = datetime.now(UTC)
        conv1 = ChatConversation(
            project_id=test_project.id,
            session_id="session-abc",
            last_active_at=now,
        )
        conv2 = ChatConversation(
            project_id=test_project.id,
            session_id="session-abc",
            last_active_at=now + timedelta(hours=1),
        )
        db_session.add(conv1)
        db_session.add(conv2)
        db_session.flush()

        # Archive the first one
        conv1.archived_at = now
        db_session.flush()

        # Query for active conversations (WHERE archived_at IS NULL)
        active = (
            db_session.query(ChatConversation)
            .filter(
                ChatConversation.project_id == test_project.id,
                ChatConversation.session_id == "session-abc",
                ChatConversation.archived_at.is_(None),
            )
            .order_by(ChatConversation.last_active_at.desc())
            .all()
        )

        # Should return only conv2 (the non-archived one)
        assert len(active) == 1
        assert active[0].id == conv2.id
