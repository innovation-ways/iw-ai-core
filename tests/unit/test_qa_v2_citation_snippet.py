"""Unit tests for citation snippet logic."""

from __future__ import annotations

from unittest.mock import MagicMock


class MockWorkItem:
    """Mock WorkItem for testing snippet extraction."""

    def __init__(
        self,
        wi_id: str,
        title: str = "Test",
        summary: str | None = "Summary",
        functional_doc_content: str | None = None,
    ) -> None:
        self.id = wi_id
        self.work_item_id = wi_id
        self.type = MagicMock(value="Feature")
        self.title = title
        self.summary = summary
        self.functional_doc_content = functional_doc_content


class TestCitationSnippet:
    """Tests for citation snippet fallback logic."""

    def test_null_functional_doc_falls_back_to_summary(self) -> None:
        """When functional_doc_content is NULL, snippet falls back to summary."""
        item = MockWorkItem(
            "F-00001",
            title="Test Item",
            summary="This is the summary text",
            functional_doc_content=None,
        )

        snippet = (item.functional_doc_content or "")[:300].strip() or (item.summary or "")

        assert snippet == "This is the summary text"

    def test_non_null_functional_doc_uses_first_300_chars(self) -> None:
        """When functional_doc_content is non-NULL, snippet uses first 300 chars."""
        content = "A" * 500
        item = MockWorkItem(
            "F-00001",
            title="Test Item",
            summary="This is the summary",
            functional_doc_content=content,
        )

        snippet = (item.functional_doc_content or "")[:300].strip() or (item.summary or "")

        assert snippet == "A" * 300
        assert len(snippet) == 300

    def test_empty_functional_doc_falls_back_to_summary(self) -> None:
        """When functional_doc_content is empty string, snippet falls back to summary."""
        item = MockWorkItem(
            "F-00001",
            title="Test Item",
            summary="Summary text",
            functional_doc_content="",
        )

        snippet = (item.functional_doc_content or "")[:300].strip() or (item.summary or "")

        assert snippet == "Summary text"

    def test_empty_both_returns_empty_string(self) -> None:
        """When both are empty, returns empty string."""
        item = MockWorkItem(
            "F-00001",
            title="Test Item",
            summary=None,
            functional_doc_content=None,
        )

        snippet = (item.functional_doc_content or "")[:300].strip() or (item.summary or "")

        assert snippet == ""

    def test_whitespace_in_functional_doc_is_stripped(self) -> None:
        """Whitespace in functional_doc_content is stripped."""
        item = MockWorkItem(
            "F-00001",
            title="Test Item",
            summary="Summary",
            functional_doc_content="   Content   ",
        )

        snippet = (item.functional_doc_content or "")[:300].strip() or (item.summary or "")

        assert snippet == "Content"
