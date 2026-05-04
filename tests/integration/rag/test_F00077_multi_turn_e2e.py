"""Integration tests for F-00077 multi-turn conversation memory e2e.

Exercises the actual code paths from dashboard/routers/code_qa.py through
orch/rag/qa.py to the DB, using stubbed QAEngine.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

# Import so orch.db.session is initialised before IW_CORE_TEST_CONTEXT takes effect
from dashboard.app import create_app  # noqa: F401
from dashboard.dependencies import get_db
from orch.db.models import ChatConversation, ChatMessage, Project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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

    def test_first_turn_creates_conversation_and_emits_meta(
        self,
        client: TestClient,
        test_project: Project,
        db_session: Session,
        db_session_factory,
    ) -> None:
        """Turn 1: conversation_id=None creates a conversation and is emitted in meta."""
        mock_engine_class = MagicMock()

        async def fake_stream(**kwargs):
            yield {"kind": "token", "text": "keep_alive is a function that..."}
            yield "__DONE__"

        mock_engine_instance = MagicMock()
        mock_engine_instance.answer_stream_v2 = fake_stream
        mock_engine_class.return_value = mock_engine_instance

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
                    "question": "what does keep_alive do in orch/daemon/main.py?",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
            )

        assert status == 200, f"Expected 200, got {status}: {frames[:3]}"
        conv_id = _extract_conversation_id_from_meta(frames)
        assert conv_id is not None, f"Expected meta event with conversation_id, got: {frames[:5]}"
        uuid.UUID(conv_id)  # raises if invalid

        db_session.expire_all()
        conv = db_session.get(ChatConversation, conv_id)
        assert conv is not None
        assert conv.project_id == test_project.id

    def test_both_turns_persisted_and_streamed(
        self,
        client: TestClient,
        test_project: Project,
        db_session: Session,
        db_session_factory,
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

        with (
            patch("orch.rag.qa.QAEngine", mock_engine_class),
            patch(
                "dashboard.routers.code_qa.SessionLocal",
                side_effect=db_session_factory,
            ),
        ):
            # Turn 1
            _, frames0 = _post_qa(
                client,
                test_project.id,
                {
                    "question": "what does keep_alive do?",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
            )
            conv_id = _extract_conversation_id_from_meta(frames0)
            assert conv_id is not None

            # Turn 2
            _, frames1 = _post_qa(
                client,
                test_project.id,
                {
                    "question": "explain how it works",
                    "context_level": "architecture",
                    "conversation_id": conv_id,
                },
            )

        # Verify stream content
        tokens = _extract_all_b64_tokens(frames1)
        assert len(tokens) > 0, "Expected at least one token"
        assert _has_done_event(frames1), "Expected __DONE__ event"

        # Verify messages persisted
        db_session.expire_all()
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
        client: TestClient,
        test_project: Project,
        db_session_factory,
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

        with (
            patch("orch.rag.qa.QAEngine", mock_engine_class),
            patch(
                "dashboard.routers.code_qa.SessionLocal",
                side_effect=db_session_factory,
            ),
        ):
            # Turn 1 — establish identity
            _, frames0 = _post_qa(
                client,
                test_project.id,
                {
                    "question": "my name is sergio",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
            )
            conv_id = _extract_conversation_id_from_meta(frames0)
            assert conv_id is not None

            # Turn 2 — retrieve identity
            _, frames1 = _post_qa(
                client,
                test_project.id,
                {
                    "question": "what's my name?",
                    "context_level": "architecture",
                    "conversation_id": conv_id,
                },
            )

        # Verify "sergio" appears in the streamed response
        tokens = _extract_all_b64_tokens(frames1)
        answer_text = "".join(tokens)
        assert "sergio" in answer_text.lower(), (
            f"Expected answer to contain 'sergio', got: {answer_text}"
        )
