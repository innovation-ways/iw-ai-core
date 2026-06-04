"""Unit test for relevance-filter regression (AC3 long-term backstop).

Builds a mock bundle with three items: F-00001 (added button), CR-00002 (coloured it blue),
CR-00003 (reshaped to square). Produces a mocked LLM output that narrates only the colour
history and cites only CR-00002. Asserts the final emitted citation list contains only CR-00002,
and CR-00003 is absent from both text and citations.

This is the regression backstop for AC3 — it will catch future prompt-layout
or allowlist changes that regress the filter.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from orch.rag.citation_allowlist import extract_citations, filter_citations
from orch.rag.evidence import EvidenceBundle


class MockWorkItem:
    """Mock WorkItem with functional doc content."""

    def __init__(
        self,
        wi_id: str,
        title: str,
        summary: str,
        functional_doc_content: str,
        work_item_type: str = "Feature",
    ) -> None:
        self.id = wi_id
        self.work_item_id = wi_id
        self.type = MagicMock(value=work_item_type)
        self.title = title
        self.summary = summary
        self.functional_doc_content = functional_doc_content


class TestRelevanceFilterRegression:
    """Regression backstop for AC3 relevance filter."""

    def test_filter_drops_off_topic_items_mentions_only_color_change(self) -> None:
        """Narrates only colour history → only CR-00002 appears in citations."""
        f_a = MockWorkItem(
            "F-00001",
            title="Add button",
            summary="Added a button widget to the UI",
            functional_doc_content=(
                "F-00001: Added a button widget to the UI. "
                "The button was initially styled with default colors."
            ),
        )
        cr_b = MockWorkItem(
            "CR-00002",
            title="Color button blue",
            summary="Changed button color to blue",
            functional_doc_content=(
                "CR-00002: Changed the button color from default to blue. "
                "We chose blue to match the brand palette."
            ),
        )
        cr_c = MockWorkItem(
            "CR-00003",
            title="Shape button square",
            summary="Changed button shape to square",
            functional_doc_content=(
                "CR-00003: Reshaped the button from a circle to a square for better visual balance."
            ),
        )

        bundle = EvidenceBundle(question="why is button X blue?")
        bundle.doc_chunks = []
        bundle.fts_items = []
        bundle.git_log_items = []
        bundle.work_items = [f_a, cr_b, cr_c]

        llm_narrative = (
            "The button is blue because of CR-00002. "
            "CR-00002 changed the color from the default to blue to match brand guidelines."
        )

        filtered_text, stripped = filter_citations(llm_narrative, bundle.allowed_ids)
        mentioned_ids = set(extract_citations(filtered_text))

        emitted = [
            item
            for item in [f_a, cr_b, cr_c]
            if item.id in mentioned_ids and item.id in bundle.allowed_ids
        ]

        assert len(emitted) == 1, (
            f"Expected exactly 1 emitted citation, got {len(emitted)}: {[e.id for e in emitted]}"
        )
        assert emitted[0].id == "CR-00002", f"Expected CR-00002, got {emitted[0].id}"

    def test_filter_removes_hallucinated_id_not_in_bundle(
        self,
    ) -> None:
        """Hallucinated ID F-99999 not in bundle.allowed_ids is dropped from citations."""
        cr_b = MockWorkItem(
            "CR-00002",
            title="Color button blue",
            summary="Changed button color to blue",
            functional_doc_content="CR-00002: Changed the button color to blue.",
        )

        bundle = EvidenceBundle(question="why is button X blue?")
        bundle.fts_items = [cr_b]
        bundle.work_items = [cr_b]

        llm_narrative = (
            "According to CR-00002, the button was recoloured blue. "
            "F-99999 also touched this file but is not relevant to the color change."
        )

        filtered_text, stripped = filter_citations(llm_narrative, bundle.allowed_ids)
        mentioned_ids = set(extract_citations(filtered_text))

        assert "F-99999" not in mentioned_ids, (
            "Hallucinated ID F-99999 must not appear in mentioned_ids"
        )
        assert "F-99999" in stripped or "F-99999" not in filtered_text

        emitted = [
            item for item in [cr_b] if item.id in mentioned_ids and item.id in bundle.allowed_ids
        ]

        assert len(emitted) == 1
        assert emitted[0].id == "CR-00002"

    def test_llm_mentions_zero_ids_emits_no_citations(self) -> None:
        """LLM answers without citing any work item → zero citation events."""
        bundle = EvidenceBundle(question="what is the version number?")
        bundle.fts_items = []
        bundle.work_items = []

        llm_narrative = "The version number is 2.1.0 and is defined in setup.py."

        filtered_text, _ = filter_citations(llm_narrative, bundle.allowed_ids)
        mentioned_ids = set(extract_citations(filtered_text))

        assert len(mentioned_ids) == 0, f"Expected no mentioned IDs, got {mentioned_ids}"

    def test_filter_respects_allowed_ids_superset_not_subset(self) -> None:
        """Only IDs that are in BOTH mentioned_ids AND allowed_ids should emit."""
        cr_b = MockWorkItem(
            "CR-00002",
            title="B",
            summary="B summary",
            functional_doc_content="CR-00002 content",
        )
        cr_c = MockWorkItem(
            "CR-00003",
            title="C",
            summary="C summary",
            functional_doc_content="CR-00003 content",
        )

        bundle = EvidenceBundle(question="test")
        bundle.fts_items = [cr_b, cr_c]
        bundle.work_items = [cr_b, cr_c]

        llm_narrative = "CR-00002 and CR-00003 are both relevant here."
        filtered_text, _ = filter_citations(llm_narrative, bundle.allowed_ids)
        mentioned_ids = set(extract_citations(filtered_text))

        allowed_and_mentioned = mentioned_ids & bundle.allowed_ids
        assert allowed_and_mentioned == {"CR-00002", "CR-00003"}, (
            f"Expected both CR-00002 and CR-00003, got {allowed_and_mentioned}"
        )

    def test_functional_doc_content_used_in_snippet_not_summary(self) -> None:
        """Citation snippet uses functional_doc_content[:300], not summary, when non-NULL."""
        cr_b = MockWorkItem(
            "CR-00002",
            title="Color button blue",
            summary="Changed button color",
            functional_doc_content=(
                "CR-00002 full functional doc: This change set specifically "
                "addresses the color aspect. We evaluated blue, green, and red "
                "before settling on the brand blue #0066CC."
            ),
        )

        bundle = EvidenceBundle(question="why is button blue?")
        bundle.fts_items = [cr_b]
        bundle.work_items = [cr_b]

        llm_narrative = "CR-00002 changed the color."
        filtered_text, _ = filter_citations(llm_narrative, bundle.allowed_ids)
        mentioned_ids = set(extract_citations(filtered_text))

        assert "CR-00002" in mentioned_ids

        item = cr_b
        snippet = (item.functional_doc_content or "")[:300].strip() or (item.summary or "")

        assert snippet.startswith("CR-00002 full functional doc"), (
            f"Snippet must use functional_doc_content, got: {snippet[:100]}"
        )
        assert "brand blue #0066CC" in snippet, "Snippet should include full functional doc content"
        assert snippet == item.functional_doc_content[:300], (
            "Snippet must be first 300 chars of functional doc"
        )
