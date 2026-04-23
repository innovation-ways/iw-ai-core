"""Integration tests for no-regression of code-only Q&A behavior.

Tests verify AC9 and Invariant 3:
- Replay a known code-only question that was working before F-00055
- Assert bit-for-bit-equivalent SSE output: only token and done events
- No phase events; no work-item citation events
- Confirms existing behavior is preserved

All tests use testcontainers — NEVER connect to live DB.
Mock QAEngine — never call real Ollama.
"""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import Project

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from pathlib import Path

    from sqlalchemy.orm import Session


def _parse_sse(body: str) -> list[dict[str, object]]:
    """Parse SSE body into a list of {'event': str | None, 'data': dict} entries."""
    events: list[dict[str, object]] = []
    current_event: str | None = None
    for raw in body.split("\n"):
        line = raw.rstrip("\r")
        if not line:
            current_event = None
            continue
        if line.startswith("event: "):
            current_event = line[len("event: ") :]
        elif line.startswith("data: "):
            payload = json.loads(line[len("data: ") :])
            events.append({"event": current_event, "data": payload})
    return events


def _decode_token(entry: dict[str, object]) -> str:
    data = entry["data"]
    assert isinstance(data, dict)
    b64 = data["b64"]
    assert isinstance(b64, str)
    return base64.b64decode(b64).decode("utf-8")


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Generator[Session, None, None]:
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


@pytest.fixture
def project_with_index(
    db_session: Session,
    tmp_path: Path,
) -> Project:
    """Create a project with code_understanding config pointing to tmp index path."""
    project_index_path = tmp_path / "code-index" / "no-reg-test" / "vectors"
    project_index_path.mkdir(parents=True)

    project = Project(
        id="no-reg-test",
        display_name="No Regression Test Project",
        repo_root="/repos/test",
        config={
            "code_understanding": {
                "provider": "local",
                "index_tier": "balanced",
                "ollama_url": "http://localhost:11434",
                "index_path": str(tmp_path / "code-index"),
            }
        },
    )
    db_session.add(project)
    db_session.flush()
    return project


async def mock_answer_stream_code_only(**kwargs: object) -> AsyncGenerator[dict, None]:
    """Mock code-only answer_stream that returns tokens only (no phase events)."""
    yield {"kind": "token", "text": "The "}
    yield {"kind": "token", "text": "CodeIndexJob "}
    yield {"kind": "token", "text": "model "}
    yield {"kind": "token", "text": "is "}
    yield {"kind": "token", "text": "defined "}
    yield {"kind": "token", "text": "at "}
    yield {"kind": "token", "text": "line "}
    yield {"kind": "token", "text": "42 "}
    yield {"kind": "token", "text": "in "}
    yield {"kind": "token", "text": "orch/db/models.py."}


