"""Unit tests for SSE phase event handling in the code_qa router."""

from __future__ import annotations

import pytest


class TestCitationTracker:
    """Tests for _CitationTracker work-item extension."""

    def test_add_work_item_valid_format(self) -> None:
        """New work-item citation returns index and stores details."""
        from dashboard.routers.code_qa import _CitationTracker

        tracker = _CitationTracker()
        idx = tracker.add_work_item("F-00042", "feature")

        assert idx == 1
        assert tracker._seen["F-00042"] == 1
        assert tracker._work_items["F-00042"] == ("feature", "F-00042")

    def test_add_work_item_duplicate_returns_none(self) -> None:
        """Duplicate work-item citation returns None."""
        from dashboard.routers.code_qa import _CitationTracker

        tracker = _CitationTracker()
        tracker.add_work_item("F-00042", "feature")
        idx = tracker.add_work_item("F-00042", "feature")

        assert idx is None

    def test_add_work_item_invalid_format_raises(self) -> None:
        """Invalid work_item_id format raises ValueError."""
        from dashboard.routers.code_qa import _CitationTracker

        tracker = _CitationTracker()

        with pytest.raises(ValueError, match="Invalid work_item_id format"):
            tracker.add_work_item("invalid-id", "feature")

        with pytest.raises(ValueError, match="Invalid work_item_id format"):
            tracker.add_work_item("F-123", "feature")

        with pytest.raises(ValueError, match="Invalid work_item_id format"):
            tracker.add_work_item("X-00042", "feature")

    @pytest.mark.parametrize(
        ("work_item_id", "expected_type"),
        [
            ("F-00042", "feature"),
            ("I-00042", "incident"),
            ("CR-00042", "change_request"),
        ],
    )
    def test_add_work_item_all_valid_types(self, work_item_id: str, expected_type: str) -> None:
        """All valid work_item_type values are accepted."""
        from dashboard.routers.code_qa import _CitationTracker

        tracker = _CitationTracker()
        idx = tracker.add_work_item(work_item_id, expected_type)

        assert idx == 1

    def test_get_work_item_returns_tuple(self) -> None:
        """get_work_item returns (type, id) tuple for seen work item."""
        from dashboard.routers.code_qa import _CitationTracker

        tracker = _CitationTracker()
        tracker.add_work_item("F-00042", "feature")
        result = tracker.get_work_item("F-00042")

        assert result == ("feature", "F-00042")

    def test_get_work_item_unknown_returns_none(self) -> None:
        """get_work_item returns None for unseen work item."""
        from dashboard.routers.code_qa import _CitationTracker

        tracker = _CitationTracker()
        result = tracker.get_work_item("F-99999")

        assert result is None

    def test_work_item_id_regex_pattern(self) -> None:
        """WORK_ITEM_ID_RE matches correct formats."""
        from dashboard.routers.code_qa import WORK_ITEM_ID_RE

        assert WORK_ITEM_ID_RE.match("F-00042")
        assert WORK_ITEM_ID_RE.match("I-12345")
        assert WORK_ITEM_ID_RE.match("CR-99999")
        assert not WORK_ITEM_ID_RE.match("f-00042")
        assert not WORK_ITEM_ID_RE.match("F00042")
        assert not WORK_ITEM_ID_RE.match("F-0042")
        assert not WORK_ITEM_ID_RE.match("X-00042")


class TestPhaseEventPayload:
    """Tests for phase event payload structure."""

    def test_phase_event_payload_structure(self) -> None:
        """Phase event dict has correct structure."""
        from orch.rag.qa import _emit_phase

        phase = _emit_phase("composing", {"render_id": "abc123", "count": 5})

        assert phase["kind"] == "phase"
        assert phase["name"] == "composing"
        assert phase["detail"] == {"render_id": "abc123", "count": 5}

    def test_phase_event_with_empty_detail(self) -> None:
        """Phase event with no detail has empty dict."""
        from orch.rag.qa import _emit_phase

        phase = _emit_phase("retrieving", None)

        assert phase["kind"] == "phase"
        assert phase["name"] == "retrieving"
        assert phase["detail"] == {}


