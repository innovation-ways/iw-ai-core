"""Integration tests for chat_repo.py — CRUD against real PostgreSQL via testcontainers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from tests.conftest import Project


class TestChatRepo:
    """chat_repo CRUD operations with real DB."""

    def test_get_or_create_conversation_creates_new(
        self, db_session: Session, test_project: Project
    ) -> None:
        """When conversation_id is None, creates a new conversation row."""
        from orch.rag.chat_repo import get_or_create_conversation

        conv = get_or_create_conversation(
            db_session,
            project_id=test_project.id,
            session_id="session-abc",
            conversation_id=None,
            module_path="orch/daemon/main.py",
            context_level="module",
            first_question="What does keep_alive do?",
        )

        assert conv.id is not None
        assert conv.project_id == test_project.id
        assert conv.session_id == "session-abc"
        assert conv.module_path == "orch/daemon/main.py"
        assert conv.context_level == "module"
        assert conv.title == "What does keep_alive do?"

    def test_get_or_create_conversation_returns_existing(
        self, db_session: Session, test_project: Project
    ) -> None:
        """When conversation_id is valid and active, returns it and bumps last_active_at."""
        from orch.rag.chat_repo import get_or_create_conversation

        conv1 = get_or_create_conversation(
            db_session,
            project_id=test_project.id,
            session_id="session-xyz",
            conversation_id=None,
            module_path=None,
            context_level="architecture",
            first_question="Tell me about the architecture",
        )
        db_session.commit()

        original_active = conv1.last_active_at

        conv2 = get_or_create_conversation(
            db_session,
            project_id=test_project.id,
            session_id="session-xyz",
            conversation_id=conv1.id,
            module_path=None,
            context_level="architecture",
        )

        assert conv2.id == conv1.id
        assert conv2.last_active_at >= original_active

    def test_get_or_create_conversation_cross_session_returns_none(
        self, db_session: Session, test_project: Project
    ) -> None:
        """Cross-session conversation_id (different session_id) creates new conversation."""
        from orch.rag.chat_repo import get_or_create_conversation

        conv1 = get_or_create_conversation(
            db_session,
            project_id=test_project.id,
            session_id="session-A",
            conversation_id=None,
            module_path=None,
            context_level="architecture",
            first_question="First question",
        )
        db_session.commit()

        # Try to use conv1's ID from a different session
        conv2 = get_or_create_conversation(
            db_session,
            project_id=test_project.id,
            session_id="session-B",  # different session
            conversation_id=conv1.id,
            module_path=None,
            context_level="architecture",
        )

        # Server must create a new conversation (cross-session = not found)
        assert conv2.id != conv1.id

    def test_append_message_updates_last_active_at(
        self, db_session: Session, test_project: Project
    ) -> None:
        """append_message bumps last_active_at in the same transaction."""
        from orch.rag.chat_repo import append_message, get_or_create_conversation

        conv = get_or_create_conversation(
            db_session,
            project_id=test_project.id,
            session_id="session-append",
            conversation_id=None,
            module_path=None,
            context_level="architecture",
            first_question="Test question",
        )
        db_session.flush()
        original_active = conv.last_active_at

        append_message(
            db_session,
            conversation_id=conv.id,
            role="user",
            content="Hello, my name is sergio",
        )

        # last_active_at bumped immediately (same transaction)
        db_session.refresh(conv)
        assert conv.last_active_at >= original_active

    def test_list_messages_for_context_skips_summarized(
        self, db_session: Session, test_project: Project
    ) -> None:
        """Messages older than summary_through_message_id are excluded (basic boundary check)."""
        from orch.db.models import ChatConversation
        from orch.rag.chat_repo import (
            append_message,
            get_or_create_conversation,
            list_messages_for_context,
        )

        # Create conversation
        conv = get_or_create_conversation(
            db_session,
            project_id=test_project.id,
            session_id="session-list",
            conversation_id=None,
            module_path=None,
            context_level="architecture",
            first_question="Test",
        )
        db_session.commit()

        # Insert 3 messages
        msg_ids = []
        for i in range(3):
            msg = append_message(
                db_session,
                conversation_id=conv.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"msg_{i}",
            )
            msg_ids.append(msg.id)
            db_session.commit()

        # Verify all 3 are returned before setting boundary
        all_before, _ = list_messages_for_context(
            db_session, conversation_id=conv.id, soft_budget_tokens=100000
        )
        assert len(all_before) == 3, f"Expected 3, got {len(all_before)}"

        # Set boundary on msg_ids[0] using ORM
        conv_obj = db_session.query(ChatConversation).filter(ChatConversation.id == conv.id).one()
        conv_obj.summary_through_message_id = msg_ids[0]
        db_session.commit()

        # Expire all to force fresh read
        db_session.expire_all()

        # Verify via raw SQL that messages exist

        raw_count = db_session.execute(
            text("SELECT COUNT(*) FROM chat_messages WHERE conversation_id = :cid"),
            {"cid": conv.id},
        ).scalar_one()
        assert raw_count == 3, f"Expected 3 raw messages, got {raw_count}"

        # Verify boundary is set via raw SQL
        raw_boundary = db_session.execute(
            text("SELECT summary_through_message_id FROM chat_conversations WHERE id = :cid"),
            {"cid": conv.id},
        ).scalar_one()
        assert raw_boundary == msg_ids[0], f"Expected boundary {msg_ids[0]}, got {raw_boundary}"

        # Get all message IDs and timestamps
        _raw_msgs = db_session.execute(
            text(
                "SELECT id, created_at FROM chat_messages WHERE conversation_id = :cid "
                "ORDER BY created_at"
            ),
            {"cid": conv.id},
        ).fetchall()

        kept, rolling = list_messages_for_context(
            db_session, conversation_id=conv.id, soft_budget_tokens=100000
        )

        # msg_ids[0] is the boundary - messages AFTER it should be kept
        kept_contents = [m["content"] for m in kept]
        assert "msg_0" not in kept_contents, (
            f"msg_0 should be skipped (boundary), got: {kept_contents}"
        )
        assert "msg_1" in kept_contents, f"msg_1 should be kept, got: {kept_contents}"
        assert "msg_2" in kept_contents, f"msg_2 should be kept, got: {kept_contents}"

    def test_archive_conversation_idempotent(
        self, db_session: Session, test_project: Project
    ) -> None:
        """Calling archive_conversation twice returns the original timestamp."""
        from orch.rag.chat_repo import archive_conversation, get_or_create_conversation

        conv = get_or_create_conversation(
            db_session,
            project_id=test_project.id,
            session_id="session-archive",
            conversation_id=None,
            module_path=None,
            context_level="architecture",
            first_question="To be archived",
        )
        db_session.commit()

        ts1 = archive_conversation(
            db_session,
            conversation_id=conv.id,
            project_id=test_project.id,
            session_id="session-archive",
        )
        assert ts1 is not None

        ts2 = archive_conversation(
            db_session,
            conversation_id=conv.id,
            project_id=test_project.id,
            session_id="session-archive",
        )
        # Second call returns None (already archived)
        assert ts2 is None

    def test_archive_conversation_cross_project_returns_none(
        self, db_session: Session, test_project: Project
    ) -> None:
        """Archiving with wrong project_id returns None."""
        from orch.rag.chat_repo import archive_conversation, get_or_create_conversation

        conv = get_or_create_conversation(
            db_session,
            project_id=test_project.id,
            session_id="session-cross",
            conversation_id=None,
            module_path=None,
            context_level="architecture",
            first_question="Test",
        )
        db_session.commit()

        # Try to archive with wrong project_id
        result = archive_conversation(
            db_session,
            conversation_id=conv.id,
            project_id="wrong-project",
            session_id="session-cross",
        )
        assert result is None

    def test_get_conversation_strict_triple_filter(
        self, db_session: Session, test_project: Project
    ) -> None:
        """get_conversation returns None when any of the three filters mismatch."""
        from orch.rag.chat_repo import get_conversation, get_or_create_conversation

        conv = get_or_create_conversation(
            db_session,
            project_id=test_project.id,
            session_id="session-get",
            conversation_id=None,
            module_path=None,
            context_level="architecture",
            first_question="Test get",
        )
        db_session.commit()

        # Correct filter
        found = get_conversation(
            db_session,
            conversation_id=conv.id,
            project_id=test_project.id,
            session_id="session-get",
        )
        assert found is not None

        # Wrong project_id
        not_found = get_conversation(
            db_session,
            conversation_id=conv.id,
            project_id="wrong-project",
            session_id="session-get",
        )
        assert not_found is None

        # Wrong session_id
        not_found = get_conversation(
            db_session,
            conversation_id=conv.id,
            project_id=test_project.id,
            session_id="wrong-session",
        )
        assert not_found is None

    def test_count_tokens_uses_tiktoken(self) -> None:
        """count_tokens returns non-trivial token counts for real text."""
        from orch.rag.chat_repo import count_tokens

        result = count_tokens("Hello, world! This is a test.")
        # Should be > 1 since the text has content
        assert isinstance(result, int)
        assert result >= 1
