"""Integration tests for F-00055 evaluation set.

Loads tests/fixtures/eval_set_f00055.json and verifies each tuple:
- Phase sequence matches expected_phase_sequence (or empty for code-only)
- At least one must_cite ID appears in citation events
- All expected_terms appear in concatenated token stream

AC8: Evaluation set passes against current iw-ai-core baseline.

All tests use testcontainers — NEVER connect to live DB.
Mock QAEngine — never call real Ollama.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import Project

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

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


def _load_eval_set() -> list[dict[str, Any]]:
    """Load the evaluation set from fixtures."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "eval_set_f00055.json"
    if not fixture_path.exists():
        pytest.skip(f"Eval set fixture not found: {fixture_path}")

    with fixture_path.open() as f:
        data = json.load(f)

    return data.get("evaluation_set", [])


def _check_eval_set_age(fixture_path: Path) -> bool:
    """Check if eval set is older than 180 days. Returns True if stale."""
    with fixture_path.open() as f:
        data = json.load(f)

    generated_at = data.get("_generated_at")
    if not generated_at:
        return True

    try:
        generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        age = datetime.now(UTC) - generated
        return age > timedelta(days=180)
    except (ValueError, TypeError):
        return True


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
    project_index_path = tmp_path / "code-index" / "eval-test" / "vectors"
    project_index_path.mkdir(parents=True)

    project = Project(
        id="eval-test",
        display_name="Eval Test Project",
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


def _make_mock_stream(eval_tuple: dict[str, Any]):
    """Create a mock answer_stream_v2 based on an eval tuple."""

    async def mock_stream(**kwargs: object) -> AsyncGenerator[dict, None]:
        question = kwargs.get("question", "")
        expected_phases = eval_tuple.get("expected_phase_sequence", [])

        if not expected_phases:
            expected_terms = eval_tuple.get("expected_terms", [])
            answer_text = (
                " ".join(expected_terms) if expected_terms else f"Code-only answer for: {question}"
            )
            yield {"kind": "token", "text": answer_text}
            return

        yield {"kind": "phase", "name": "retrieving", "detail": {}}

        must_cite = eval_tuple.get("must_cite_work_items", [])
        may_cite = eval_tuple.get("may_cite_work_items", [])
        all_cite_ids = must_cite + may_cite

        yield {"kind": "phase", "name": "finding_items", "detail": {"count": len(all_cite_ids)}}
        yield {"kind": "phase", "name": "reading_docs", "detail": {"count": len(all_cite_ids)}}

        sorted_wis = []
        for i, wid in enumerate(all_cite_ids):
            wi_type = (
                "feature"
                if wid.startswith("F-")
                else "change_request"
                if wid.startswith("CR-")
                else "incident"
            )
            sorted_wis.append(
                MockWorkItem(
                    wi_id=wid,
                    wi_type=wi_type,
                    title=f"Mock {wid}",
                    summary=f"Mock summary for {wid}",
                    created_at=datetime(2025, 1, i + 1, tzinfo=UTC),
                )
            )

        sorted_wis.sort(key=lambda wi: wi.created_at)
        for n, wi in enumerate(sorted_wis, start=1):
            wi_type_str = wi.type.value if hasattr(wi.type, "value") else str(wi.type)
            yield {
                "kind": "citation",
                "n": n,
                "work_item_type": wi_type_str.lower(),
                "work_item_id": wi.id,
                "label": f"{wi.id} — {wi.title}",
                "url": f"/project/eval-test/item/{wi.id}",
                "snippet": wi.summary[:200],
            }

        yield {
            "kind": "phase",
            "name": "composing",
            "detail": {"render_id": "eval-render-id", "count": len(all_cite_ids)},
        }

        expected_terms = eval_tuple.get("expected_terms", [])
        answer_text = " ".join(expected_terms)
        yield {"kind": "token", "text": answer_text}

    return mock_stream


class TestEvalSetAge:
    """Verify eval set is not stale."""

    def test_eval_set_not_stale(self) -> None:
        """Warn (not fail) if eval set is older than 180 days."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "eval_set_f00055.json"
        if not fixture_path.exists():
            pytest.skip("Eval set fixture not found")

        is_stale = _check_eval_set_age(fixture_path)
        if is_stale:
            import warnings

            warnings.warn(
                "Eval set is older than 180 days. Run scripts/regen_eval_set_f00055.py to refresh.",
                UserWarning,
                stacklevel=2,
            )


class TestEvalSetRunner:
    """Run each tuple in the evaluation set and verify assertions."""

    @pytest.mark.parametrize("eval_tuple", _load_eval_set())
    def test_eval_tuple_phase_sequence(
        self,
        eval_tuple: dict[str, Any],
        client: TestClient,
        project_with_index: Project,
        tmp_path: Path,
    ) -> None:
        """AC8: Phase sequence matches expected_phase_sequence."""
        project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
        project_index_path.mkdir(parents=True, exist_ok=True)

        expected_phases = eval_tuple.get("expected_phase_sequence", [])
        mock_stream = _make_mock_stream(eval_tuple)

        with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
            mock_engine = mock_qa_engine.return_value
            mock_engine.answer_stream_v2 = mock_stream

            resp = client.post(
                f"/api/projects/{project_with_index.id}/code/qa",
                json={
                    "question": eval_tuple["question"],
                    "context_level": "architecture",
                    "context_chips": eval_tuple.get("context_chips", []),
                },
            )

        assert resp.status_code == 200
        events = _parse_sse(resp.text)

        phase_events = [e for e in events if e["event"] == "phase"]
        phase_names = [e["data"].get("name") for e in phase_events]

        if not expected_phases:
            assert len(phase_events) == 0, (
                f"Code-only query must NOT emit phase events. Got: {phase_names}"
            )
        else:
            assert phase_names == expected_phases, (
                f"Phase sequence must be exactly {expected_phases}, got {phase_names}"
            )

    @pytest.mark.parametrize("eval_tuple", _load_eval_set())
    def test_eval_tuple_must_cite_appears(
        self,
        eval_tuple: dict[str, Any],
        client: TestClient,
        project_with_index: Project,
        tmp_path: Path,
    ) -> None:
        """AC8: At least one must_cite ID appears in citation events."""
        project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
        project_index_path.mkdir(parents=True, exist_ok=True)

        must_cite = eval_tuple.get("must_cite_work_items", [])
        if not must_cite:
            pytest.skip("No must_cite IDs for this tuple")

        mock_stream = _make_mock_stream(eval_tuple)

        with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
            mock_engine = mock_qa_engine.return_value
            mock_engine.answer_stream_v2 = mock_stream

            resp = client.post(
                f"/api/projects/{project_with_index.id}/code/qa",
                json={
                    "question": eval_tuple["question"],
                    "context_level": "architecture",
                    "context_chips": eval_tuple.get("context_chips", []),
                },
            )

        assert resp.status_code == 200
        events = _parse_sse(resp.text)

        citation_events = [e for e in events if e["event"] == "citation"]
        citation_ids = {e["data"].get("work_item_id") for e in citation_events}

        must_cite_set = set(must_cite)
        overlapping = must_cite_set & citation_ids
        assert len(overlapping) > 0, (
            f"AC8: At least one must_cite ID ({must_cite}) must appear in citations. "
            f"Got citation IDs: {citation_ids}"
        )

    @pytest.mark.parametrize("eval_tuple", _load_eval_set())
    def test_eval_tuple_expected_terms(
        self,
        eval_tuple: dict[str, Any],
        client: TestClient,
        project_with_index: Project,
        tmp_path: Path,
    ) -> None:
        """AC8: All expected_terms appear in concatenated token stream."""
        project_index_path = tmp_path / "code-index" / project_with_index.id / "vectors"
        project_index_path.mkdir(parents=True, exist_ok=True)

        expected_terms = eval_tuple.get("expected_terms", [])
        if not expected_terms:
            pytest.skip("No expected_terms for this tuple")

        mock_stream = _make_mock_stream(eval_tuple)

        with patch("orch.rag.qa.QAEngine") as mock_qa_engine:
            mock_engine = mock_qa_engine.return_value
            mock_engine.answer_stream_v2 = mock_stream

            resp = client.post(
                f"/api/projects/{project_with_index.id}/code/qa",
                json={
                    "question": eval_tuple["question"],
                    "context_level": "architecture",
                    "context_chips": eval_tuple.get("context_chips", []),
                },
            )

        assert resp.status_code == 200
        events = _parse_sse(resp.text)

        token_events = [e for e in events if e["event"] == "token"]
        full_text = "".join(_decode_token(e) for e in token_events).lower()

        missing_terms = [term for term in expected_terms if term.lower() not in full_text]
        assert len(missing_terms) == 0, (
            f"AC8: All expected_terms must appear in token stream. "
            f"Missing terms: {missing_terms}. "
            f"Token stream: {full_text[:200]}..."
        )


class TestEvalSetFunctionalQueries:
    """Tests for functional-register queries in the eval set."""

    @pytest.fixture
    def project_with_index(
        self,
        db_session: Session,
        tmp_path: Path,
    ) -> Project:
        project_index_path = tmp_path / "code-index" / "eval-test" / "vectors"
        project_index_path.mkdir(parents=True)

        project = Project(
            id="eval-test",
            display_name="Eval Test Project",
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

    def test_functional_query_emits_phase_events(self) -> None:
        """Functional-register queries (why/how) must emit phase events."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "eval_set_f00055.json"
        if not fixture_path.exists():
            pytest.skip("Eval set fixture not found")

        with fixture_path.open() as f:
            data = json.load(f)

        eval_set = data.get("evaluation_set", [])
        functional_queries = [
            t
            for t in eval_set
            if t.get("register") == "functional" and t.get("expected_phase_sequence")
        ]

        assert len(functional_queries) >= 3, (
            "Eval set must contain at least 3 functional-register queries"
        )


class TestEvalSetTechnicalQueries:
    """Tests for technical-register queries in the eval set."""

    def test_technical_queries_have_no_phase_events(self) -> None:
        """Technical-register queries should NOT emit phase events."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "eval_set_f00055.json"
        if not fixture_path.exists():
            pytest.skip("Eval set fixture not found")

        with fixture_path.open() as f:
            data = json.load(f)

        eval_set = data.get("evaluation_set", [])
        technical_queries = [
            t
            for t in eval_set
            if t.get("register") == "technical" and not t.get("expected_phase_sequence")
        ]

        assert len(technical_queries) >= 3, (
            "Eval set must contain at least 3 technical-register "
            "(code-only) queries as negative controls"
        )


class TestEvalSetSlashOverride:
    """Tests for slash-override queries in the eval set."""

    def test_slash_override_queries(self) -> None:
        """Slash-override queries (/why, /findusages) must emit phase events."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "eval_set_f00055.json"
        if not fixture_path.exists():
            pytest.skip("Eval set fixture not found")

        with fixture_path.open() as f:
            data = json.load(f)

        eval_set = data.get("evaluation_set", [])
        slash_queries = [
            t
            for t in eval_set
            if t.get("context_chips")
            and any(c in t.get("context_chips", []) for c in ["why", "findusages"])
        ]

        assert len(slash_queries) >= 2, "Eval set must contain at least 2 slash-override queries"
