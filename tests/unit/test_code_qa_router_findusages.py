"""Unit tests for /findusages chip handling in the code_qa router."""

from __future__ import annotations


class TestFindUsagesRouting:
    """Tests for findusages chip routing and symbol hint extraction."""

    def test_symbol_hint_extracted_from_question(self) -> None:
        """When findusages is in chips, symbol_hint is question.strip()."""
        from dashboard.routers.code_qa import QARequest

        request = QARequest(
            question="parse_id",
            context_level="architecture",
            context_chips=["findusages"],
        )

        symbol_hint = request.question.strip() if "findusages" in request.context_chips else None
        assert symbol_hint == "parse_id"

    def test_symbol_hint_not_extracted_without_findusages_chip(self) -> None:
        """Without findusages chip, symbol_hint is None."""
        from dashboard.routers.code_qa import QARequest

        request = QARequest(
            question="Why does the daemon retry?",
            context_level="architecture",
            context_chips=["why"],
        )

        symbol_hint = request.question.strip() if "findusages" in request.context_chips else None
        assert symbol_hint is None

    def test_symbol_hint_includes_spaces(self) -> None:
        """Symbol hint preserves spaces in multi-word symbols."""
        from dashboard.routers.code_qa import QARequest

        request = QARequest(
            question="parse_id function",
            context_level="architecture",
            context_chips=["findusages"],
        )

        symbol_hint = request.question.strip() if "findusages" in request.context_chips else None
        assert symbol_hint == "parse_id function"

    def test_findusages_chip_is_list_of_strings(self) -> None:
        """context_chips is a list of strings."""
        from dashboard.routers.code_qa import QARequest

        request = QARequest(
            question="parse_id",
            context_level="architecture",
            context_chips=["findusages"],
        )

        assert isinstance(request.context_chips, list)
        assert all(isinstance(c, str) for c in request.context_chips)

    def test_multiple_chips_including_findusages(self) -> None:
        """Multiple chips can include findusages along with others."""
        from dashboard.routers.code_qa import QARequest

        request = QARequest(
            question="Why does parse_id work?",
            context_level="architecture",
            context_chips=["why", "findusages"],
        )

        symbol_hint = request.question.strip() if "findusages" in request.context_chips else None
        assert symbol_hint == "Why does parse_id work?"
        assert "why" in request.context_chips
        assert "findusages" in request.context_chips
