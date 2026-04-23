"""Integration tests for POST /api/projects/{project_id}/code/qa SSE endpoint.

Tests verify:
- 404 when project not found
- 404 when LanceDB index does not exist
- 422 on Pydantic validation failures (empty question, question too long, invalid context_level)
- SSE token streaming with mocked QAEngine
- SSE error event when QAEngine yields __ERROR__ token
- SSE error event on ConnectionRefusedError

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
def test_project_with_index(db_session: Session, tmp_path: Path) -> Project:
    """Insert a Project row with code_understanding config using tmp_path for index."""
    project = Project(
        id="test-proj",
        display_name="Test Project",
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


@pytest.fixture
def test_project(db_session: Session) -> Project:
    """Insert a Project row with code_understanding config."""
    project = Project(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        config={
            "code_understanding": {
                "provider": "local",
                "index_tier": "balanced",
                "ollama_url": "http://localhost:11434",
                "index_path": "/tmp/nonexistent-test-index",  # noqa: S108
            }
        },
    )
    db_session.add(project)
    db_session.flush()
    return project


def test_qa_project_not_found(client: TestClient) -> None:
    """Given a project_id that does not exist in the DB, returns HTTP 404."""
    resp = client.post(
        "/api/projects/nonexistent-project/code/qa",
        json={
            "question": "What does it do?",
            "context_level": "architecture",
        },
    )
    assert resp.status_code == 404
    assert "Project not found" in resp.json()["detail"]


def test_qa_no_index_found(client: TestClient, test_project: Project) -> None:
    """Given a valid project but no LanceDB index on disk, returns HTTP 404."""
    resp = client.post(
        f"/api/projects/{test_project.id}/code/qa",
        json={
            "question": "What does it do?",
            "context_level": "architecture",
        },
    )
    assert resp.status_code == 404
    assert "No code index found" in resp.json()["detail"]


def test_qa_validation_empty_question(client: TestClient, test_project: Project) -> None:
    """Given question = '', returns HTTP 422 (Pydantic validation failure)."""
    resp = client.post(
        f"/api/projects/{test_project.id}/code/qa",
        json={
            "question": "",
            "context_level": "architecture",
        },
    )
    assert resp.status_code == 422


def test_qa_validation_question_too_long(client: TestClient, test_project: Project) -> None:
    """Given question > 1000 chars, returns HTTP 422."""
    resp = client.post(
        f"/api/projects/{test_project.id}/code/qa",
        json={
            "question": "x" * 1001,
            "context_level": "architecture",
        },
    )
    assert resp.status_code == 422


def test_qa_validation_invalid_context_level(client: TestClient, test_project: Project) -> None:
    """Given context_level = 'symbol', returns HTTP 422."""
    resp = client.post(
        f"/api/projects/{test_project.id}/code/qa",
        json={
            "question": "What does it do?",
            "context_level": "symbol",
        },
    )
    assert resp.status_code == 422


def test_qa_streams_tokens(
    client: TestClient, test_project_with_index: Project, tmp_path: Path
) -> None:
    """Given valid project + mocked index + mocked answer_stream_v2, SSE tokens stream correctly."""
    project_index_path = tmp_path / "code-index" / test_project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True)

    async def mock_answer_stream_v2(**kwargs: object) -> AsyncGenerator[dict[str, object], None]:
        yield {"kind": "token", "text": "Hello"}
        yield {"kind": "token", "text": " world"}
        yield {"kind": "token", "text": "!"}

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2

        resp = client.post(
            f"/api/projects/{test_project_with_index.id}/code/qa",
            json={
                "question": "What does it do?",
                "context_level": "architecture",
            },
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

    events = _parse_sse(resp.text)

    token_events = [e for e in events if e["event"] == "token"]
    assert len(token_events) == 3
    assert _decode_token(token_events[0]) == "Hello"
    assert _decode_token(token_events[1]) == " world"
    assert _decode_token(token_events[2]) == "!"

    done_events = [e for e in events if e["event"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["data"] == {"ok": True}


def test_qa_streams_error_event_on_ollama_down(
    client: TestClient, test_project_with_index: Project, tmp_path: Path
) -> None:
    """Given QAEngine yields __ERROR__: token, SSE error event is returned."""
    project_index_path = tmp_path / "code-index" / test_project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True)

    async def mock_answer_stream_v2_error(
        **kwargs: object,
    ) -> AsyncGenerator[dict[str, object], None]:
        yield {"kind": "error", "message": "Local AI unavailable. Check that Ollama is running."}

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2_error

        resp = client.post(
            f"/api/projects/{test_project_with_index.id}/code/qa",
            json={
                "question": "What does it do?",
                "context_level": "architecture",
            },
        )

    assert resp.status_code == 200

    events = _parse_sse(resp.text)
    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    error_data = error_events[0]["data"]
    assert isinstance(error_data, dict)
    assert "Local AI unavailable" in error_data["message"]


def test_qa_empty_conversation_history(
    client: TestClient, test_project_with_index: Project, tmp_path: Path
) -> None:
    """Given empty conversation_history, endpoint returns 200 with streaming response."""
    project_index_path = tmp_path / "code-index" / test_project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True)

    async def mock_answer_stream_v2(**kwargs: object) -> AsyncGenerator[dict[str, object], None]:
        yield {"kind": "token", "text": "Answer"}

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2

        resp = client.post(
            f"/api/projects/{test_project_with_index.id}/code/qa",
            json={
                "question": "What does it do?",
                "context_level": "architecture",
                "conversation_history": [],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    token_events = [e for e in events if e["event"] == "token"]
    assert len(token_events) == 1
    assert _decode_token(token_events[0]) == "Answer"
    done_events = [e for e in events if e["event"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["data"] == {"ok": True}


def test_post_qa_with_module_name_forwards_to_engine(
    client: TestClient, test_project_with_index: Project, tmp_path: Path
) -> None:
    """AC7: module_name is forwarded to the QAEngine spy."""
    project_index_path = tmp_path / "code-index" / test_project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True)

    captured_kwargs: dict = {}

    async def mock_answer_stream_v2(**kwargs: object) -> AsyncGenerator[dict[str, object], None]:
        captured_kwargs.update(kwargs)
        yield {"kind": "token", "text": "Answer"}

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2

        resp = client.post(
            f"/api/projects/{test_project_with_index.id}/code/qa",
            json={
                "question": "What does it do?",
                "context_level": "module",
                "module_path": "orch/daemon/",
                "module_name": "Orchestration Daemon",
            },
        )

    assert resp.status_code == 200
    assert captured_kwargs.get("module_name") == "Orchestration Daemon"


def test_post_qa_without_module_name_still_accepted(
    client: TestClient, test_project_with_index: Project, tmp_path: Path
) -> None:
    """AC7: Request without module_name is accepted and None is forwarded."""
    project_index_path = tmp_path / "code-index" / test_project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True)

    captured_kwargs: dict = {}

    async def mock_answer_stream(**kwargs: object) -> AsyncGenerator[str, None]:
        captured_kwargs.update(kwargs)
        yield "Answer"

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream = mock_answer_stream

        resp = client.post(
            f"/api/projects/{test_project_with_index.id}/code/qa",
            json={
                "question": "What does it do?",
                "context_level": "module",
                "module_path": "orch/daemon/",
            },
        )

    assert resp.status_code == 200
    assert captured_kwargs.get("module_name") is None


def test_post_qa_with_module_name_null_still_accepted(
    client: TestClient, test_project_with_index: Project, tmp_path: Path
) -> None:
    """AC7: Request with explicit module_name=null is accepted and None is forwarded."""
    project_index_path = tmp_path / "code-index" / test_project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True)

    captured_kwargs: dict = {}

    async def mock_answer_stream(**kwargs: object) -> AsyncGenerator[str, None]:
        captured_kwargs.update(kwargs)
        yield "Answer"

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream = mock_answer_stream

        resp = client.post(
            f"/api/projects/{test_project_with_index.id}/code/qa",
            json={
                "question": "What does it do?",
                "context_level": "module",
                "module_path": "orch/daemon/",
                "module_name": None,
            },
        )

    assert resp.status_code == 200
    assert captured_kwargs.get("module_name") is None
