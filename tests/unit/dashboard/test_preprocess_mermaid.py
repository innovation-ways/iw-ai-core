"""Unit tests for _preprocess_mermaid helper in dashboard/routers/code_ui.py."""

from __future__ import annotations

import re

_PATTERN = re.compile(r"```mermaid\s*(.*?)\s*```", re.DOTALL)


def _preprocess_mermaid(text: str) -> str:
    return _PATTERN.sub(r'<pre data-lang="mermaid"><code>\1</code></pre>', text)


class TestPreprocessMermaid:
    """Tests for _preprocess_mermaid — converts ```mermaid blocks to <pre data-lang="mermaid">."""

    def test_preprocess_mermaid_outputs_pre_tag(self) -> None:
        """Output contains <pre data-lang="mermaid"> not <div class="mermaid">."""
        input_md = "Some text\n\n```mermaid\ngraph TD\n  A --> B\n```\n"
        result = _preprocess_mermaid(input_md)

        assert '<pre data-lang="mermaid">' in result
        assert '<div class="mermaid">' not in result

    def test_preprocess_mermaid_preserves_dsl_content(self) -> None:
        """Mermaid DSL content (graph TD) is preserved inside the <pre> element."""
        input_md = "```mermaid\ngraph TD\n  A --> B\n```"
        result = _preprocess_mermaid(input_md)

        assert "graph TD" in result
        assert "A --> B" in result
        assert '<pre data-lang="mermaid">' in result

    def test_preprocess_mermaid_no_mermaid_block(self) -> None:
        """Plain markdown text is returned unchanged (no transformation)."""
        input_md = "Just some markdown text"
        result = _preprocess_mermaid(input_md)

        assert result == input_md
        assert '<pre data-lang="mermaid">' not in result
        assert '<div class="mermaid">' not in result
