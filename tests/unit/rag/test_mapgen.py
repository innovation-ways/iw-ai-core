"""Unit tests for MapGenerator._assemble_markdown invariant (I-00055).

RED until I-00055 lands. The architecture-map content must contain
no '## Architecture Diagram' H2, no purpose comment, and no mermaid fence.
"""

from __future__ import annotations


class TestAssembleMarkdownOmission:
    """Tests for the I-00055 content invariant: _assemble_markdown must NOT
    emit the architecture diagram section inline.
    """

    def test_i00055_assemble_markdown_omits_inline_diagram(self):
        """The assembled markdown must contain no H2, no purpose comment,
        and no mermaid fence — all three are forbidden substrings.
        """
        from orch.rag.mapgen import MapGenerator

        # Provide only the minimal required answers; the mermaid and purpose
        # args are passed to match the signature but must not appear in output.
        answers = {key: f"answer for {key}" for key, _, _ in MapGenerator.QUESTIONS}

        md = MapGenerator()._assemble_markdown(
            answers,
            mermaid="graph TD\n  A --> B",
            purpose="example purpose",
        )

        # All three forbidden substrings must be absent.
        assert "## Architecture Diagram" not in md, (
            "Architecture-map markdown must NOT contain an '## Architecture Diagram' H2 section"
        )
        assert "<!-- purpose:" not in md, (
            "Architecture-map markdown must NOT contain a purpose HTML comment"
        )
        assert "```mermaid" not in md, (
            "Architecture-map markdown must NOT contain a mermaid fenced code block"
        )

    def test_i00055_assemble_markdown_contains_all_sections(self):
        """Sanity check: all 8 section H2s must be present."""
        from orch.rag.mapgen import _SECTION_TITLES, MapGenerator

        answers = {key: f"answer for {key}" for key, _, _ in MapGenerator.QUESTIONS}
        md = MapGenerator()._assemble_markdown(answers, mermaid="", purpose="")

        for key, _question, _retrieval in MapGenerator.QUESTIONS:
            label = _SECTION_TITLES.get(key, key.replace("_", " ").title())
            assert f"## {label}" in md, (
                f"Section '## {label}' must be present in assembled markdown"
            )

    def test_i00055_assemble_markdown_answers_are_plain_text(self):
        """Answers must be embedded verbatim (no markdown fences wrapping them)."""
        from orch.rag.mapgen import MapGenerator

        answers = {key: f"plain text for {key}" for key, _, _ in MapGenerator.QUESTIONS}
        md = MapGenerator()._assemble_markdown(answers, mermaid="", purpose="")

        for key in answers:
            assert answers[key] in md
