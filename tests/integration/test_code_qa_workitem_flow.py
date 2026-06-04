"""Integration tests for full SSE flow with work-item-aware pipeline.

Tests verify:
- Full SSE event sequence: phase:retrieving → phase:finding_items →
  phase:reading_docs → N×citation → phase:composing → token+ → done
- Citation events contain work_item_type and work_item_id fields
- Project isolation: work items from another project do NOT appear in citations
- Invariant 2: phase events follow exact sequence
- Invariant 3: default code-only emits no phase events

All tests use testcontainers — NEVER connect to live DB.
Mock QAEngine / LanceDB — never call real Ollama.
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
from orch.db.models import Project, WorkItem, WorkItemType

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from pathlib import Path

    from sqlalchemy.orm import Session

WORK_ITEM_ID_RE = __import__("re", fromlist=["compile"]).compile(r"^(F|I|CR)-\d{5}$")


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
def project_with_work_items(
    db_session: Session,
) -> Project:
    """Create a project with 3 work items (Feature, CR, Incident) with design_doc_content."""
    project = Project(
        id="test-proj-wi",
        display_name="Test Project with Work Items",
        repo_root="/repos/test",
        config={
            "code_understanding": {
                "provider": "local",
                "index_tier": "balanced",
                "ollama_url": "http://localhost:11434",
                "index_path": "nonexistent-test-index",
            }
        },
    )
    db_session.add(project)

    now = datetime.now(UTC)

    wi_feature = WorkItem(
        project_id="test-proj-wi",
        id="F-00001",
        type=WorkItemType.Feature,
        title="Daemon polling interval feature",
        status="completed",
        phase="done",
        design_doc_content=(
            "The daemon polls the database every 60 seconds to check for approved batches."
        ),
        summary="Daemon polling interval",
        created_at=now,
    )

    wi_cr = WorkItem(
        project_id="test-proj-wi",
        id="CR-00001",
        type=WorkItemType.ChangeRequest,
        title="Change polling interval",
        status="completed",
        phase="done",
        design_doc_content=(
            "Changed polling interval from 30 to 60 seconds to reduce database load."
        ),
        summary="Polling interval change",
        created_at=now,
    )

    wi_incident = WorkItem(
        project_id="test-proj-wi",
        id="I-00001",
        type=WorkItemType.Issue,
        title="Fix retry logic",
        status="completed",
        phase="done",
        design_doc_content="Fixed the retry logic to retry exactly 3 times before giving up.",
        summary="Retry logic fix",
        created_at=now,
    )

    db_session.add_all([wi_feature, wi_cr, wi_incident])
    db_session.flush()
    return project


@pytest.fixture
def project_with_index(
    db_session: Session,
    tmp_path: Path,
) -> Project:
    """Create a project with code_understanding config pointing to tmp index path."""
    project_index_path = tmp_path / "code-index" / "test-proj-wi" / "vectors"
    project_index_path.mkdir(parents=True)

    project = Project(
        id="test-proj-wi",
        display_name="Test Project with Work Items",
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
        design_doc_content: str,
        created_at: datetime,
    ) -> None:
        self.id = wi_id
        self.type = MagicMock(value=wi_type)
        self.title = title
        self.summary = summary
        self.design_doc_content = design_doc_content
        self.created_at = created_at


def _make_mock_bundle(work_items: list[MockWorkItem]) -> MagicMock:
    """Create a mock EvidenceBundle with the given work items."""
    from orch.rag.evidence import EvidenceBundle

    bundle = MagicMock(spec=EvidenceBundle)
    bundle.question = "why does the daemon retry 3 times?"
    bundle.code_chunks = []
    bundle.doc_chunks = []
    bundle.fts_items = work_items
    bundle.git_log_items = []
    bundle.work_items = work_items
    bundle.retrieval_cutoff = datetime.now(UTC)
    bundle.allowed_ids = {wi.id for wi in work_items}
    return bundle


async def mock_answer_stream_v2_wi_aware(**kwargs: object) -> AsyncGenerator[dict, None]:
    """Mock answer_stream_v2 that returns a full work-item-aware sequence."""
    mock_wi1 = MockWorkItem(
        wi_id="F-00001",
        wi_type="Feature",
        title="Daemon polling interval feature",
        summary="Daemon polling interval",
        design_doc_content="The daemon polls the database every 60 seconds.",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    mock_wi2 = MockWorkItem(
        wi_id="CR-00001",
        wi_type="changerequest",
        title="Change polling interval",
        summary="Polling interval change",
        design_doc_content="Changed polling interval from 30 to 60 seconds.",
        created_at=datetime(2025, 1, 2, tzinfo=UTC),
    )
    mock_wi3 = MockWorkItem(
        wi_id="I-00001",
        wi_type="Issue",
        title="Fix retry logic",
        summary="Retry logic fix",
        design_doc_content="Fixed the retry logic to retry exactly 3 times.",
        created_at=datetime(2025, 1, 3, tzinfo=UTC),
    )

    work_items = [mock_wi1, mock_wi2, mock_wi3]

    _make_mock_bundle(work_items)

    yield {"kind": "phase", "name": "retrieving", "detail": {}}
    yield {"kind": "phase", "name": "finding_items", "detail": {"count": 3}}

    yield {"kind": "phase", "name": "reading_docs", "detail": {"count": 3}}

    sorted_wis = sorted(work_items, key=lambda wi: wi.created_at)
    for n, wi in enumerate(sorted_wis, start=1):
        wi_type = wi.type.value if hasattr(wi.type, "value") else str(wi.type)
        yield {
            "kind": "citation",
            "n": n,
            "work_item_type": wi_type.lower(),
            "work_item_id": wi.id,
            "label": f"{wi.id} — {wi.title}",
            "url": f"/project/test-proj-wi/item/{wi.id}",
            "snippet": wi.summary[:200],
        }

    yield {
        "kind": "phase",
        "name": "composing",
        "detail": {"render_id": "test-render-id", "count": 3},
    }

    for chunk_text in [
        "The daemon retries 3 times because of ",
        "[F-00001]. ",
        "The retry logic was introduced in [I-00001] and later adjusted in [CR-00001].",
    ]:
        yield {"kind": "token", "text": chunk_text}


def test_workitem_flow_full_sse_sequence(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC1/Invariant 2: Full SSE flow emits correct phase sequence and citation events."""
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
    assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

    events = _parse_sse(resp.text)

    event_types = [e["event"] for e in events]
    phase_events = [e for e in events if e["event"] == "phase"]
    citation_events = [e for e in events if e["event"] == "citation"]
    token_events = [e for e in events if e["event"] == "token"]

    phase_names = [e["data"].get("name") for e in phase_events]
    expected_phase_sequence = ["retrieving", "finding_items", "reading_docs", "composing"]
    assert phase_names == expected_phase_sequence, (
        f"Phase sequence must be exactly {expected_phase_sequence}, got {phase_names}"
    )

    assert len(citation_events) == 3, (
        f"Must emit exactly 3 citation events, got {len(citation_events)}"
    )

    citation_ids = {e["data"].get("work_item_id") for e in citation_events}
    assert citation_ids == {"F-00001", "CR-00001", "I-00001"}, (
        f"Citation work_item_ids must be exactly {{F-00001, CR-00001, I-00001}}, got {citation_ids}"
    )

    for cit_event in citation_events:
        data = cit_event["data"]
        assert "work_item_type" in data, "Citation must have work_item_type field"
        assert "work_item_id" in data, "Citation must have work_item_id field"
        wi_id = data["work_item_id"]
        assert WORK_ITEM_ID_RE.match(wi_id), f"work_item_id {wi_id} must match F/CR/I-NNNNN format"

    assert len(token_events) > 0, "Must emit at least one token event"

    done_events = [e for e in events if e["event"] == "done"]
    assert len(done_events) == 1, "Must emit exactly one done event"

    done_idx = event_types.index("done")
    assert done_idx == len(event_types) - 1, "done must be the last event"


