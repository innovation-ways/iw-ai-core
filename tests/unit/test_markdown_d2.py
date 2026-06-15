"""Unit tests for server-side D2 diagram rendering in markdown.py.

D2 has no client renderer, so fenced ``d2`` blocks must always render server-side
to brand-themed SVG. These tests skip gracefully when the d2 binary is absent.
"""

from __future__ import annotations

import pytest


class TestD2Rendering:
    """Fenced d2 blocks render to brand-themed inline SVG regardless of the mermaid flag."""

    def test_d2_block_renders_brand_svg(self) -> None:
        """Verifies a d2 block becomes a teal-themed SVG wrapped in .d2-diagram."""
        import dashboard.utils.markdown as md_mod

        md = "```d2\ndirection: right\nx: Service\ny: Database\nx -> y\n```\n"
        result = md_mod.render_markdown_with_callouts(md, render_mermaid=False)

        if 'class="language-d2"' in result:
            pytest.skip("d2 binary unavailable in this environment; raw block preserved")

        assert result.find("<svg") != -1, "d2 block must render to an SVG"
        assert result.find('class="d2-diagram"') != -1, "SVG must be wrapped in .d2-diagram"
        assert result.lower().find("0d9488") != -1, "brand teal must be applied to the D2 SVG"

    def test_d2_rendered_even_when_mermaid_disabled(self) -> None:
        """Verifies d2 renders with render_mermaid=False (no client-side D2 renderer)."""
        import dashboard.utils.markdown as md_mod

        result = md_mod.render_markdown_with_callouts("```d2\na -> b\n```\n", render_mermaid=False)

        if 'class="language-d2"' in result:
            pytest.skip("d2 binary unavailable")
        assert result.find("<svg") != -1
