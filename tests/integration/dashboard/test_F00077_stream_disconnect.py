"""Integration test: stream interruption persists partial content (Invariant 1).

Verifies that when the QA stream is interrupted mid-stream (after 3 tokens),
a chat_messages row is created with the partial content and
metadata.error=true, and that subsequent history loading filters it out.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

# Import so orch.db.session is initialised before IW_CORE_TEST_CONTEXT takes effect
from dashboard.app import create_app  # noqa: F401

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.orm import Session

    from orch.db.models import Project


@pytest.fixture
def app() -> FastAPI:
    """FastAPI app for dashboard router tests."""
    return create_app()


def _sync_post_qa(
    app: FastAPI,
    project_id: str,
    json_body: dict,
    session_headers: dict[str, str],
) -> tuple[int, list[str]]:
    """POST to code/qa and return (status_code, list of SSE frame strings])."""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    frames: list[str] = []

    async def _do() -> tuple[int, list[str]]:
        nonlocal frames
        async with (
            AsyncClient(transport=transport, base_url="http://test") as client,
            client.stream(
                "POST",
                f"/api/projects/{project_id}/code/qa",
                headers=session_headers,
                json=json_body,
            ) as resp,
        ):
            status = resp.status_code
            async for line in resp.aiter_lines():
                if line:
                    frames.append(line)
            return status, frames

    return asyncio.run(_do())


def _extract_conversation_id_from_meta(frames: list[str]) -> str | None:
    """Parse conversation_id from an event: meta frame."""
    import json

    for i, frame in enumerate(frames):
        if frame == "event: meta":
            next_line = i + 1
            if next_line < len(frames) and frames[next_line].startswith("data: "):
                data_str = frames[next_line][6:]
                try:
                    obj = json.loads(data_str)
                    return obj.get("conversation_id")
                except json.JSONDecodeError:
                    pass
    return None


@pytest.fixture
def session_headers(app: FastAPI) -> dict[str, str]:
    """Return headers dict with a valid iw_chat_session cookie."""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)

    async def _capture() -> dict[str, str]:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            set_cookie = resp.headers.get("set-cookie", "")
            match = re.search(r"iw_chat_session=([a-f0-9-]{36})", set_cookie)
            assert match
            return {"cookie": f"iw_chat_session={match.group(1)}"}

    return asyncio.run(_capture())


class TestStreamInterruption:
    """Invariant 1: stream interruption persists partial content with error flag."""

    def test_interrupted_stream_persists_partial_with_error_flag(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """After 3 tokens the stream raises; partial assistant message is persisted."""
        from orch.db.models import ChatConversation, ChatMessage

        mock_engine_class = MagicMock()

        token_count = [0]

        async def fake_stream_that_errors_after_3(**kwargs):
            """Yield 3 tokens then raise."""
            yield {"kind": "token", "text": "first "}
            token_count[0] += 1
            yield {"kind": "token", "text": "second "}
            token_count[0] += 1
            yield {"kind": "token", "text": "third"}
            token_count[0] += 1
            raise RuntimeError("simulated stream disconnection after 3 tokens")

        mock_engine_instance = MagicMock()
        mock_engine_instance.answer_stream_v2 = fake_stream_that_errors_after_3
        mock_engine_class.return_value = mock_engine_instance

        # Suppress the exception that bubbles up from StreamingResponse
        with (
            patch("dashboard.routers.code_qa.QAEngine", mock_engine_class),
            pytest.raises(RuntimeError),
        ):
            _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "what does keep_alive do?",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
                session_headers,
            )

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
            f"found {len(error_msgs)} messages. "
            f"All messages: {[(m.role, m.content[:30], m.message_metadata) for m in all_msgs]}"
        )
        partial_msg = error_msgs[0]
        assert partial_msg.content in ("first second third", "first second third "), (
            f"Partial content should be 'first second third', got: {partial_msg.content!r}"
        )
        assert partial_msg.message_metadata.get("error") is True
        assert (
            "error_reason" in partial_msg.message_metadata
            or "error" in partial_msg.message_metadata
        )

    def test_partial_message_excluded_from_subsequent_history(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
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
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
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