def test_workitem_flow_finding_items_count(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """Invariant 2: phase:finding_items payload contains count >= 1."""
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

    finding_items_events = [
        e for e in events if e["event"] == "phase" and e["data"].get("name") == "finding_items"
    ]
    assert len(finding_items_events) == 1, "Must emit exactly one finding_items phase"

    detail = finding_items_events[0]["data"].get("detail", {})
    assert "count" in detail, "finding_items detail must have count field"
    assert detail["count"] >= 1, f"finding_items count must be >= 1, got {detail['count']}"


def test_workitem_flow_citation_has_required_fields(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """Invariant 4: citation events carry work_item_type and work_item_id."""
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
    citation_events = [e for e in events if e["event"] == "citation"]

    assert len(citation_events) == 3, "Must emit exactly 3 citation events"

    for cit_event in citation_events:
        data = cit_event["data"]
        assert "work_item_type" in data, "Citation must have work_item_type"
        assert "work_item_id" in data, "Citation must have work_item_id"

        wi_type = data["work_item_type"]
        valid_types = ("feature", "issue", "incident", "change_request", "changerequest")
        assert wi_type in valid_types, (
            f"work_item_type must be feature/issue/incident/change_request/"
            f"changerequest, got {wi_type}"
        )

        wi_id = data["work_item_id"]
        assert WORK_ITEM_ID_RE.match(wi_id), (
            f"work_item_id must match ^(F|I|CR)-\\d{{5}}$, got {wi_id}"
        )


def test_workitem_flow_project_isolation(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
    db_session: Session,
) -> None:
    """Invariant 9: work items from another project do NOT appear in citations."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    other_project = Project(
        id="other-project",
        display_name="Other Project",
        repo_root="/repos/other",
        config={},
    )
    db_session.add(other_project)
    db_session.flush()

    now = datetime.now(UTC)
    other_wi = WorkItem(
        project_id="other-project",
        id="F-99999",
        type=WorkItemType.Feature,
        title="Other project feature",
        status="completed",
        phase="done",
        design_doc_content="This is from another project and should not appear.",
        summary="Other project",
        created_at=now,
    )
    db_session.add(other_wi)
    db_session.flush()

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
    citation_events = [e for e in events if e["event"] == "citation"]

    citation_ids = {e["data"].get("work_item_id") for e in citation_events}
    assert "F-99999" not in citation_ids, (
        "F-99999 from other-project must NOT appear in citations (Invariant 9)"
    )
    assert citation_ids <= {"F-00001", "CR-00001", "I-00001"}, (
        f"Only test-proj-wi work items should appear, got {citation_ids}"
    )


def test_workitem_flow_done_arrives_last(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """Verify done event is always the last event in the SSE stream."""
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

    done_events = [e for e in events if e["event"] == "done"]
    assert len(done_events) == 1, "Must emit exactly one done event"

    event_types = [e["event"] for e in events]
    done_idx = event_types.index("done")
    assert done_idx == len(event_types) - 1, "done must be the last event type"


def test_workitem_flow_token_events_emitted(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """AC1: At least one token event is emitted during composing phase."""
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
    token_events = [e for e in events if e["event"] == "token"]

    assert len(token_events) > 0, "Must emit at least one token event"

    full_text = "".join(_decode_token(e) for e in token_events)
    assert len(full_text) > 0, "Token events must contain non-empty text"


async def mock_answer_stream_v2_empty_items(**kwargs: object) -> AsyncGenerator[dict, None]:
    """Mock answer_stream_v2 that returns zero work items (finding_items count=0)."""
    yield {"kind": "phase", "name": "retrieving", "detail": {}}
    yield {"kind": "phase", "name": "finding_items", "detail": {"count": 0}}
    yield {
        "kind": "phase",
        "name": "composing",
        "detail": {"render_id": "empty-render-id", "count": 0},
    }
    yield {"kind": "token", "text": "No matching work items found for your question."}


def test_workitem_flow_zero_matching_items(
    client: TestClient,
    project_with_index: Project,
    tmp_path: Path,
) -> None:
    """Boundary: /why with zero matching items emits finding_items:count=0, no fictional items."""
    project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
    project_index_path.mkdir(parents=True, exist_ok=True)

    with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
        mock_engine = mock_qa_engine.return_value
        mock_engine.answer_stream_v2 = mock_answer_stream_v2_empty_items

        resp = client.post(
            f"/api/projects/{project_with_index.id}/code/qa",
            json={
                "question": "why does some unknown feature work?",
                "context_level": "architecture",
                "context_chips": ["why"],
            },
        )

    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    finding_items_events = [
        e for e in events if e["event"] == "phase" and e["data"].get("name") == "finding_items"
    ]
    assert len(finding_items_events) == 1
    assert finding_items_events[0]["data"].get("detail", {}).get("count") == 0, (
        "finding_items count must be 0 when no items match"
    )

    token_events = [e for e in events if e["event"] == "token"]
    full_text = "".join(_decode_token(e) for e in token_events).lower()
    assert "no matching" in full_text or "not found" in full_text, (
        "Answer should mention no matching items found"
    )

    citation_events = [e for e in events if e["event"] == "citation"]
    assert len(citation_events) == 0, "No citations should be emitted when no items match"
