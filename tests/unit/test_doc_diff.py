"""Unit tests for orch.doc_diff — section-aware document diff."""

from __future__ import annotations

from orch.doc_diff import diff_document_versions


class TestDiffNoH2Headings:
    def test_no_h2_headings_single_document_section(self) -> None:
        """No H2 headings → single 'Document' section."""
        old = "Hello world\n"
        new = "Hello universe\n"
        result = diff_document_versions(old, new, 1, 2)

        assert len(result.sections) == 1
        assert result.sections[0].section_name == "Document"
        assert result.sections[0].status == "changed"


class TestDiffUnchangedSection:
    def test_identical_section_content_unchanged(self) -> None:
        """Identical section content → status unchanged."""
        content = "## Purpose\nSame content\n"
        result = diff_document_versions(content, content, 1, 2)

        assert result.sections[0].status == "unchanged"
        assert result.sections[0].unified_diff == []

    def test_multiple_unchanged_sections(self) -> None:
        """All sections identical → all status unchanged."""
        content = "## Purpose\nSame content\n## Architecture\nMore content\n"
        result = diff_document_versions(content, content, 1, 2)

        assert len(result.sections) == 2
        assert all(s.status == "unchanged" for s in result.sections)


class TestDiffAddedSection:
    def test_section_only_in_new_version_added(self) -> None:
        """Section present only in new version → status added."""
        old = "## Purpose\nOld purpose\n"
        new = "## Purpose\nOld purpose\n## Usage\nNew section\n"
        result = diff_document_versions(old, new, 1, 2)

        statuses = {s.section_name: s.status for s in result.sections}
        assert statuses["Purpose"] == "unchanged"
        assert statuses["Usage"] == "added"

    def test_entire_document_added(self) -> None:
        """No H2 headings in old, new content has sections → Document removed, Purpose added."""
        old = "Old document content\n"
        new = "## Purpose\nNew purpose\n"
        result = diff_document_versions(old, new, 1, 2)

        assert len(result.sections) == 2
        statuses = {s.section_name: s.status for s in result.sections}
        assert statuses["Document"] == "removed"
        assert statuses["Purpose"] == "added"


class TestDiffRemovedSection:
    def test_section_only_in_old_version_removed(self) -> None:
        """Section present only in old version → status removed."""
        old = "## Purpose\nOld purpose\n## Deprecated\nGoing away\n"
        new = "## Purpose\nOld purpose\n"
        result = diff_document_versions(old, new, 1, 2)

        statuses = {s.section_name: s.status for s in result.sections}
        assert statuses["Purpose"] == "unchanged"
        assert statuses["Deprecated"] == "removed"


class TestDiffChangedSection:
    def test_modified_section_content_changed(self) -> None:
        """Modified section content → status changed with non-empty diff."""
        old = "## Purpose\nVersion 1 content\n"
        new = "## Purpose\nVersion 2 content\n"
        result = diff_document_versions(old, new, 1, 2)

        assert result.sections[0].status == "changed"
        assert len(result.sections[0].unified_diff) > 0

    def test_changed_section_diff_contains_expected_markers(self) -> None:
        """Changed section unified diff contains + and - line markers."""
        old = "## Purpose\nOld line\n"
        new = "## Purpose\nNew line\n"
        result = diff_document_versions(old, new, 1, 2)

        diff_text = "".join(result.sections[0].unified_diff)
        assert any(marker in diff_text for marker in ["+", "-"])


class TestDiffVersionNumbers:
    def test_version_old_and_new_preserved_in_result(self) -> None:
        """version_old and version_new are preserved in DocDiff."""
        result = diff_document_versions("a\n", "b\n", 3, 7)

        assert result.version_old == 3
        assert result.version_new == 7

    def test_version_numbers_in_unified_diff_filenames(self) -> None:
        """Unified diff fromfile/tofile use the correct version numbers."""
        old = "## Purpose\nOld content\n"
        new = "## Purpose\nNew content\n"
        result = diff_document_versions(old, new, 5, 10)

        diff_text = "".join(result.sections[0].unified_diff)
        assert "v5/Purpose" in diff_text
        assert "v10/Purpose" in diff_text


class TestDiffMultipleSections:
    def test_mixed_change_types(self) -> None:
        """Document with added, removed, unchanged, and changed sections."""
        old = "## Overview\nOld overview\n## Purpose\nOld purpose\n## Deprecated\nGoing away\n"
        new = "## Overview\nNew overview\n## Purpose\nOld purpose\n## Usage\nNew section\n"
        result = diff_document_versions(old, new, 1, 2)

        statuses = {s.section_name: s.status for s in result.sections}
        assert statuses["Overview"] == "changed"
        assert statuses["Purpose"] == "unchanged"
        assert statuses["Deprecated"] == "removed"
        assert statuses["Usage"] == "added"
        assert len(result.sections) == 4

    def test_section_order_preserved_from_document(self) -> None:
        """Section order in result matches document order."""
        old = "## Third\nOld\n## First\nOld\n"
        new = "## Third\nNew\n## First\nNew\n"
        result = diff_document_versions(old, new, 1, 2)

        section_names = [s.section_name for s in result.sections]
        assert section_names == ["Third", "First"]


class TestDiffUnifiedDiffFormat:
    def test_added_section_unified_diff_no_from_lines(self) -> None:
        """Added section diff has no old content lines."""
        old = "## Purpose\nOld purpose\n"
        new = "## Purpose\nOld purpose\n## Usage\nNew section\n"
        result = diff_document_versions(old, new, 1, 2)

        usage_section = next(s for s in result.sections if s.section_name == "Usage")
        assert usage_section.status == "added"
        diff_text = "".join(usage_section.unified_diff)
        assert "---" in diff_text
        assert any("+New section" in line for line in usage_section.unified_diff)

    def test_removed_section_unified_diff_no_to_lines(self) -> None:
        """Removed section diff has no new content lines."""
        old = "## Purpose\nOld purpose\n## Deprecated\nGoing away\n"
        new = "## Purpose\nOld purpose\n"
        result = diff_document_versions(old, new, 1, 2)

        deprecated_section = next(s for s in result.sections if s.section_name == "Deprecated")
        assert deprecated_section.status == "removed"
        diff_text = "".join(deprecated_section.unified_diff)
        assert "---" in diff_text
        assert any("-Going away" in line for line in deprecated_section.unified_diff)
