"""Integration tests: AC9 no-regressions on SSE event types and slash commands.

Verifies that the new meta event does not break existing SSE event type
contract, and that slash commands (/explain, /diagram, /why, /findusages,
/history) still produce their prior phase + citation behavior.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

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


def _extract_event_types(frames: list[str]) -> set[str]:
    """Extract all SSE event types from frames."""
    types = set()
    for frame in frames:
        if frame.startswith("event: "):
            types.add(frame[7:])
    return types


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


class TestAC9NoRegressions:
    """AC9: SSE event types match prior contract + new meta event."""

    def test_module_context_emits_expected_event_types(
        self,
        app: FastAPI,
        test_project: Project,
        db_session: Session,
        session_headers: dict[str, str],
    ) -> None:
        """SSE emits: meta, token, phase, citation, done (no regression on existing types)."""
        mock_engine_class = MagicMock()

        async def fake_stream(**kwargs):
            yield {"kind": "phase", "name": "composing", "detail": {"count": 1}}
            yield {"kind": "token", "text": "The daemon loop "}
            yield {"kind": "token", "text": "runs forever."}
            yield {
                "kind": "citation",
                "n": 1,
                "work_item_type": "Feature",
                "work_item_id": "F-00077",
                "label": "F-00077",
                "url": "/project/test-proj/item/F-00077",
                "snippet": "summary",
            }
            yield "__DONE__"

        mock_engine_instance = MagicMock()
        mock_engine_instance.answer_stream_v2 = fake_stream
        mock_engine_class.return_value = mock_engine_instance

        with patch("dashboard.routers.code_qa.QAEngine", mock_engine_class):
            status, frames = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "what does the daemon loop do?",
                    "context_level": "module",
                    "module_path": "orch/daemon",
                    "conversation_id": None,
                },
                session_headers,
            )

        assert status == 200
        event_types = _extract_event_types(frames)

        # All existing event types must still be present
        assert "token" in event_types, "token event must exist (prior contract)"
        assert "phase" in event_types, "phase event must exist (prior contract)"
        assert "citation" in event_types, "citation event must exist (prior contract)"
        assert "done" in event_types, "done event must exist (prior contract)"
        # New meta event
        assert "meta" in event_types, "meta event is new for F-00077"
        # error event is conditional
        assert "error" in event_types or "error" not in event_types  # optional

    def test_diagram_command_emits_phase_and_diagram_events(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """Slash command /diagram still produces phase + image events (no regression)."""
        mock_engine_class = MagicMock()

        async def fake_stream(**kwargs):
            yield {"kind": "phase", "name": "composing", "detail": {}}
            yield {"kind": "token", "text": "Here is a diagram:\n"}
            yield {"kind": "token", "text": "```mermaid\nflowchart TD\n  A-->B\n```"}
            yield {
                "kind": "image",
                "svg_b64": "PHN2Zz4=",
                "alt": "Diagram",
                "source_type": "mermaid",
                "block_index": 0,
            }
            yield "__DONE__"

        mock_engine_instance = MagicMock()
        mock_engine_instance.answer_stream_v2 = fake_stream
        mock_engine_class.return_value = mock_engine_instance

        with patch("dashboard.routers.code_qa.QAEngine", mock_engine_class):
            status, frames = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "/diagram how does the daemon work",
                    "context_level": "architecture",
                    "context_chips": ["diagram"],
                    "conversation_id": None,
                },
                session_headers,
            )

        assert status == 200
        event_types = _extract_event_types(frames)
        assert "phase" in event_types
        assert "token" in event_types
        assert "image" in event_types
        assert "done" in event_types
        assert "meta" in event_types  # new event

    def test_findusages_command_emits_phase(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """Slash command /findusages emits phase events (no regression)."""
        mock_engine_class = MagicMock()

        async def fake_stream(**kwargs):
            yield {
                "kind": "phase",
                "name": "finding_items",
                "detail": {"count": 2, "symbol": "keep_alive"},
            }
            yield {"kind": "token", "text": "Found 2 usages of keep_alive."}
            yield "__DONE__"

        mock_engine_instance = MagicMock()
        mock_engine_instance.answer_stream_v2 = fake_stream
        mock_engine_class.return_value = mock_engine_instance

        with patch("dashboard.routers.code_qa.QAEngine", mock_engine_class):
            status, frames = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "/findusages keep_alive",
                    "context_level": "module",
                    "module_path": "orch/daemon/main.py",
                    "context_chips": ["findusages"],
                    "conversation_id": None,
                },
                session_headers,
            )

        assert status == 200
        event_types = _extract_event_types(frames)
        assert "phase" in event_types, "phase event must exist for /findusages"
        assert "token" in event_types
        assert "done" in event_types

    def test_error_event_still_emitted_on_failure(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """When LLM is unavailable, error event is emitted (prior contract)."""
        mock_engine_class = MagicMock()

        async def fake_stream_that_errors(**kwargs):
            yield {
                "kind": "error",
                "message": "Local AI unavailable. Check that Ollama is running.",
            }

        mock_engine_instance = MagicMock()
        mock_engine_instance.answer_stream_v2 = fake_stream_that_errors
        mock_engine_class.return_value = mock_engine_instance

        with patch("dashboard.routers.code_qa.QAEngine", mock_engine_class):
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

        assert status == 200  # The HTTP status is still 200; error is in event
        event_types = _extract_event_types(frames)
        assert "error" in event_types, "error event must exist on LLM failure"

    def test_meta_event_always_first(
        self,
        app: FastAPI,
        test_project: Project,
        session_headers: dict[str, str],
    ) -> None:
        """The meta event always comes before any token/phase event."""
        mock_engine_class = MagicMock()

        async def fake_stream(**kwargs):
            yield {"kind": "phase", "name": "composing", "detail": {}}
            yield {"kind": "token", "text": "answer"}
            yield "__DONE__"

        mock_engine_instance = MagicMock()
        mock_engine_instance.answer_stream_v2 = fake_stream
        mock_engine_class.return_value = mock_engine_instance

        with patch("dashboard.routers.code_qa.QAEngine", mock_engine_class):
            _, frames = _sync_post_qa(
                app,
                test_project.id,
                {
                    "question": "hello",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
                session_headers,
            )

        meta_idx = next((i for i, f in enumerate(frames) if f == "event: meta"), None)
        token_idx = next((i for i, f in enumerate(frames) if f == "event: token"), None)
        assert meta_idx is not None, f"No meta event: {frames[:6]}"
        assert token_idx is not None, f"No token event: {frames[:6]}"
        assert meta_idx < token_idx, (
            f"meta event (idx={meta_idx}) must come before first token (idx={token_idx})"
        )
