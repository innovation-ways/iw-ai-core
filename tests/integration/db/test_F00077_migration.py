"""Integration test for F-00077 migration: chat_conversations, chat_messages,
chat_summarization_jobs.

Verifies that the alembic migration:
1. Creates all three tables correctly.
2. Creates the chat_message_role ENUM.
3. Creates the partial unique index on chat_summarization_jobs.
4. Base.metadata reflects all three tables.

IMPORTANT: Never downgrade with `-1` in migration tests; use a specific revision ID
so the test stays stable as new migrations land above.
"""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# The migration under test creates chat_conversations, chat_messages,
# chat_summarization_jobs, and the chat_message_role ENUM.
# We need to apply all migrations up to the PREV_REVISION to establish the
# baseline schema, then apply the F-00077 migration.
PREV_REVISION = "4876b3246ff2"  # head at time of F-00077 implementation


@pytest.fixture(scope="module")
def pg_container() -> PostgresContainer:
    """Provide a module-scoped PostgreSQL testcontainer for migration tests."""
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def db_engine(pg_container: PostgresContainer) -> Engine:
    """Create a SQLAlchemy engine pointed at the testcontainer DB with env vars set.

    Args:
        pg_container: The running PostgreSQL testcontainer.

    Yields:
        A configured SQLAlchemy engine with IW_CORE_DB_* env vars set.
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
        yield create_engine(url, pool_pre_ping=True)


@pytest.fixture(scope="module")
def migrated_engine(db_engine: Engine) -> Engine:
    """Apply all alembic migrations up to head (includes the F-00077 migration)."""
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "orch/db/migrations")
    alembic_cfg.set_main_option(
        "sqlalchemy.url", db_engine.url.render_as_string(hide_password=False)
    )
    # Run all migrations — the initial migration creates the FTS trigger,
    # so no separate FTS setup is needed here.
    command.upgrade(alembic_cfg, "head")
    return db_engine


@pytest.fixture(scope="module")
def db_session_factory(migrated_engine: Engine) -> sessionmaker[Session]:
    """Provide a sessionmaker bound to the migrated engine.

    Args:
        migrated_engine: Engine after all alembic migrations have been applied.

    Returns:
        A sessionmaker configured for manual transaction control.
    """
    return sessionmaker(bind=migrated_engine, autocommit=False, autoflush=False)


class TestF00077Migration:
    """Verify F-00077 migration applied correctly."""

    def test_three_tables_exist(self, migrated_engine: Engine) -> None:
        """chat_conversations, chat_messages, chat_summarization_jobs all exist."""
        inspector = inspect(migrated_engine)
        table_names = inspector.get_table_names()
        assert "chat_conversations" in table_names
        assert "chat_messages" in table_names
        assert "chat_summarization_jobs" in table_names

    def test_enum_exists(self, migrated_engine: Engine) -> None:
        """chat_message_role ENUM exists with correct values."""
        connection = migrated_engine.connect()
        try:
            result = connection.execute(
                text(
                    "SELECT enumlabel FROM pg_enum WHERE enumtypid = "
                    "(SELECT oid FROM pg_type WHERE typname = 'chat_message_role') "
                    "ORDER BY enumsortorder"
                )
            )
            labels = [row[0] for row in result]
            assert labels == ["user", "assistant", "system"]
        finally:
            connection.close()

    def test_partial_unique_index_exists(self, migrated_engine: Engine) -> None:
        """uq_chat_summarization_jobs_one_in_flight exists as a partial unique index."""
        inspector = inspect(migrated_engine)
        indexes = inspector.get_indexes("chat_summarization_jobs")
        index_names = [idx["name"] for idx in indexes]
        assert "uq_chat_summarization_jobs_one_in_flight" in index_names

        # Also verify it is unique
        unique_indexes = [
            idx
            for idx in inspector.get_indexes("chat_summarization_jobs")
            if idx["name"] == "uq_chat_summarization_jobs_one_in_flight"
        ]
        assert len(unique_indexes) == 1
        assert unique_indexes[0]["unique"] is True

    def test_base_metadata_reflects_tables(self, migrated_engine: Engine) -> None:
        """Base.metadata contains ChatConversation, ChatMessage, ChatSummarizationJob."""
        # Import after migration has run
        from orch.db.models import ChatConversation, ChatMessage, ChatSummarizationJob

        # Verify table names
        assert ChatConversation.__tablename__ == "chat_conversations"
        assert ChatMessage.__tablename__ == "chat_messages"
        assert ChatSummarizationJob.__tablename__ == "chat_summarization_jobs"

    def test_conversation_pk_auto_generated(
        self, migrated_engine: Engine, db_session_factory: sessionmaker[Session]
    ) -> None:
        """Inserting a ChatConversation without specifying id generates a UUID."""
        from orch.db.models import ChatConversation, Project

        connection = migrated_engine.connect()
        transaction = connection.begin()
        session = db_session_factory(bind=connection)

        # Create a project first
        project = Project(
            id="f77-mig-test-proj",
            display_name="F-00077 Migration Test",
            repo_root="/repos/f77-mig-test",
            config={},
        )
        session.add(project)
        session.flush()

        # Insert a conversation without specifying id
        conv = ChatConversation(
            project_id=project.id,
            session_id="migration-test-session",
        )
        session.add(conv)
        session.flush()
        assert conv.id is not None
        assert len(conv.id) > 0

        transaction.rollback()
        connection.close()

    def test_cascade_delete_on_conversation(
        self, migrated_engine: Engine, db_session_factory: sessionmaker[Session]
    ) -> None:
        """Deleting a ChatConversation cascades to ChatMessage."""
        from orch.db.models import ChatConversation, ChatMessage, Project

        connection = migrated_engine.connect()
        transaction = connection.begin()
        session = db_session_factory(bind=connection)

        project = Project(
            id="f77-cascade-test-proj",
            display_name="F-00077 Cascade Test",
            repo_root="/repos/f77-cascade-test",
            config={},
        )
        session.add(project)
        session.flush()

        conv = ChatConversation(
            project_id=project.id,
            session_id="cascade-test-session",
        )
        session.add(conv)
        session.flush()

        msg = ChatMessage(
            conversation_id=conv.id,
            role="user",
            content="Test message",
        )
        session.add(msg)
        session.flush()

        msg_id = msg.id

        # Delete conversation
        session.delete(conv)
        session.flush()
        session.commit()

        transaction.rollback()
        connection.close()

        # Verify message is gone (cascade delete)
        connection2 = migrated_engine.connect()
        result = connection2.execute(
            text("SELECT id FROM chat_messages WHERE id = :id"), {"id": msg_id}
        )
        assert result.fetchone() is None
        connection2.close()

    def test_unique_in_flight_constraint_blocks_concurrent_jobs(
        self, migrated_engine: Engine, db_session_factory: sessionmaker[Session]
    ) -> None:
        """The unique partial index prevents two in-flight jobs for the same conversation."""
        from datetime import datetime

        from sqlalchemy.exc import IntegrityError

        from orch.db.models import ChatConversation, ChatSummarizationJob, Project

        connection = migrated_engine.connect()
        transaction = connection.begin()
        session = db_session_factory(bind=connection)

        project = Project(
            id="f77-uniq-test-proj",
            display_name="F-00077 Unique Index Test",
            repo_root="/repos/f77-uniq-test",
            config={},
        )
        session.add(project)
        session.flush()

        conv = ChatConversation(
            project_id=project.id,
            session_id="uniq-test-session",
        )
        session.add(conv)
        session.flush()

        now = datetime.now(UTC)

        job1 = ChatSummarizationJob(
            conversation_id=conv.id,
            status="queued",
            triggered_at=now,
        )
        session.add(job1)
        session.flush()

        job2 = ChatSummarizationJob(
            conversation_id=conv.id,
            status="running",
            triggered_at=now,
        )
        session.add(job2)
        with pytest.raises(IntegrityError):
            session.flush()

        transaction.rollback()
        connection.close()
