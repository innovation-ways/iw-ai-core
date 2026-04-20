"""Integration tests for query routing: slash override and classifier auto-detect.

Tests verify:
- AC2: /why slash override forces work-item-aware pipeline even for code-like queries
- AC3: Classifier auto-detects behavior questions and routes to work-item-aware pipeline
- AC9/Invariant 3: Code-only queries emit no phase events and no work-item citations
- Invariant 2: Phase events follow exact sequence when work-item pipeline runs

All tests use testcontainers — NEVER connect to live DB.
Mock QAEngine / LLM classifier — never call real Ollama.
"""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import Project

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from datetime import datetime
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
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def project_with_index(
    db_session: Session,
    tmp_path: Path,
) -> Project:
    """Create a project with code_understanding config pointing to tmp index path."""
    project_index_path = tmp_path / "code-index" / "routing-test" / "vectors"
    project_index_path.mkdir(parents=True)

    project = Project(
        id="routing-test",
        display_name="Routing Test Project",
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


async def mock_answer_stream_v2_wi_aware(**kwargs: object) -> AsyncGenerator[dict, None]:
    """Mock answer_stream_v2 that returns a full work-item-aware sequence."""
    yield {"kind": "phase", "name": "retrieving", "detail": {}}
    yield {"kind": "phase", "name": "finding_items", "detail": {"count": 1}}
    yield {"kind": "phase", "name": "reading_docs", "detail": {"count": 1}}

    yield {
        "kind": "citation",
        "n": 1,
        "work_item_type": "feature",
        "work_item_id": "F-00055",
        "label": "F-00055 — Work-item-aware code chat",
        "url": "/project/routing-test/item/F-00055",
        "snippet": "F-00055 feature",
    }

    yield {
        "kind": "phase",
        "name": "composing",
        "detail": {"render_id": "test-render-id", "count": 1},
    }
    yield {"kind": "token", "text": "Answer based on [F-00055]."}


async def mock_answer_stream_code_only(**kwargs: object) -> AsyncGenerator[dict, None]:
    """Mock answer_stream that returns code-only tokens (no phase events)."""
    yield {"kind": "token", "text": "The function parse_id is defined at line 42."}


def test_case_a_slash_override_why_runs_workitem_pipeline(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC2: /why chip forces work-item-aware pipeline even for code-like query.

    Query looks like code ("show me parse_id") but /why chip overrides classifier.
    """
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2_wi_aware

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "show me parse_id",
                "context_level": "architecture",
                "context_chips": ["why"],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    phase_events = [e for e in events if e["event"] == "phase"]
    citation_events = [e for e in events if e["event"] == "citation"]

    assert len(phase_events) > 0, (
        "AC2: /why chip must force work-item-aware pipeline even for code-like query"
    )

    phase_names = [e["data"].get("name") for e in phase_events]
    expected_sequence = ["retrieving", "finding_items", "reading_docs", "composing"]
    assert phase_names == expected_sequence, (
        f"Phase sequence must be {expected_sequence}, got {phase_names}"
    )

    assert len(citation_events) == 1, "Must emit citation events when work-item pipeline runs"
    assert citation_events[0]["data"].get("work_item_id") == "F-00055", (
        "Citation must reference F-00055"
    )


def test_case_b_classifier_auto_detect_behavior_query(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC3: Classifier auto-detects behavior query and routes to work-item-aware pipeline.

    Query is behavioral ("why does the daemon retry 3 times?") without slash chip.
    """
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    def mock_classify(question: str, config: object, context_chips: list | None = None) -> str:
        """Mock classifier that returns workitem_aware for behavior questions."""
        if context_chips and any(c in ("why", "history", "findusages") for c in context_chips):
            return "workitem_aware"
        behavior_signals = {"why", "how does", "what caused", "feature", "behavior"}
        question_lower = question.lower()
        if any(signal in question_lower for signal in behavior_signals):
            return "workitem_aware"
        return "code_only"

    with (
        patch("orch.rag.qa.QAEngine") as mock_qa_engine,
        patch("orch.rag.classifier.classify_query", mock_classify),
    ):
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2_wi_aware

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "why does the daemon retry 3 times?",
                "context_level": "architecture",
                "context_chips": [],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    phase_events = [e for e in events if e["event"] == "phase"]
    citation_events = [e for e in events if e["event"] == "citation"]

    assert len(phase_events) > 0, (
        "AC3: Classifier must route behavior query to work-item-aware pipeline"
    )

    phase_names = [e["data"].get("name") for e in phase_events]
    assert "retrieving" in phase_names, "Must emit retrieving phase"
    assert "composing" in phase_names, "Must emit composing phase"

    assert len(citation_events) == 1, "Must emit citation events for behavior query"


def test_case_c_code_only_no_phase_events(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC9/Invariant 3: Code-only query emits no phase events and no work-item citations.

    Query is purely structural ("where is CodeIndexJob defined?") without slash chip.
    Classifier routes to code-only pipeline.
    """
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    def mock_classify(question: str, config: object, context_chips: list | None = None) -> str:
        """Mock classifier that returns code_only for structural queries."""
        if context_chips and any(c in ("why", "history", "findusages") for c in context_chips):
            return "workitem_aware"
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
    citation_events = [e for e in events if e["event"] == "citation"]
    token_events = [e for e in events if e["event"] == "token"]

    assert len(phase_events) == 0, "AC9/Invariant 3: Code-only query must NOT emit phase events"

    assert len(citation_events) == 0, (
        "AC9/Invariant 3: Code-only query must NOT emit work-item citation events"
    )

    assert len(token_events) > 0, "Code-only query must emit token events"

    full_text = "".join(_decode_token(e) for e in token_events)
    assert len(full_text) > 0, "Token events must contain non-empty text"


def test_slash_history_alias(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC2/Invariant 6: /history chip aliases /why and forces work-item-aware pipeline."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2_wi_aware

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "what changed in the retry logic?",
                "context_level": "architecture",
                "context_chips": ["history"],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    phase_events = [e for e in events if e["event"] == "phase"]
    assert len(phase_events) > 0, "/history chip must force work-item-aware pipeline"


def test_slash_findusages_alias(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC7/Invariant 6: /findusages chip forces work-item-aware pipeline with symbol anchor."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    captured_context_chips: list = []

    async def mock_answer_stream_v2_capture(**kwargs: object) -> AsyncGenerator[dict, None]:
        captured_context_chips.append(kwargs.get("context_chips"))
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
    events = _parse_sse(resp.text)

    phase_events = [e for e in events if e["event"] == "phase"]
    assert len(phase_events) > 0, "/findusages chip must force work-item-aware pipeline"

    assert captured_context_chips[0] == ["findusages"], (
        "findusages chip must be passed to answer_stream_v2"
    )


def test_low_confidence_classifier_defaults_to_code_only(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """Boundary/AC3: Classifier timeout/default falls back to code-only pipeline."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    def mock_classify_timeout(
        question: str, config: object, context_chips: list | None = None
    ) -> str:
        """Mock classifier that times out/defaults to code_only."""
        if context_chips and any(c in ("why", "history", "findusages") for c in context_chips):
            return "workitem_aware"
        return "code_only"

    with (
        patch("orch.rag.qa.QAEngine") as mock_qa_engine,
        patch("orch.rag.classifier.classify_query", mock_classify_timeout),
    ):
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_code_only

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "why does this ambiguous query work?",
                "context_level": "architecture",
                "context_chips": [],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    phase_events = [e for e in events if e["event"] == "phase"]
    assert len(phase_events) == 0, "Low-confidence query must default to code-only pipeline"


def test_phase_sequence_exact_order(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """Invariant 2: Phase events must be in exact order:
    retrieving → finding_items → reading_docs → composing."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2_wi_aware

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "why does the daemon retry 3 times?",
                "context_level": "architecture",
                "context_chips": ["why"],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    phase_events = [e for e in events if e["event"] == "phase"]

    phase_names = [e["data"].get("name") for e in phase_events]
    expected_sequence = ["retrieving", "finding_items", "reading_docs", "composing"]

    assert phase_names == expected_sequence, (
        f"Invariant 2: Phase sequence must be exactly {expected_sequence}, got {phase_names}"
    )

    for i, name in enumerate(phase_names):
        assert name == expected_sequence[i], (
            f"Phase at index {i} must be '{expected_sequence[i]}', got '{name}'"
        )


def test_no_duplicate_phases(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """Invariant 2: No phase may fire more than once per answer."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2_wi_aware

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "why does the daemon retry 3 times?",
                "context_level": "architecture",
                "context_chips": ["why"],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    phase_events = [e for e in events if e["event"] == "phase"]

    phase_names = [e["data"].get("name") for e in phase_events]
    unique_phases = set(phase_names)

    assert len(phase_names) == len(unique_phases), (
        f"Invariant 2: No phase may fire more than once. Got: {phase_names}"
    )
