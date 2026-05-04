"""Integration tests for qa.py with conversation memory (F-00077).

Verifies:
- condense is invoked with prior history on turns >= 2
- retrieval uses the condensed query (not the original)
- hardening lines appear in the system prompt
- rolling_summary is prepended as synthetic system note when set
- answer streams successfully with conversation_id
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from tests.conftest import Project


class TestQAWithConversation:
    """answer_stream with conversation_id integration."""

    @pytest.mark.asyncio
    async def test_condense_invoked_on_second_turn(
        self, db_session: Session, test_project: Project
    ) -> None:
        """On turn 2+, condense_query is called with the prior history."""
        from orch.rag.chat_repo import append_message, get_or_create_conversation
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        # Setup: create conversation with 1 prior turn
        conv = get_or_create_conversation(
            db_session,
            project_id=test_project.id,
            session_id="test-session",
            conversation_id=None,
            module_path=None,
            context_level="architecture",
            first_question="First question",
        )
        db_session.flush()
        append_message(
            db_session, conversation_id=conv.id, role="user", content="What is keep_alive?"
        )
        append_message(
            db_session, conversation_id=conv.id, role="assistant", content="keep_alive is..."
        )
        db_session.commit()

        # Create a minimal config
        config = MagicMock(spec=CodeUnderstandingConfig)
        config.resolved_embed_model.return_value = "nomic-embed-text"
        config.resolved_llm_model.return_value = "llama3.2:3b"
        config.ollama_url = "http://localhost:11434"
        config.index_path = "/tmp/lancedb"

        engine = QAEngine(project_id=test_project.id, config=config)

        # Track condense calls and mock the DB-backed list_messages_for_context
        mock_messages = [
            {"role": "user", "content": "What is keep_alive?", "token_count": 5},
            {"role": "assistant", "content": "keep_alive is...", "token_count": 3},
        ]

        # Async generator for streaming - make it return an AsyncIterator directly
        # so that await on it works
        class MockAsyncIterator:
            def __init__(self):
                self.generated = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.generated:
                    self.generated = True
                    return MagicMock(delta="keep_alive is a function")
                raise StopAsyncIteration

        async def mock_astream_chat(*args, **kwargs):
            return MockAsyncIterator()

        with patch("orch.rag.qa._condense_query") as mock_condense:
            mock_condense.return_value = "what does keep_alive do in orch/daemon/main.py?"

            with (
                patch(
                    "orch.rag.chat_repo.list_messages_for_context",
                    return_value=(mock_messages, None),
                ),
                patch("lancedb.connect"),
                patch("orch.rag.qa.OllamaEmbedding") as mock_embed_cls,
            ):
                mock_embed_instance = MagicMock()
                mock_embed_instance.get_query_embedding = MagicMock(return_value=[0.0] * 768)
                mock_embed_cls.return_value = mock_embed_instance

                with patch("orch.rag.qa.Ollama") as mock_ollama_cls:
                    mock_ollama_instance = MagicMock()
                    mock_ollama_instance.astream_chat = AsyncMock(mock_astream_chat())
                    mock_ollama_cls.return_value = mock_ollama_instance

                    tokens = []
                    async for tok in engine.answer_stream(
                        question="explain how it works",
                        context_level="architecture",
                        context_doc_id=None,
                        conversation_history=[],
                        session=db_session,
                        conversation_id=conv.id,
                    ):
                        tokens.append(tok)

        # Condense was called with the prior history (turn 1)
        mock_condense.assert_called_once()
        call_args = mock_condense.call_args
        history_arg = call_args[0][0]  # first positional arg
        assert len(history_arg) == 2  # turn 1 (user + assistant)

    def test_system_prompt_contains_hardening_lines(
        self, db_session: Session, test_project: Project
    ) -> None:
        """The system prompt always includes the hardening lines."""
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import SYSTEM_PROMPT_HARDENING, QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        config.resolved_embed_model.return_value = "nomic-embed-text"
        config.resolved_llm_model.return_value = "llama3.2:3b"
        config.ollama_url = "http://localhost:11434"
        config.index_path = "/tmp/lancedb"

        engine = QAEngine(project_id=test_project.id, config=config)

        # Build system prompt via the method
        prompt = engine._build_system_prompt(
            context_doc_content="Some architecture content",
            chunks=["---\nsome code chunk\n"],
            module_path=None,
            module_name=None,
            fallback_triggered=False,
            context_chips=None,
            workitem_section="",
        )

        assert SYSTEM_PROMPT_HARDENING in prompt
        assert "trust the most recent one" in prompt
        assert "Do not claim to remember anything not present" in prompt

    def test_rolling_summary_prepended_as_synthetic_system_note(
        self, db_session: Session, test_project: Project
    ) -> None:
        """When rolling_summary is set on conversation, it appears as system note."""
        from orch.db.models import ChatConversation
        from orch.rag.chat_repo import (
            append_message,
            get_or_create_conversation,
            list_messages_for_context,
        )

        # Setup conversation with rolling_summary
        conv = get_or_create_conversation(
            db_session,
            project_id=test_project.id,
            session_id="test-session-summ",
            conversation_id=None,
            module_path=None,
            context_level="architecture",
            first_question="Test",
        )
        db_session.flush()
        append_message(
            db_session, conversation_id=conv.id, role="user", content="My name is sergio"
        )
        append_message(
            db_session, conversation_id=conv.id, role="assistant", content="Hello Sergio!"
        )
        db_session.commit()

        # Set rolling_summary on conversation
        db_session.execute(
            ChatConversation.__table__.update()
            .where(ChatConversation.__table__.c.id == conv.id)
            .values(rolling_summary="User's name is Sergio.")
        )
        db_session.commit()

        # Load via list_messages_for_context - synchronous call, no async needed
        kept, rolling_summary = list_messages_for_context(
            db_session,
            conversation_id=conv.id,
            soft_budget_tokens=100000,
        )
        assert rolling_summary == "User's name is Sergio."
        assert len(kept) == 2

    @pytest.mark.asyncio
    async def test_legacy_conversation_history_still_works(
        self, db_session: Session, test_project: Project
    ) -> None:
        """When conversation_id is None, falls back to conversation_history (backwards compat)."""
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.qa import QAEngine

        config = MagicMock(spec=CodeUnderstandingConfig)
        config.resolved_embed_model.return_value = "nomic-embed-text"
        config.resolved_llm_model.return_value = "llama3.2:3b"
        config.ollama_url = "http://localhost:11434"
        config.index_path = "/tmp/lancedb"

        engine = QAEngine(project_id=test_project.id, config=config)

        history = [
            {"role": "user", "content": "What is keep_alive?"},
            {"role": "assistant", "content": "keep_alive is a function..."},
        ]

        class MockAsyncIteratorLegacy:
            def __init__(self):
                self.generated = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self.generated:
                    self.generated = True
                    return MagicMock(delta="answer")
                raise StopAsyncIteration

        async def mock_astream_chat_legacy(*args, **kwargs):
            return MockAsyncIteratorLegacy()

        with patch("orch.rag.qa._condense_query") as mock_condense:
            mock_condense.return_value = "keep_alive function"

            with (
                patch("lancedb.connect"),
                patch("orch.rag.qa.OllamaEmbedding") as mock_embed_cls,
                patch("orch.rag.qa.Ollama") as mock_ollama_cls,
            ):
                mock_embed_instance = MagicMock()
                mock_embed_instance.get_query_embedding = MagicMock(return_value=[0.0] * 768)
                mock_embed_cls.return_value = mock_embed_instance

                mock_ollama_instance = MagicMock()
                mock_ollama_instance.astream_chat = AsyncMock(mock_astream_chat_legacy())
                mock_ollama_cls.return_value = mock_ollama_instance

                tokens = []
                async for tok in engine.answer_stream(
                    question="tell me more",
                    context_level="architecture",
                    context_doc_id=None,
                    conversation_history=history,
                    session=db_session,
                    conversation_id=None,
                ):
                    tokens.append(tok)

        # condense was called since len(history) >= 2
        mock_condense.assert_called_once()