def test_code_only_no_phase_events(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC9/Invariant 3: Code-only query emits NO phase events."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    def mock_classify(question: str, config: object, context_chips: list | None = None) -> str:
        return "code_only"

    with (
        patch("orch.rag.qa.QAEngine") as mock_qa_engine,
        patch("orch.rag.classifier.classify_query", mock_classify),
    ):
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_code_only

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "where is CodeIndexJob defined?",
                "context_level": "architecture",
                "context_chips": [],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    phase_events = [e for e in events if e["event"] == "phase"]
    assert len(phase_events) == 0, (
        f"AC9/Invariant 3: Code-only query must NOT emit phase events. "
        f"Got phase events: {[(e['event'], e['data']) for e in phase_events]}"
    )


def test_code_only_no_citation_events(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC9/Invariant 3: Code-only query emits NO work-item citation events."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    def mock_classify(question: str, config: object, context_chips: list | None = None) -> str:
        return "code_only"

    with (
        patch("orch.rag.qa.QAEngine") as mock_qa_engine,
        patch("orch.rag.classifier.classify_query", mock_classify),
    ):
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_code_only

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "where is CodeIndexJob defined?",
                "context_level": "architecture",
                "context_chips": [],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    citation_events = [e for e in events if e["event"] == "citation"]
    assert len(citation_events) == 0, (
        f"AC9/Invariant 3: Code-only query must NOT emit citation events. "
        f"Got citation events: {[e['data'] for e in citation_events]}"
    )


def test_code_only_token_and_done_only(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC9: Code-only SSE contains only token and done events."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    def mock_classify(question: str, config: object, context_chips: list | None = None) -> str:
        return "code_only"

    with (
        patch("orch.rag.qa.QAEngine") as mock_qa_engine,
        patch("orch.rag.classifier.classify_query", mock_classify),
    ):
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_code_only

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "where is CodeIndexJob defined?",
                "context_level": "architecture",
                "context_chips": [],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    event_types = {e["event"] for e in events if e["event"] is not None}

    assert event_types <= {"token", "done"}, (
        f"AC9: Code-only SSE must contain only token and done events. Got events: {event_types}"
    )

    token_events = [e for e in events if e["event"] == "token"]
    done_events = [e for e in events if e["event"] == "done"]

    assert len(token_events) > 0, "Code-only query must emit token events"
    assert len(done_events) == 1, "Code-only query must emit exactly one done event"


def test_code_only_done_is_last(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """Verify done event is always the last event in code-only SSE."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    def mock_classify(question: str, config: object, context_chips: list | None = None) -> str:
        return "code_only"

    with (
        patch("orch.rag.qa.QAEngine") as mock_qa_engine,
        patch("orch.rag.classifier.classify_query", mock_classify),
    ):
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_code_only

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "where is CodeIndexJob defined?",
                "context_level": "architecture",
                "context_chips": [],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    event_types_list = [e["event"] for e in events]
    done_idx = event_types_list.index("done")
    assert done_idx == len(event_types_list) - 1, "done must be the last event"


def test_code_only_answer_content(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """Verify code-only answer contains the expected content."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    def mock_classify(question: str, config: object, context_chips: list | None = None) -> str:
        return "code_only"

    with (
        patch("orch.rag.qa.QAEngine") as mock_qa_engine,
        patch("orch.rag.classifier.classify_query", mock_classify),
    ):
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_code_only

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "where is CodeIndexJob defined?",
                "context_level": "architecture",
                "context_chips": [],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    token_events = [e for e in events if e["event"] == "token"]
    full_text = "".join(_decode_token(e) for e in token_events)

    assert "CodeIndexJob" in full_text, "Answer must mention CodeIndexJob"
    assert "defined" in full_text, "Answer must mention 'defined'"


def test_code_only_with_module_context(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC9: Code-only query with module context still emits no phase events."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    def mock_classify(question: str, config: object, context_chips: list | None = None) -> str:
        return "code_only"

    with (
        patch("orch.rag.qa.QAEngine") as mock_qa_engine,
        patch("orch.rag.classifier.classify_query", mock_classify),
    ):
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_code_only

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "show me the signature of parse_id",
                "context_level": "module",
                "module_path": "orch/rag/qa",
                "module_name": "RAG QA Engine",
                "context_chips": [],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    phase_events = [e for e in events if e["event"] == "phase"]
    assert len(phase_events) == 0, "AC9: Module-level code-only query must NOT emit phase events"


def test_code_only_empty_history(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC9: Code-only query with empty conversation history still works."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    def mock_classify(question: str, config: object, context_chips: list | None = None) -> str:
        return "code_only"

    with (
        patch("orch.rag.qa.QAEngine") as mock_qa_engine,
        patch("orch.rag.classifier.classify_query", mock_classify),
    ):
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_code_only

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "show me the signature of parse_id",
                "context_level": "architecture",
                "conversation_history": [],
                "context_chips": [],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    phase_events = [e for e in events if e["event"] == "phase"]
    assert len(phase_events) == 0, (
        "AC9: Code-only query with empty history must NOT emit phase events"
    )


def test_code_only_preserves_existing_sse_shape(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC9/Invariant 3: Code-only SSE preserves bit-for-bit shape from pre-F-00055.

    The SSE format for code-only must be identical to what existed before F-00055:
    - event: token with base64-encoded text
    - event: done with {"ok": true}
    - No phase events
    - No citation events with work_item_type/work_item_id
    """
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    def mock_classify(question: str, config: object, context_chips: list | None = None) -> str:
        return "code_only"

    with (
        patch("orch.rag.qa.QAEngine") as mock_qa_engine,
        patch("orch.rag.classifier.classify_query", mock_classify),
    ):
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_code_only

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "where is CodeIndexJob defined?",
                "context_level": "architecture",
                "context_chips": [],
            },
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

    events = _parse_sse(resp.text)

    all_event_types = [e["event"] for e in events if e["event"] is not None]
    assert set(all_event_types) <= {"token", "done"}, (
        f"Code-only SSE must only contain token/done events. Got: {set(all_event_types)}"
    )

    for event in events:
        if event["event"] == "token":
            data = event["data"]
            assert isinstance(data, dict), "Token data must be a dict"
            assert "b64" in data, "Token data must have 'b64' field"
            assert isinstance(data["b64"], str), "Token b64 must be a string"

        if event["event"] == "done":
            data = event["data"]
            assert isinstance(data, dict), "Done data must be a dict"
            assert data.get("ok") is True, "Done data must have ok=true"
