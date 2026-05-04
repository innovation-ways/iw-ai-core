"""Integration test: stream interruption persists partial content (Invariant 1).

Verifies that when the QA stream is interrupted mid-stream (after 3 tokens),
a chat_messages row is created with the partial content and
metadata.error=true, and that subsequent history loading filters it out.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

# Import so orch.db.session is initialised before IW_CORE_TEST_CONTEXT takes effect
from dashboard.app import create_app  # noqa: F401
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project


@pytest.fixture
def client(db_session: Session):
    """TestClient with get_db overridden to the test session."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


def _post_qa(
    client: TestClient,
    project_id: str,
    json_body: dict,
) -> tuple[int, list[str]]:
    """POST to code/qa and return (status_code, list of SSE frame strings)."""
    resp = client.post(
        f"/api/projects/{project_id}/code/qa",
        json=json_body,
    )
    frames = [line for line in resp.text.split("\n") if line]
    return resp.status_code, frames


class TestStreamInterruption:
    """Invariant 1: stream interruption persists partial content with error flag."""

    def test_interrupted_stream_persists_partial_with_error_flag(
        self,
        client: TestClient,
        test_project: Project,
        db_session: Session,
        db_session_factory,
    ) -> None:
        """After 3 tokens the stream raises; partial assistant message is persisted."""
        from orch.db.models import ChatConversation, ChatMessage

        mock_engine_class = MagicMock()

        async def fake_stream_that_errors_after_3(**kwargs):
            """Yield 3 tokens then raise — error is caught by _run_qa_in_thread."""
            yield {"kind": "token", "text": "first "}
            yield {"kind": "token", "text": "second "}
            yield {"kind": "token", "text": "third"}
            raise RuntimeError("simulated stream disconnection after 3 tokens")

        mock_engine_instance = MagicMock()
        mock_engine_instance.answer_stream_v2 = fake_stream_that_errors_after_3
        mock_engine_class.return_value = mock_engine_instance

        # Patch SessionLocal so the SSE generator's internal session_factory
        # returns sessions bound to the same test transaction as db_session.
        with (
            patch("orch.rag.qa.QAEngine", mock_engine_class),
            patch(
                "dashboard.routers.code_qa.SessionLocal",
                side_effect=db_session_factory,
            ),
        ):
            status, frames = _post_qa(
                client,
                test_project.id,
                {
                    "question": "what does keep_alive do?",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
            )

        assert status == 200, f"Expected 200, got {status}. Frames: {frames[:6]}"

        # Refresh db_session to see any rows committed by the SSE generator
        db_session.expire_all()

        # Find the most recent conversation for this project
        recent_convs = (
            db_session.execute(
                select(ChatConversation)
                .where(ChatConversation.project_id == test_project.id)
                .order_by(ChatConversation.created_at.desc())
                .limit(1)
            )
            .scalars()
            .all()
        )
        assert len(recent_convs) >= 1, "Expected at least one conversation"
        conv_id = recent_convs[0].id

        # Find error messages
        error_msgs = (
            db_session.execute(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conv_id)
                .where(ChatMessage.role == "assistant")
                .where(ChatMessage.message_metadata["error"].astext == "true")
                .order_by(ChatMessage.created_at.desc())
            )
            .scalars()
            .all()
        )
        all_msgs = (
            db_session.execute(select(ChatMessage).where(ChatMessage.conversation_id == conv_id))
            .scalars()
            .all()
        )
        assert len(error_msgs) >= 1, (
            f"Expected at least one assistant message with metadata.error=true, "
            f"found {len(error_msgs)} error messages. "
            f"All messages: {[(m.role, m.content[:30], m.message_metadata) for m in all_msgs]}"
        )
        partial_msg = error_msgs[0]
        assert "first" in partial_msg.content, (
            f"Partial content should contain 'first', got: {partial_msg.content!r}"
        )
        assert partial_msg.message_metadata.get("error") is True

    def test_partial_message_excluded_from_subsequent_history(
        self,
        client: TestClient,
        test_project: Project,
        db_session: Session,
    ) -> None:
        """Subsequent turn loading history filters out messages with error=true."""
        from orch.db.models import ChatConversation, ChatMessage
        from orch.rag.chat_repo import list_messages_for_context
        from orch.rag.qa import HISTORY_SOFT_BUDGET_TOKENS

        # Create a conversation and manually add a partial error message
        conv = ChatConversation(
            project_id=test_project.id,
            session_id="test-session-stream-partial",
            context_level="architecture",
        )
        db_session.add(conv)
        db_session.flush()
        conv_id = conv.id

        # Add a complete user message
        m_user = ChatMessage(
            conversation_id=conv_id,
            role="user",
            content="what is keep_alive?",
            token_count=100,
            message_metadata={},
        )
        db_session.add(m_user)

        # Add a partial assistant message with error=true
        m_partial = ChatMessage(
            conversation_id=conv_id,
            role="assistant",
            content="partial res",
            token_count=50,
            message_metadata={"error": True, "error_reason": "stream disconnected"},
        )
        db_session.add(m_partial)
        db_session.flush()

        # Load history via list_messages_for_context
        kept_messages, _ = list_messages_for_context(
            db_session,
            conversation_id=conv_id,
            soft_budget_tokens=HISTORY_SOFT_BUDGET_TOKENS,
        )

        # The partial message should be filtered out
        roles = [m.get("role") for m in kept_messages]
        assert "assistant" not in roles or all(
            m.get("role") != "assistant" or m.get("content") != "partial res" for m in kept_messages
        ), (
            "Partial assistant message with error=true should be excluded from loaded history. "
            f"Got: {kept_messages}"
        )

    def test_complete_messages_preserved_after_error(
        self,
        client: TestClient,
        test_project: Project,
        db_session: Session,
    ) -> None:
        """After an error, subsequent complete messages are still included."""
        from orch.db.models import ChatConversation, ChatMessage
        from orch.rag.chat_repo import list_messages_for_context
        from orch.rag.qa import HISTORY_SOFT_BUDGET_TOKENS

        conv = ChatConversation(
            project_id=test_project.id,
            session_id="test-session-complete-preserved",
            context_level="architecture",
        )
        db_session.add(conv)
        db_session.flush()
        conv_id = conv.id

        # Complete message before error
        m1 = ChatMessage(
            conversation_id=conv_id,
            role="user",
            content="first question",
            token_count=50,
            message_metadata={},
        )
        # Partial error message
        m2 = ChatMessage(
            conversation_id=conv_id,
            role="assistant",
            content="partial",
            token_count=30,
            message_metadata={"error": True, "error_reason": "disconnect"},
        )
        # Complete message after error (normal flow)
        m3 = ChatMessage(
            conversation_id=conv_id,
            role="assistant",
            content="complete response after reconnect",
            token_count=100,
            message_metadata={},
        )
        for m in [m1, m2, m3]:
            db_session.add(m)
        db_session.flush()

        kept_messages, _ = list_messages_for_context(
            db_session,
            conversation_id=conv_id,
            soft_budget_tokens=HISTORY_SOFT_BUDGET_TOKENS,
        )

        # m3 (complete) should be preserved; m2 (error) should not
        contents = [m.get("content") for m in kept_messages]
        assert "complete response after reconnect" in contents
        assert "partial" not in contents
