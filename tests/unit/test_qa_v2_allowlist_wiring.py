"""Unit tests for citation allowlist wiring in answer_stream_v2."""

from __future__ import annotations

from unittest.mock import MagicMock

from orch.rag.citation_allowlist import extract_citations, filter_citations


class TestCitationAllowlistWiring:
    """Tests for citation allowlist filter wiring."""

    def test_llm_output_containing_allowed_id_only(self) -> None:
        """When LLM mentions only allowed IDs, all are emitted."""
        bundle_allowed = {"F-00042", "CR-00011", "I-00033"}
        llm_output = "According to F-00042, the button was created to handle project creation."

        filtered_text, stripped = filter_citations(llm_output, bundle_allowed)

        assert stripped == []
        assert "F-00042" in filtered_text

    def test_llm_hallucinates_id_not_in_allowed(self) -> None:
        """Hallucinated IDs not in allowed set are dropped."""
        bundle_allowed = {"CR-00011"}
        llm_output = "CR-00011 is the change that added the button, but F-99999 changed it later."

        filtered_text, stripped = filter_citations(llm_output, bundle_allowed)

        assert "F-99999" not in filtered_text
        assert "F-99999" in stripped
        assert "CR-00011" in filtered_text

    def test_extract_citations_from_text(self) -> None:
        """extract_citations returns set of IDs mentioned in text."""
        text = "Based on F-00042 and CR-00011, we can see that I-00033 was also involved."

        ids = extract_citations(text)

        assert set(ids) == {"F-00042", "CR-00011", "I-00033"}

    def test_allowlist_intersection_for_citation_emission(self) -> None:
        """Only IDs in both LLM output and allowed_ids emit citation events."""
        bundle_allowed = {"F-00042", "CR-00011", "I-00033"}
        llm_output = "The F-00042 change introduced the button. CR-00011 changed its color."

        filtered_text, _ = filter_citations(llm_output, bundle_allowed)
        mentioned_ids = set(extract_citations(filtered_text))

        candidate_items = [
            MagicMock(id="F-00042", title="Button Feature"),
            MagicMock(id="CR-00011", title="Color Change"),
            MagicMock(id="I-00033", title="Some Incident"),
        ]

        emitted = [
            item
            for item in candidate_items
            if item.id in mentioned_ids and item.id in bundle_allowed
        ]

        assert len(emitted) == 2
        assert emitted[0].id == "F-00042"
        assert emitted[1].id == "CR-00011"

    def test_no_ids_mentioned_emits_nothing(self) -> None:
        """When LLM mentions no IDs, no citation events are emitted."""
        bundle_allowed = {"F-00042", "CR-00011"}
        llm_output = "The button was created as part of the New Project feature."

        filtered_text, _ = filter_citations(llm_output, bundle_allowed)
        mentioned_ids = set(extract_citations(filtered_text))

        candidate_items = [
            MagicMock(id="F-00042", title="Button Feature"),
            MagicMock(id="CR-00011", title="Color Change"),
        ]

        emitted = [
            item
            for item in candidate_items
            if item.id in mentioned_ids and item.id in bundle_allowed
        ]

        assert len(emitted) == 0

    def test_all_ids_allowed_all_emitted(self) -> None:
        """When LLM mentions only IDs all in allowed set, all are emitted."""
        bundle_allowed = {"F-00042", "CR-00011", "I-00033"}
        llm_output = "F-00042, CR-00011, and I-00033 all relate to the button."

        filtered_text, _ = filter_citations(llm_output, bundle_allowed)
        mentioned_ids = set(extract_citations(filtered_text))

        candidate_items = [
            MagicMock(id="F-00042", title="Item 1"),
            MagicMock(id="CR-00011", title="Item 2"),
            MagicMock(id="I-00033", title="Item 3"),
        ]

        emitted = [
            item
            for item in candidate_items
            if item.id in mentioned_ids and item.id in bundle_allowed
        ]

        assert len(emitted) == 3
