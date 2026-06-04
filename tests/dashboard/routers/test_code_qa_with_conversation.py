"""Tests for code_qa SSE endpoint with conversation persistence (F-00077)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.orm import Session

    from orch.db.models import Project


def _sync_post_qa(
    app: FastAPI,
    project_id: str,
    json_body: dict,
    session_headers: dict[str, str],
) -> tuple[int, list[str]]:
    """POST to code/qa and return (status_code, list of SSE frame strings])."""
    import asyncio

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


class TestCodeQASseWithConversation:
    """SSE meta event and persistence for POST /api/projects/{id}/code/qa."""

    @pytest.fixture
    def session_headers(self, app: FastAPI) -> dict[str, str]:
        """Return headers dict with a valid iw_chat_session cookie."""
        import asyncio
        import re

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

    def test_meta_event_contains_conversation_id_on_first_turn(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """SSE stream starts with event: meta containing a fresh conversation_id."""
        with patch("orch.rag.qa.QAEngine") as mock_engine:
            mock_instance = MagicMock()

            async def fake_stream(**kwargs):
                """Yield fake SSE tokens simulating a QA stream response."""
                yield {"kind": "token", "text": "test response"}
                yield "__DONE__"

            mock_instance.answer_stream_v2 = fake_stream
            mock_engine.return_value = mock_instance

            status, frames = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "hello",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
                session_headers,
            )

        assert status == 200, f"Expected 200, got {status}: {frames[:3]}"
        conv_id = _extract_conversation_id_from_meta(frames)
        assert conv_id is not None, (
            f"Expected meta event with conversation_id, got frames: {frames[:5]}"
        )
        import uuid

        uuid.UUID(conv_id)  # raises if invalid

    def test_conversation_id_meta_emitted_before_token_events(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """The meta event always comes before any token event."""
        with patch("orch.rag.qa.QAEngine") as mock_engine:
            mock_instance = MagicMock()

            async def fake_stream(**kwargs):
                """Yield fake SSE tokens simulating a QA stream response."""
                yield {"kind": "token", "text": "hello"}
                yield "__DONE__"

            mock_instance.answer_stream_v2 = fake_stream
            mock_engine.return_value = mock_instance

            status, frames = _sync_post_qa(
                app,
                test_project.id,
                {"question": "hi", "context_level": "architecture", "conversation_id": None},
                session_headers,
            )

        assert status == 200
        meta_idx = next((i for i, f in enumerate(frames) if f == "event: meta"), None)
        token_idx = next((i for i, f in enumerate(frames) if f == "event: token"), None)
        assert meta_idx is not None, f"No meta event in frames: {frames[:6]}"
        assert token_idx is not None, f"No token event in frames: {frames[:6]}"
        assert meta_idx < token_idx, (
            f"Meta event (idx={meta_idx}) must come before first token (idx={token_idx})"
        )

    def test_second_turn_persists_user_and_assistant_messages(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """With conversation_id, both user and assistant messages are persisted."""
        from orch.db.models import ChatMessage

        with patch("orch.rag.qa.QAEngine") as mock_engine:
            mock_instance = MagicMock()

            async def fake_stream(**kwargs):
                """Yield fake SSE tokens simulating a QA stream response."""
                yield {"kind": "token", "text": "answer text"}
                yield "__DONE__"

            mock_instance.answer_stream_v2 = fake_stream
            mock_engine.return_value = mock_instance

            # First turn — get conversation_id
            _, frames0 = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "first question",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
                session_headers,
            )
            conv_id = _extract_conversation_id_from_meta(frames0)
            assert conv_id is not None

            # Second turn — send conversation_id, should persist both messages
            _, frames1 = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "second question",
                    "context_level": "architecture",
                    "conversation_id": conv_id,
                },
                session_headers,
            )
            assert frames1, "Expected SSE frames"

        # Verify: at least one user message and one assistant message
        messages = (
            db_session.execute(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conv_id)
                .order_by(ChatMessage.created_at)
            )
            .scalars()
            .all()
        )

        user_msgs = [m for m in messages if m.role == "user"]
        assistant_msgs = [m for m in messages if m.role == "assistant"]

        assert len(user_msgs) >= 1, f"Expected at least 1 user message, got {len(user_msgs)}"
        assert len(assistant_msgs) >= 1, (
            f"Expected at least 1 assistant message, got {len(assistant_msgs)}"
        )

    def test_stranger_conversation_id_creates_new_conversation(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """Sending a conversation_id from another session results in a NEW conversation_id."""
        from orch.db.models import ChatConversation

        # Create a conversation in another session
        stranger_conv = ChatConversation(
            project_id=test_project.id,
            session_id="stranger-session-abc123",
            context_level="architecture",
        )
        db_session.add(stranger_conv)
        db_session.flush()
        stranger_conv_id = stranger_conv.id

        with patch("orch.rag.qa.QAEngine") as mock_engine:
            mock_instance = MagicMock()

            async def fake_stream(**kwargs):
                """Yield fake SSE tokens simulating a QA stream response."""
                yield {"kind": "token", "text": "response"}
                yield "__DONE__"

            mock_instance.answer_stream_v2 = fake_stream
            mock_engine.return_value = mock_instance

            status, frames = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "hello",
                    "context_level": "architecture",
                    "conversation_id": stranger_conv_id,
                },
                session_headers,
            )

        assert status == 200
        new_conv_id = _extract_conversation_id_from_meta(frames)
        assert new_conv_id is not None
        assert new_conv_id != stranger_conv_id, (
            "Server should treat stranger's conversation_id as not-found and create new"
        )

    def test_interrupted_stream_persists_partial_with_error_flag(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """Stream disconnection results in a chat_messages row with metadata.error=true."""
        import contextlib

        from orch.db.models import ChatConversation, ChatMessage

        with patch("orch.rag.qa.QAEngine") as mock_engine:
            mock_instance = MagicMock()

            async def fake_stream_that_errors(**kwargs):
                """Yield fake SSE tokens and then raise a runtime exception."""
                yield {"kind": "token", "text": "partial response "}
                raise RuntimeError("simulated stream disconnection")

            mock_instance.answer_stream_v2 = fake_stream_that_errors
            mock_engine.return_value = mock_instance

            with contextlib.suppress(Exception):
                _sync_post_qa(
                    app,
                    test_project.id,
                    {"question": "hello", "context_level": "architecture", "conversation_id": None},
                    session_headers,
                )

        # Find error messages in recent conversations for this project
        recent = (
            db_session.query(ChatMessage)
            .join(ChatConversation)
            .where(ChatConversation.project_id == test_project.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
            .all()
        )

        error_msgs = [
            m for m in recent if m.role == "assistant" and m.message_metadata.get("error") is True
        ]
        assert len(error_msgs) >= 1, (
            f"Expected at least one assistant message with metadata.error=true, "
            f"found {len(error_msgs)} messages"
        )

    def test_hard_budget_overflow_enqueues_summarization_job(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """When token_count exceeds HARD_BUDGET, exactly one ChatSummarizationJob is queued."""
        from orch.db.models import ChatConversation, ChatMessage, ChatSummarizationJob

        with patch("orch.rag.qa.QAEngine") as mock_engine:
            mock_instance = MagicMock()

            async def fake_stream(**kwargs):
                """Yield fake SSE tokens simulating a QA stream response."""
                yield {"kind": "token", "text": "answer"}
                yield "__DONE__"

            mock_instance.answer_stream_v2 = fake_stream
            mock_engine.return_value = mock_instance

            # First turn — get conversation_id
            _, frames0 = _sync_post_qa(
                app,
                test_project.id,
                {"question": "hello", "context_level": "architecture", "conversation_id": None},
                session_headers,
            )
            conv_id = _extract_conversation_id_from_meta(frames0)

        # Insert messages with high token_count to trigger enqueue
        conv = db_session.get(ChatConversation, conv_id)
        assert conv is not None

        for i in range(10):
            msg = ChatMessage(
                conversation_id=conv_id,
                role="user",
                content=f"message content token count high {i}" * 50,
                token_count=800,
                message_metadata={},
            )
            db_session.add(msg)
        db_session.flush()

        # Trigger enqueue check
        from orch.rag.chat_repo import enqueue_summarization_if_needed
        from orch.rag.qa import HISTORY_HARD_BUDGET_TOKENS

        enqueue_summarization_if_needed(
            db_session,
            conversation_id=conv_id,
            hard_budget_tokens=HISTORY_HARD_BUDGET_TOKENS,
        )
        db_session.commit()

        # Verify exactly one job
        jobs = (
            db_session.query(ChatSummarizationJob)
            .where(ChatSummarizationJob.conversation_id == conv_id)
            .all()
        )
        assert len(jobs) == 1, f"Expected exactly 1 summarization job, got {len(jobs)}"
        assert jobs[0].status == "queued"
