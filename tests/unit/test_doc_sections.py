"""Unit tests for orch.doc_sections — H2 markdown section extraction utilities."""

from __future__ import annotations

from orch.doc_sections import extract_sections, split_by_sections


class TestExtractSections:
    """Tests for ExtractSections scenarios."""

    def test_extract_sections_with_h2_headings(self) -> None:
        """Verifies that extract sections with h2 headings."""
        content = """# My Document

## Purpose

This is the purpose section.

## Architecture

This is the architecture section.

## Usage

This is the usage section.
"""
        result = extract_sections(content)
        assert result == ["Purpose", "Architecture", "Usage"]

    def test_extract_sections_no_h2_returns_document(self) -> None:
        """Verifies that extract sections no h2 returns document."""
        content = """# My Document

Some content without any H2 headings.

### H3 Heading

But no H2.
"""
        result = extract_sections(content)
        assert result == ["Document"]

    def test_extract_sections_empty_content(self) -> None:
        """Verifies that extract sections empty content."""
        result = extract_sections("")
        assert result == ["Document"]

    def test_extract_sections_h3_only_returns_document(self) -> None:
        """Verifies that extract sections h3 only returns document."""
        content = """# Document Title

### SubSection A

Content A

### SubSection B

Content B
"""
        result = extract_sections(content)
        assert result == ["Document"]

    def test_extract_sections_strips_whitespace(self) -> None:
        """Verifies that extract sections strips whitespace."""
        content = """# Doc

##   Purpose with spaces

Content
"""
        result = extract_sections(content)
        assert result == ["Purpose with spaces"]

    def test_extract_sections_preserves_inline_backticks(self) -> None:
        """Verifies that extract sections preserves inline backticks."""
        content = """# Doc

## `Code` Section

Content
"""
        result = extract_sections(content)
        assert result == ["`Code` Section"]


class TestSplitBySections:
    """Tests for SplitBySections scenarios."""

    def test_split_by_sections_correct_bodies(self) -> None:
        """Verifies that split by sections correct bodies."""
        content = """# Document

## Purpose

This is the purpose body.

## Architecture

This is the architecture body.
"""
        result = split_by_sections(content)

        assert "Purpose" in result
        assert "Architecture" in result
        assert "This is the purpose body." in result["Purpose"]
        assert "This is the architecture body." in result["Architecture"]
        assert "## Purpose" in result["Purpose"]
        assert "## Architecture" in result["Architecture"]

    def test_split_by_sections_no_h2_returns_document_key(self) -> None:
        """Verifies that split by sections no h2 returns document key."""
        content = """# Document

Some plain content without any H2 headings.
More content here.
"""
        result = split_by_sections(content)

        assert "Document" in result
        assert content in result["Document"]

    def test_split_by_sections_last_section_to_end(self) -> None:
        """Verifies that split by sections last section to end."""
        content = """# Doc

## First

First content.

## Last

Last content goes to the end.
"""
        result = split_by_sections(content)

        assert "First" in result
        assert "Last" in result
        assert "Last content goes to the end." in result["Last"]

    def test_split_by_sections_empty_content(self) -> None:
        """Verifies that split by sections empty content."""
        result = split_by_sections("")
        assert result == {"Document": ""}

    def test_split_by_sections_single_h2(self) -> None:
        """Verifies that split by sections single h2."""
        content = """# Document

## Only One

Content under the only section.
"""
        result = split_by_sections(content)

        assert "Only One" in result
        assert "Content under the only section." in result["Only One"]