class TestTokenEventPayload:
    """Tests for token event payload structure."""

    def test_token_event_payload_structure(self) -> None:
        """Token event dict has correct structure."""
        from orch.rag.qa import _emit_token

        token = _emit_token("Hello world.")

        assert token["kind"] == "token"
        assert token["text"] == "Hello world."


class TestCitationEventPayload:
    """Tests for citation event payload structure."""

    def test_citation_event_payload_structure(self) -> None:
        """Citation event dict has correct structure."""
        from orch.rag.qa import _emit_citation

        citation = _emit_citation(
            n=1,
            work_item_type="feature",
            work_item_id="F-00042",
            label="F-00042 — Test Feature",
            url="/project/test/item/F-00042",
            snippet="This feature adds X",
        )

        assert citation["kind"] == "citation"
        assert citation["n"] == 1
        assert citation["work_item_type"] == "feature"
        assert citation["work_item_id"] == "F-00042"
        assert citation["label"] == "F-00042 — Test Feature"
        assert citation["url"] == "/project/test/item/F-00042"
        assert citation["snippet"] == "This feature adds X"


class TestQARequestSchema:
    """Tests for QARequest schema."""

    def test_context_chips_accepts_valid_values(self) -> None:
        """context_chips field accepts why, history, findusages."""
        from dashboard.routers.code_qa import QARequest

        request = QARequest(
            question="Why does X do Y?",
            context_level="architecture",
            context_chips=["why"],
        )
        assert "why" in request.context_chips

        request = QARequest(
            question="Show me history",
            context_level="architecture",
            context_chips=["history"],
        )
        assert "history" in request.context_chips

        request = QARequest(
            question="Find usages of parse_id",
            context_level="architecture",
            context_chips=["findusages"],
        )
        assert "findusages" in request.context_chips

    def test_findusages_symbol_hint_extraction(self) -> None:
        """When findusages is in chips, symbol_hint is question.strip()."""
        from dashboard.routers.code_qa import QARequest

        request = QARequest(
            question="parse_id function",
            context_level="architecture",
            context_chips=["findusages"],
        )

        symbol_hint = request.question.strip() if "findusages" in request.context_chips else None
        assert symbol_hint == "parse_id function"

    def test_symbol_hint_not_extracted_without_findusages(self) -> None:
        """Without findusages chip, symbol_hint is None."""
        from dashboard.routers.code_qa import QARequest

        request = QARequest(
            question="Why does the daemon retry?",
            context_level="architecture",
            context_chips=["why"],
        )

        symbol_hint = request.question.strip() if "findusages" in request.context_chips else None
        assert symbol_hint is None


class TestQARerenderRequestSchema:
    """Tests for QARerenderRequest schema."""

    def test_tone_valid_values(self) -> None:
        """tone accepts only technical or functional."""
        from dashboard.routers.code_qa import QARerenderRequest

        req = QARerenderRequest(render_id="abc123", tone="technical")
        assert req.tone == "technical"

        req = QARerenderRequest(render_id="abc123", tone="functional")
        assert req.tone == "functional"

    def test_tone_invalid_value_rejected(self) -> None:
        """tone rejects invalid values."""
        from pydantic import ValidationError

        from dashboard.routers.code_qa import QARerenderRequest

        with pytest.raises(ValidationError):
            QARerenderRequest(render_id="abc123", tone="invalid")

    def test_render_id_required(self) -> None:
        """render_id is required and must be non-empty."""
        from pydantic import ValidationError

        from dashboard.routers.code_qa import QARerenderRequest

        with pytest.raises(ValidationError):
            QARerenderRequest(render_id="", tone="technical")
