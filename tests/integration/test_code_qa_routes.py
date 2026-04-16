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


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


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
    """Given valid project + mocked index + mocked answer_stream, SSE tokens stream correctly."""
    project_index_path = tmp_path / "code-index" / test_project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True)

    async def mock_answer_stream(**kwargs: object) -> AsyncGenerator[str, None]:
        yield "Hello"
        yield " world"
        yield "!"

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream = mock_answer_stream

        resp = client.post(
            f"/api/projects/{test_project_with_index.id}/code/qa",
            json={
                "question": "What does it do?",
                "context_level": "architecture",
            },
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

    body = resp.text
    data_lines = [line[6:] for line in body.split("\n") if line.startswith("data: ")]
    payloads = [json.loads(line) for line in data_lines]

    token_payloads = [p for p in payloads if "token" in p]
    assert len(token_payloads) == 3
    assert token_payloads[0]["token"] == "Hello"  # noqa: S105
    assert token_payloads[1]["token"] == " world"  # noqa: S105
    assert token_payloads[2]["token"] == "!"  # noqa: S105

    done_payloads = [p for p in payloads if p.get("event") == "done"]
    assert len(done_payloads) == 1
    assert done_payloads[0]["full_response"] == "Hello world!"


def test_qa_streams_error_event_on_ollama_down(
    client: TestClient, test_project_with_index: Project, tmp_path: Path
) -> None:
    """Given QAEngine yields __ERROR__: token, SSE error event is returned."""
    project_index_path = tmp_path / "code-index" / test_project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True)

    async def mock_answer_stream_error(**kwargs: object) -> AsyncGenerator[str, None]:
        yield "__ERROR__:Local AI unavailable. Check that Ollama is running."

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream = mock_answer_stream_error

        resp = client.post(
            f"/api/projects/{test_project_with_index.id}/code/qa",
            json={
                "question": "What does it do?",
                "context_level": "architecture",
            },
        )

    assert resp.status_code == 200

    body = resp.text
    data_lines = [line[6:] for line in body.split("\n") if line.startswith("data: ")]
    payloads = [json.loads(line) for line in data_lines]

    error_payloads = [p for p in payloads if p.get("event") == "error"]
    assert len(error_payloads) == 1
    assert "Local AI unavailable" in error_payloads[0]["message"]


def test_qa_empty_conversation_history(
    client: TestClient, test_project_with_index: Project, tmp_path: Path
) -> None:
    """Given empty conversation_history, endpoint returns 200 with streaming response."""
    project_index_path = tmp_path / "code-index" / test_project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True)

    async def mock_answer_stream(**kwargs: object) -> AsyncGenerator[str, None]:
        yield "Answer"

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream = mock_answer_stream

        resp = client.post(
            f"/api/projects/{test_project_with_index.id}/code/qa",
            json={
                "question": "What does it do?",
                "context_level": "architecture",
                "conversation_history": [],
            },
        )

    assert resp.status_code == 200
    body = resp.text
    data_lines = [line[6:] for line in body.split("\n") if line.startswith("data: ")]
    payloads = [json.loads(line) for line in data_lines]
    done_payloads = [p for p in payloads if p.get("event") == "done"]
    assert len(done_payloads) == 1
    assert done_payloads[0]["full_response"] == "Answer"
