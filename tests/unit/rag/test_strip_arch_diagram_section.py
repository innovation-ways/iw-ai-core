"""Unit tests for strip_trailing_arch_diagram_section (I-00055).

Covers the strip helper that removes legacy trailing '## Architecture Diagram'
sections from architecture-map markdown content.
"""

from __future__ import annotations

from orch.rag.mapgen import strip_trailing_arch_diagram_section


class TestStripTrailingArchDiagramSection:
    """Tests for the strip_trailing_arch_diagram_section helper."""

    def test_strip_trailing_arch_diagram_section_removes_legacy_block(self):
        """When content contains a trailing '## Architecture Diagram' section
        with purpose comment and mermaid fence, the entire trailing block
        (H2 + comment + fence + DSL) must be removed.
        """
        legacy = (
            "# Architecture Map\n\n"
            "## Purpose\nA test project.\n\n"
            "## Architecture Diagram\n\n"
            "<!-- purpose: example -->\n\n"
            "```mermaid\n"
            "---\n"
            "config:\n"
            "  layout: elk\n"
            "---\n"
            "graph TD\n"
            "  A --> B\n"
            "```\n"
        )
        cleaned = strip_trailing_arch_diagram_section(legacy)

        # All three forbidden substrings from the trailing section must be gone.
        assert "## Architecture Diagram" not in cleaned, (
            "The '## Architecture Diagram' H2 must be stripped from the trailing section"
        )
        assert "<!-- purpose:" not in cleaned, (
            "The purpose HTML comment must be stripped from the trailing section"
        )
        assert "```mermaid" not in cleaned, (
            "The mermaid fenced block must be stripped from the trailing section"
        )
        # The prefix (Purpose section) must be preserved.
        assert "## Purpose" in cleaned, (
            "The prefix content before the Architecture Diagram section must be preserved"
        )

    def test_strip_trailing_arch_diagram_section_is_idempotent(self):
        """Calling the stripper twice must produce the same result as calling it once."""
        legacy = "# X\n\n## Architecture Diagram\n\n```mermaid\ngraph TD\nA-->B\n```\n"
        once = strip_trailing_arch_diagram_section(legacy)
        twice = strip_trailing_arch_diagram_section(once)
        assert once == twice, "strip_trailing_arch_diagram_section must be idempotent"

    def test_strip_trailing_arch_diagram_section_no_op_when_absent(self):
        """When content contains no trailing Architecture Diagram section,
        the content must be returned unchanged (modulo trailing whitespace removal
        which the function applies uniformly via .rstrip()).
        """
        clean = "# Architecture Map\n\n## Purpose\nA test project.\n"
        result = strip_trailing_arch_diagram_section(clean)
        # The function applies .rstrip() unconditionally, so the result
        # has no trailing whitespace (but all other content is preserved).
        assert result == clean.rstrip(), (
            "Content without a trailing Architecture Diagram section must be returned "
            "unchanged (modulo trailing whitespace removal)"
        )
        # Explicitly verify the internal content is preserved
        assert "# Architecture Map" in result
        assert "## Purpose" in result
        assert "A test project." in result

    def test_strip_trailing_arch_diagram_section_keeps_non_trailing_h2(self):
        """A non-trailing '## Architecture Diagram' H2 (followed by another
        section) must NOT be removed — only the trailing one is stripped.

        The spec requires that only the LAST H2 named 'Architecture Diagram' be
        removed. Since '## Purpose' comes after '## Architecture Diagram',
        this input should be returned unchanged (ignoring trailing whitespace).
        If the implementation incorrectly strips it, this test fails.
        """
        md = (
            "# Architecture Map\n\n"
            "## Architecture Diagram\nNot the last section.\n\n"
            "## Purpose\nFinal section.\n"
        )
        result = strip_trailing_arch_diagram_section(md)
        # Per the spec: non-trailing Architecture Diagram H2 must be preserved.
        # The function applies .rstrip() so we compare trailing-wstripped versions.
        assert result == md.rstrip(), (
            "A non-trailing '## Architecture Diagram' H2 must be preserved — "
            "the function must not strip content when '## Purpose' (or any other H2) "
            f"follows '## Architecture Diagram'. Got: {result!r}"
        )
        # Verify the core structure is intact
        assert "## Architecture Diagram" in result
        assert "## Purpose" in result

    def test_strip_trailing_arch_diagram_section_strips_without_final_newline(self):
        """When the document ends without a trailing newline, stripping still works."""
        legacy = "# Architecture Map\n\n## Architecture Diagram\n\n```mermaid\ngraph TD\nA-->B\n```"
        cleaned = strip_trailing_arch_diagram_section(legacy)
        assert "## Architecture Diagram" not in cleaned
        assert "```mermaid" not in cleaned
        # Content before the diagram section must be preserved
        assert "# Architecture Map" in cleaned

    def test_strip_trailing_arch_diagram_section_preserves_content_before(self):
        """All content before the trailing diagram section must be preserved byte-exactly."""
        md = (
            "# Architecture Map\n\n"
            "## Purpose\nThe main purpose.\n\n"
            "## Components\n- Component A\n- Component B\n\n"
            "## Architecture Diagram\n\n"
            "```mermaid\ngraph TD\n  A --> B\n```\n"
        )
        cleaned = strip_trailing_arch_diagram_section(md)

        # These sections must survive intact.
        assert "# Architecture Map" in cleaned
        assert "## Purpose" in cleaned
        assert "## Components" in cleaned
        assert "- Component A" in cleaned
        assert "- Component B" in cleaned

    def test_strip_trailing_arch_diagram_section_strips_multiple_diagram_blocks(self):
        """If the trailing section contains multiple mermaid fences, all are stripped."""
        legacy = (
            "# Architecture Map\n\n"
            "## Purpose\nA project.\n\n"
            "## Architecture Diagram\n\n"
            "<!-- purpose: example -->\n\n"
            "```mermaid\n"
            "graph TD\n"
            "  A --> B\n"
            "```\n\n"
            "Some prose.\n\n"
            "```mermaid\n"
            "graph LR\n"
            "  X --> Y\n"
            "```\n"
        )
        cleaned = strip_trailing_arch_diagram_section(legacy)
        assert "## Architecture Diagram" not in cleaned
        assert "<!-- purpose:" not in cleaned
        assert cleaned.count("```mermaid") == 0, (
            "All mermaid fences in the trailing section must be removed"
        )
        # Prose section preserved
        assert "## Purpose" in cleaned
