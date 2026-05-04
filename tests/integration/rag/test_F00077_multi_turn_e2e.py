"""Integration tests for F-00077 multi-turn conversation memory e2e.

Exercises the actual code paths from dashboard/routers/code_qa.py through
orch/rag/qa.py to the DB, using stubbed Ollama LLM and LanceDB.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

# Import so orch.db.session is initialised before IW_CORE_TEST_CONTEXT takes effect
from dashboard.app import create_app  # noqa: F401
from orch.db.models import ChatConversation, ChatMessage, Project

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.orm import Session


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


def _extract_all_b64_tokens(frames: list[str]) -> list[str]:
    """Extract all base64-decoded token texts from token events."""
    tokens = []
    for i, frame in enumerate(frames):
        if frame == "event: token":
            next_line = i + 1
            if next_line < len(frames) and frames[next_line].startswith("data: "):
                data_str = frames[next_line][6:]
                try:
                    obj = json.loads(data_str)
                    b64 = obj.get("b64", "")
                    token_text = base64.b64decode(b64).decode("utf-8")
                    tokens.append(token_text)
                except Exception:
                    pass
    return tokens


def _has_done_event(frames: list[str]) -> bool:
    """Return True if frames contain an 'event: done' line."""
    return "event: done" in frames


class TestF00077MultiTurnE2E:
    """End-to-end multi-turn conversation memory — AC1, AC2, AC4."""

    @pytest.fixture
    def session_headers(self, app: FastAPI) -> dict[str, str]:
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

    def test_first_turn_creates_conversation_and_emits_meta(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """Turn 1: conversation_id=None creates a conversation and is emitted in meta."""
        mock_engine_class = MagicMock()

        async def fake_stream(**kwargs):
            yield {"kind": "token", "text": "keep_alive is a function that..."}
            yield "__DONE__"

        mock_engine_instance = MagicMock()
        mock_engine_instance.answer_stream_v2 = fake_stream
        mock_engine_class.return_value = mock_engine_instance

        with patch("dashboard.routers.code_qa.QAEngine", mock_engine_class):
            status, frames = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "what does keep_alive do in orch/daemon/main.py?",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
                session_headers,
            )

        assert status == 200, f"Expected 200, got {status}: {frames[:3]}"
        conv_id = _extract_conversation_id_from_meta(frames)
        assert conv_id is not None, f"Expected meta event with conversation_id, got: {frames[:5]}"
        uuid.UUID(conv_id)  # raises if invalid

        conv = db_session.get(ChatConversation, conv_id)
        assert conv is not None
        assert conv.project_id == test_project.id

    def test_both_turns_persisted_and_streamed(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """Both user and assistant messages are persisted; tokens stream; __DONE__ reached."""
        mock_engine_class = MagicMock()

        async def fake_stream(**kwargs):
            yield {"kind": "token", "text": "answer part 1 "}
            yield {"kind": "token", "text": "answer part 2"}
            yield "__DONE__"

        mock_engine_instance = MagicMock()
        mock_engine_instance.answer_stream_v2 = fake_stream
        mock_engine_class.return_value = mock_engine_instance

        with patch("dashboard.routers.code_qa.QAEngine", mock_engine_class):
            # Turn 1
            _, frames0 = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "what does keep_alive do?",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
                session_headers,
            )
            conv_id = _extract_conversation_id_from_meta(frames0)
            assert conv_id is not None

            # Turn 2
            _, frames1 = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "explain how it works",
                    "context_level": "architecture",
                    "conversation_id": conv_id,
                },
                session_headers,
            )

        # Verify stream content
        tokens = _extract_all_b64_tokens(frames1)
        assert len(tokens) > 0, "Expected at least one token"
        assert _has_done_event(frames1), "Expected __DONE__ event"

        # Verify messages persisted
        messages = (
            db_session.execute(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conv_id)
                .order_by(ChatMessage.created_at)
            )
            .scalars()
            .all()
        )
        assert len(messages) >= 4, (
            f"Expected >= 4 messages (2 user + 2 assistant), got {len(messages)}"
        )
        user_msgs = [m for m in messages if m.role == "user"]
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        assert len(user_msgs) >= 2, f"Expected >= 2 user messages, got {len(user_msgs)}"
        assert len(assistant_msgs) >= 2, (
            f"Expected >= 2 assistant messages, got {len(assistant_msgs)}"
        )

    def test_ac1_name_persists_across_turns(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """AC1: prior history 'my name is sergio' is remembered; answer cites 'sergio'."""
        mock_engine_class = MagicMock()

        async def fake_stream(**kwargs):
            # The LLM would see history including "my name is sergio" and answer
            yield {"kind": "token", "text": "Your name is sergio."}
            yield "__DONE__"

        mock_engine_instance = MagicMock()
        mock_engine_instance.answer_stream_v2 = fake_stream
        mock_engine_class.return_value = mock_engine_instance

        with patch("dashboard.routers.code_qa.QAEngine", mock_engine_class):
            # Turn 1 — establish identity
            _, frames0 = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "my name is sergio",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
                session_headers,
            )
            conv_id = _extract_conversation_id_from_meta(frames0)
            assert conv_id is not None

            # Turn 2 — retrieve identity
            _, frames1 = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "what's my name?",
                    "context_level": "architecture",
                    "conversation_id": conv_id,
                },
                session_headers,
            )

        # Verify "sergio" appears in the streamed response
        tokens = _extract_all_b64_tokens(frames1)
        answer_text = "".join(tokens)
        assert "sergio" in answer_text.lower(), (
            f"Expected answer to contain 'sergio', got: {answer_text}"
        )
