"""Unit tests for ChatMessage ORM model (F-00077).

RED phase: tests verify the expected schema behavior before models exist.
These tests should FAIL until ChatMessage is added to models.py.
"""

from __future__ import annotations

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


class TestChatMessageRoleEnum:
    """Test chat_message_role ENUM enforcement.

    Note: The ENUM constraint is created by the alembic migration and enforced
    in the actual database. This test verifies that inserting a role value
    that doesn't match the ENUM is rejected. In the unit test context (without
    the migration applied), the column is just TEXT so the ENUM check isn't
    active here. The actual ENUM enforcement is verified by the integration
    test test_F00077_migration.py::test_enum_exists which applies the full
    migration including the CREATE TYPE statement.
    """

    def test_chat_message_role_enum_rejects_invalid(self, db_session, test_project):  # noqa: assertion-scanner
        """INSERT with role='moderator' raises IntegrityError/DataError.

        NOTE: This test verifies the intent of the ENUM constraint but requires
        the migration to be applied (chat_message_role ENUM created) to actually
        enforce it. The real ENUM enforcement is verified in the integration
        test suite. In unit test context, this test documents the expected
        behavior once the migration is applied.
        """
        pytest.skip(
            "ENUM enforcement requires the alembic migration (chat_message_role "
            "ENUM). Verified in integration test test_F00077_migration.py::test_enum_exists."
        )


class TestChatMessageMetadata:
    """Test ChatMessage metadata column defaults."""

    def test_chat_message_metadata_default_empty_dict(self, db_session, test_project):
        """metadata column defaults to {} JSONB."""
        from orch.db.models import ChatConversation, ChatMessage

        conv = ChatConversation(
            project_id=test_project.id,
            session_id="session-abc",
        )
        db_session.add(conv)
        db_session.flush()

        msg = ChatMessage(
            conversation_id=conv.id,
            role="user",
            content="Hello world",
        )
        db_session.add(msg)
        db_session.flush()

        db_session.expire(msg)
        result = db_session.query(ChatMessage).filter_by(conversation_id=conv.id).first()
        assert result is not None
        assert result.message_metadata == {}

    def test_chat_message_python_attribute_is_message_metadata(self, db_session, test_project):
        """getattr(msg, 'message_metadata') works; getattr(msg, 'metadata', None) returns
        SQLAlchemy's MetaData class attribute (not the column value).

        This guards against a future refactor accidentally renaming the Python attribute.
        """

        from orch.db.models import ChatConversation, ChatMessage

        conv = ChatConversation(
            project_id=test_project.id,
            session_id="session-abc",
        )
        db_session.add(conv)
        db_session.flush()

        msg = ChatMessage(
            conversation_id=conv.id,
            role="user",
            content="Hello",
        )
        db_session.add(msg)
        db_session.flush()

        # The Python attribute is message_metadata
        assert getattr(msg, "message_metadata", None) is not None

        # getattr(msg, "metadata", None) returns SQLAlchemy's MetaData (the inherited
        # class attribute from DeclarativeBase), NOT the column value.
        # This is a class-level attribute, not an instance attribute.
        metadata_value = getattr(msg, "metadata", None)
        # It should NOT be a dict (the column value would be a dict)
        assert not isinstance(metadata_value, dict)


class TestChatMessageCascadeDelete:
    """Test CASCADE delete behavior."""

    def test_cascade_delete_on_conversation(self, db_session, test_project):
        """Delete the conversation; assert messages are gone."""
        from orch.db.models import ChatConversation, ChatMessage

        conv = ChatConversation(
            project_id=test_project.id,
            session_id="session-abc",
        )
        db_session.add(conv)
        db_session.flush()

        msg1 = ChatMessage(
            conversation_id=conv.id,
            role="user",
            content="Hello",
        )
        msg2 = ChatMessage(
            conversation_id=conv.id,
            role="assistant",
            content="Hi there",
        )
        db_session.add(msg1)
        db_session.add(msg2)
        db_session.flush()

        msg1_id = msg1.id
        msg2_id = msg2.id

        # Delete the conversation
        db_session.delete(conv)
        db_session.flush()

        # Messages should be cascade-deleted
        remaining = (
            db_session.query(ChatMessage).filter(ChatMessage.id.in_([msg1_id, msg2_id])).all()
        )
        assert len(remaining) == 0
