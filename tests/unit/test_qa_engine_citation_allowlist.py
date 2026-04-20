"""Unit tests for citation allowlist filter."""

from __future__ import annotations

from unittest.mock import patch


class TestFilterCitations:
    """Tests for filter_citations function."""

    def test_in_allowlist_passes_through(self) -> None:
        """IDs in allowed_ids pass through unchanged."""
        from orch.rag.citation_allowlist import filter_citations

        allowed = {"F-00001", "CR-00002", "I-00003"}
        text = "According to [F-00001] and [CR-00002], this was introduced."

        filtered, stripped = filter_citations(text, allowed)

        assert filtered == text
        assert stripped == []

    def test_out_of_allowlist_stripped(self) -> None:
        """IDs NOT in allowed_ids are stripped (AC4)."""
        from orch.rag.citation_allowlist import filter_citations

        allowed = {"F-00001"}
        text = "According to [F-00001] and [F-99999], this was introduced."

        filtered, stripped = filter_citations(text, allowed)

        assert "F-99999" not in filtered
        assert "F-00001" in filtered
        assert "F-99999" in stripped

    def test_multiple_stripped_ids_logged(self) -> None:
        """Stripped IDs are logged at WARNING level."""
        from orch.rag.citation_allowlist import filter_citations

        allowed = {"F-00001"}
        text = "See [F-00001], [CR-00001], [I-00001] for details."

        with patch("orch.rag.citation_allowlist.logger") as mock_logger:
            filtered, stripped = filter_citations(text, allowed)

        assert len(stripped) == 2
        assert "CR-00001" in stripped
        assert "I-00001" in stripped

        assert mock_logger.warning.called
        call_args = mock_logger.warning.call_args
        assert "CR-00001" in call_args[0][1] or "CR-00001" in str(call_args)

    def test_no_ids_in_text(self) -> None:
        """Text without IDs passes through unchanged."""
        from orch.rag.citation_allowlist import filter_citations

        allowed = {"F-00001"}
        text = "This is plain text without any citations."

        filtered, stripped = filter_citations(text, allowed)

        assert filtered == text
        assert stripped == []

    def test_hallucinated_id_stripped_middle_of_sentence(self) -> None:
        """Hallucinated ID in middle of sentence is stripped correctly."""
        from orch.rag.citation_allowlist import filter_citations

        allowed = {"F-00001"}
        text = "The behavior was introduced in [F-00001] but later modified by [CR-99999]."

        filtered, stripped = filter_citations(text, allowed)

        assert "CR-99999" not in filtered
        assert "[F-00001]" in filtered
        assert "CR-99999" in stripped


class TestExtractCitations:
    """Tests for extract_citations function."""

    def test_extracts_multiple_ids(self) -> None:
        """All IDs in text are extracted in order."""
        from orch.rag.citation_allowlist import extract_citations

        text = "See [F-00001], then [F-00002], and [CR-00001]."

        ids = extract_citations(text)

        assert ids == ["F-00001", "F-00002", "CR-00001"]

    def test_deduplicates_ids(self) -> None:
        """Same ID appearing multiple times is deduplicated."""
        from orch.rag.citation_allowlist import extract_citations

        text = "[F-00001] was introduced, then modified in [F-00001]."

        ids = extract_citations(text)

        assert ids == ["F-00001"]

    def test_no_ids_returns_empty(self) -> None:
        """Text without IDs returns empty list."""
        from orch.rag.citation_allowlist import extract_citations

        ids = extract_citations("No IDs here")
        assert ids == []


class TestValidateCitation:
    """Tests for validate_citation function."""

    def test_valid_id(self) -> None:
        """ID in allowed set returns 'valid'."""
        from orch.rag.citation_allowlist import validate_citation

        result = validate_citation("F-00001", {"F-00001", "CR-00002"})
        assert result == "valid"

    def test_stripped_id(self) -> None:
        """ID not in allowed set returns 'stripped'."""
        from orch.rag.citation_allowlist import validate_citation

        result = validate_citation("F-99999", {"F-00001", "CR-00002"})
        assert result == "stripped"


class TestWorkItemIdPattern:
    """Tests for the work-item ID regex pattern."""

    def test_matches_f_id(self) -> None:
        """F-NNNNN format matches."""
        from orch.rag.citation_allowlist import WORK_ITEM_ID_PATTERN

        assert WORK_ITEM_ID_PATTERN.search("See [F-00001] for details")

    def test_matches_cr_id(self) -> None:
        """CR-NNNNN format matches."""
        from orch.rag.citation_allowlist import WORK_ITEM_ID_PATTERN

        assert WORK_ITEM_ID_PATTERN.search("See [CR-00042] for details")

    def test_matches_i_id(self) -> None:
        """I-NNNNN format matches."""
        from orch.rag.citation_allowlist import WORK_ITEM_ID_PATTERN

        assert WORK_ITEM_ID_PATTERN.search("Related to [I-00123]")

    def test_no_match_invalid_format(self) -> None:
        """Invalid formats do not match."""
        from orch.rag.citation_allowlist import WORK_ITEM_ID_PATTERN

        assert WORK_ITEM_ID_PATTERN.search("F-0001") is None
        assert WORK_ITEM_ID_PATTERN.search("X-00001") is None
        assert WORK_ITEM_ID_PATTERN.search("F-000001") is None
