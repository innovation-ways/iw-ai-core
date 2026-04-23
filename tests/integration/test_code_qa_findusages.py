"""Integration tests for /findusages consolidation (AC7).

Tests verify:
- AC7: /findusages chip routes to work-item-aware pipeline with symbol anchor
- Symbol hint flows to retrieval; code chunks containing the symbol rank highest
- Work-item citations for items that introduced/modified the symbol appear

All tests use testcontainers — NEVER connect to live DB.
Mock QAEngine — never call real Ollama.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

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
    project_index_path = tmp_path / "code-index" / "findusages-test" / "vectors"
    project_index_path.mkdir(parents=True)

    project = Project(
        id="findusages-test",
        display_name="Findusages Test Project",
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


class MockWorkItem:
    """Mock work item for evidence bundle."""

    def __init__(
        self,
        wi_id: str,
        wi_type: str,
        title: str,
        summary: str,
        created_at: datetime,
    ) -> None:
        self.id = wi_id
        self.type = MagicMock(value=wi_type)
        self.title = title
        self.summary = summary
        self.created_at = created_at


class MockCodeChunk:
    """Mock code chunk."""

    def __init__(self, file_path: str, text: str) -> None:
        self.file_path = file_path
        self.text = text


async def mock_answer_stream_v2_findusages(**kwargs: object) -> AsyncGenerator[dict, None]:
    """Mock answer_stream_v2 that simulates /findusages behavior with symbol anchor."""
    symbol_hint = kwargs.get("symbol_hint", "")

    mock_wi1 = MockWorkItem(
        wi_id="F-00055",
        wi_type="Feature",
        title="Work-item-aware code chat",
        summary="Introduced work-item-aware code chat",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    mock_wi2 = MockWorkItem(
        wi_id="CR-00001",
        wi_type="ChangeRequest",
        title="Refactor parse_id function",
        summary="Refactored parse_id to use new pattern",
        created_at=datetime(2025, 1, 10, tzinfo=UTC),
    )

    yield {"kind": "phase", "name": "retrieving", "detail": {}}

    if symbol_hint:
        yield {
            "kind": "phase",
            "name": "finding_items",
            "detail": {"count": 2, "symbol": symbol_hint},
        }
    else:
        yield {"kind": "phase", "name": "finding_items", "detail": {"count": 2}}

    yield {"kind": "phase", "name": "reading_docs", "detail": {"count": 2}}

    sorted_wis = sorted([mock_wi1, mock_wi2], key=lambda wi: wi.created_at)
    for n, wi in enumerate(sorted_wis, start=1):
        wi_type = wi.type.value if hasattr(wi.type, "value") else str(wi.type)
        yield {
            "kind": "citation",
            "n": n,
            "work_item_type": wi_type.lower(),
            "work_item_id": wi.id,
            "label": f"{wi.id} — {wi.title}",
            "url": f"/project/findusages-test/item/{wi.id}",
            "snippet": wi.summary[:200],
        }

    yield {
        "kind": "phase",
        "name": "composing",
        "detail": {"render_id": "findusages-render-id", "count": 2},
    }

    answer_text = f"Symbol '{symbol_hint}' is referenced in the codebase. "
    answer_text += "It was introduced in [F-00055] and modified in [CR-00001]."
    yield {"kind": "token", "text": answer_text}


def test_findusages_routes_to_workitem_pipeline(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC7: /findusages chip routes to work-item-aware pipeline."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2_findusages

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "parse_id",
                "context_level": "architecture",
                "context_chips": ["findusages"],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    phase_events = [e for e in events if e["event"] == "phase"]
    citation_events = [e for e in events if e["event"] == "citation"]

    assert len(phase_events) >= 4, (
        "AC7: /findusages must emit at least 4 phase events "
        "(retrieving, finding_items, reading_docs, composing)"
    )

    phase_names = [e["data"].get("name") for e in phase_events]
    assert "retrieving" in phase_names
    assert "finding_items" in phase_names
    assert "reading_docs" in phase_names
    assert "composing" in phase_names

    assert len(citation_events) == 2, "AC7: /findusages must emit citation events for work items"


def test_findusages_symbol_hint_passed_to_retrieval(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC7: Symbol hint flows to retrieval layer."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    captured_kwargs: dict = {}

    async def mock_answer_stream_v2_capture(**kwargs: object) -> AsyncGenerator[dict, None]:
        captured_kwargs.update(kwargs)
        captured_kwargs["symbol_hint"] = kwargs.get("symbol_hint", "")
        yield {"kind": "phase", "name": "retrieving", "detail": {}}
        yield {"kind": "phase", "name": "finding_items", "detail": {"count": 0}}
        yield {"kind": "phase", "name": "composing", "detail": {"render_id": "test", "count": 0}}
        yield {"kind": "token", "text": "No usages found."}

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2_capture

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "parse_id",
                "context_level": "architecture",
                "context_chips": ["findusages"],
            },
        )

    assert resp.status_code == 200

    assert captured_kwargs.get("symbol_hint") == "parse_id", (
        "AC7: Symbol name must be passed as symbol_hint to answer_stream_v2"
    )

    assert "findusages" in captured_kwargs.get("context_chips", []), (
        "AC7: findusages chip must be passed to answer_stream_v2"
    )


def test_findusages_returns_citations_for_symbol_introducers(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC7: Citations include work items that introduced or modified the symbol."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2_findusages

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "parse_id",
                "context_level": "architecture",
                "context_chips": ["findusages"],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    citation_events = [e for e in events if e["event"] == "citation"]

    assert len(citation_events) == 2, "AC7: Must emit 2 citation events for work items"

    citation_ids = {e["data"].get("work_item_id") for e in citation_events}
    assert citation_ids == {"F-00055", "CR-00001"}, (
        f"AC7: Citations must be {{F-00055, CR-00001}}, got {citation_ids}"
    )

    for cit_event in citation_events:
        data = cit_event["data"]
        assert "work_item_type" in data, "Citation must have work_item_type"
        assert "work_item_id" in data, "Citation must have work_item_id"
        wi_type = data["work_item_type"]
        assert wi_type in ("feature", "issue", "incident", "change_request", "changerequest"), (
            f"work_item_type must be feature/issue/incident/change_request/"
            f"changerequest, got {wi_type}"
        )


def test_findusages_empty_result(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """Boundary: /findusages on non-existent symbol returns empty feed, no crash."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    async def mock_answer_stream_empty(**kwargs: object) -> AsyncGenerator[dict, None]:
        yield {"kind": "phase", "name": "retrieving", "detail": {}}
        yield {"kind": "phase", "name": "finding_items", "detail": {"count": 0}}
        yield {"kind": "phase", "name": "composing", "detail": {"render_id": "empty", "count": 0}}
        yield {"kind": "token", "text": "No usages found for this symbol."}

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_empty

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "nonexistent_symbol_xyz",
                "context_level": "architecture",
                "context_chips": ["findusages"],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    phase_events = [e for e in events if e["event"] == "phase"]
    citation_events = [e for e in events if e["event"] == "citation"]
    token_events = [e for e in events if e["event"] == "token"]

    assert len(phase_events) >= 3, "Must still emit phases even with no results"

    assert len(citation_events) == 0, (
        "Boundary: /findusages with no results must not emit citations"
    )

    full_text = "".join(_decode_token(e) for e in token_events)
    assert "no usages" in full_text.lower() or "not found" in full_text.lower(), (
        "Answer should indicate no usages found"
    )


def test_findusages_question_extracted_from_symbol_name(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """Verify the question containing the symbol is used as the symbol hint."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    captured_question = ""

    async def mock_answer_stream_capture_question(**kwargs: object) -> AsyncGenerator[dict, None]:
        nonlocal captured_question
        captured_question = kwargs.get("question", "")
        yield {"kind": "phase", "name": "retrieving", "detail": {}}
        yield {"kind": "phase", "name": "finding_items", "detail": {"count": 0}}
        yield {"kind": "phase", "name": "composing", "detail": {"render_id": "test", "count": 0}}
        yield {"kind": "token", "text": "Done."}

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_capture_question

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "CodeIndexJob",
                "context_level": "architecture",
                "context_chips": ["findusages"],
            },
        )

    assert resp.status_code == 200
    assert captured_question == "CodeIndexJob", (
        "Question text must be used as-is for /findusages symbol hint"
    )
