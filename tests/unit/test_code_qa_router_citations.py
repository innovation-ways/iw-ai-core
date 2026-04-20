"""Unit tests for work-item citation handling in the code_qa router."""

from __future__ import annotations

import re

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

    def test_symbol_id_uses_same_tracker(self) -> None:
        """Symbol IDs and work-item IDs share the same tracker."""
        from dashboard.routers.code_qa import _CitationTracker

        tracker = _CitationTracker()
        idx1 = tracker.add("symbol:parse_id")
        idx2 = tracker.add_work_item("F-00042", "feature")

        assert idx1 == 1
        assert idx2 == 2


class TestCitationEventPayload:
    """Tests for citation event payload structure from backend."""

    def test_citation_event_payload_structure(self) -> None:
        """Citation event dict has correct structure from _emit_citation."""
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

    def test_citation_event_all_work_item_types(self) -> None:
        """All work_item_type values are correctly supported."""
        from orch.rag.qa import _emit_citation

        for wi_type in ["feature", "incident", "change_request"]:
            citation = _emit_citation(
                n=1,
                work_item_type=wi_type,
                work_item_id="F-00001",
                label="Test",
                url="/test",
                snippet="Test",
            )
            assert citation["work_item_type"] == wi_type
            assert re.match(r"^(F|I|CR)-\d{5}$", citation["work_item_id"])
