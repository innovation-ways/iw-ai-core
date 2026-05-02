"""Unit tests for the _GROUNDING_TEMPLATE prompt in orch.rag.mapgen."""

from __future__ import annotations

from orch.rag.mapgen import _GROUNDING_TEMPLATE


class TestGroundingTemplate:
    """Tests for _GROUNDING_TEMPLATE — locks in prose-length constraints."""

    def test_grounding_template_asks_for_short_sections(self) -> None:
        """RED until I-00056 lands. Locks the rule at 1-3 sentences so future
        edits don't silently inflate prose length again.

        The template must ask for 1-3 concise sentences (not 2-5) so that
        future edits cannot inflate prose length without this test failing.
        """
        text = _GROUNDING_TEMPLATE.template
        assert "1-3 concise sentences" in text, (
            "Grounding template must ask for 1-3 concise sentences (not 2-5) "
            "to keep architecture-map prose compact and above-the-fold readable"
        )
        assert "2-5 concise sentences" not in text, (
            "Grounding template must not ask for 2-5 sentences — the 1-3 limit is the I-00056 fix"
        )
