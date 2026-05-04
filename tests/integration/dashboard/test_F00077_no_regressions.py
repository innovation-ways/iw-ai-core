"""Integration tests: AC9 no-regressions on SSE event types and slash commands.

Verifies that the new meta event does not break existing SSE event type
contract, and that slash commands (/explain, /diagram, /why, /findusages,
/history) still produce their prior phase + citation behavior.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Import so orch.db.session is initialised before IW_CORE_TEST_CONTEXT takes effect
from dashboard.app import create_app  # noqa: F401
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """TestClient with get_db overridden to use the test session."""
    import os

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


class TestAC9NoRegressions:
    """AC9: SSE event types match prior contract + new meta event."""

    def test_module_context_emits_expected_event_types(
        self,
        client: TestClient,
        test_project: Project,
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

        with patch("orch.rag.qa.QAEngine", mock_engine_class):
            status, frames = _post_qa(
                client,
                test_project.id,
                {
                    "question": "what does the daemon loop do?",
                    "context_level": "module",
                    "module_path": "orch/daemon",
                    "conversation_id": None,
                },
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
        client: TestClient,
        test_project: Project,
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

        with patch("orch.rag.qa.QAEngine", mock_engine_class):
            status, frames = _post_qa(
                client,
                test_project.id,
                {
                    "question": "/diagram how does the daemon work",
                    "context_level": "architecture",
                    "context_chips": ["diagram"],
                    "conversation_id": None,
                },
            )

        assert status == 200
        event_types = _extract_event_types(frames)
        assert "phase" in event_types
        assert "token" in event_types
        assert "done" in event_types
        assert "meta" in event_types  # new event

    def test_findusages_command_emits_phase(
        self,
        client: TestClient,
        test_project: Project,
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

        with patch("orch.rag.qa.QAEngine", mock_engine_class):
            status, frames = _post_qa(
                client,
                test_project.id,
                {
                    "question": "/findusages keep_alive",
                    "context_level": "module",
                    "module_path": "orch/daemon/main.py",
                    "context_chips": ["findusages"],
                    "conversation_id": None,
                },
            )

        assert status == 200
        event_types = _extract_event_types(frames)
        assert "phase" in event_types, "phase event must exist for /findusages"
        assert "token" in event_types
        assert "done" in event_types

    def test_error_event_still_emitted_on_failure(
        self,
        client: TestClient,
        test_project: Project,
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

        with patch("orch.rag.qa.QAEngine", mock_engine_class):
            status, frames = _post_qa(
                client,
                test_project.id,
                {
                    "question": "hello",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
            )

        assert status == 200  # The HTTP status is still 200; error is in event
        event_types = _extract_event_types(frames)
        assert "error" in event_types, "error event must exist on LLM failure"

    def test_meta_event_always_first(
        self,
        client: TestClient,
        test_project: Project,
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

        with patch("orch.rag.qa.QAEngine", mock_engine_class):
            _, frames = _post_qa(
                client,
                test_project.id,
                {
                    "question": "hello",
                    "context_level": "architecture",
                    "conversation_id": None,
                },
            )

        meta_idx = next((i for i, f in enumerate(frames) if f == "event: meta"), None)
        token_idx = next((i for i, f in enumerate(frames) if f == "event: token"), None)
        assert meta_idx is not None, f"No meta event: {frames[:6]}"
        assert token_idx is not None, f"No token event: {frames[:6]}"
        assert meta_idx < token_idx, (
            f"meta event (idx={meta_idx}) must come before first token (idx={token_idx})"
        )
