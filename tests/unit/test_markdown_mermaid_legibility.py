"""Unit tests for Mermaid rendering legibility + branding in markdown.py.

These tests verify that server-side Mermaid rendering produces a self-contained,
legible, on-brand diagram — Innovation Ways ink labels on a light background with
the brand teal applied — so the SVG is correct regardless of where it is embedded
(dark dashboard page, standalone HTML, PDF).

The contract:
- The rendered SVG output (or its wrapper) contains the enforced brand ink token
  (``1a1d23``) so labels are never white-on-white.
- The brand accent (teal ``0d9488``) reaches the rendered SVG, proving the brand
  theme — not stock default Mermaid — was applied.
- A fallback to a raw ``<pre>`` block (when mmdc is unavailable) is skipped rather
  than asserted, because we cannot control the CI environment's node/mmdc state.
"""

from __future__ import annotations

import pytest


class TestMermaidLegibility:
    """Test that server-side Mermaid render enforces dark legible brand labels."""

    def test_mermaid_render_contains_enforced_brand_ink_token(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When mmdc renders a diagram, the output must contain the brand ink colour.

        The enforced ink token (``1a1d23``) appears in the wrapper <div> inline
        style (and the diagram's textColor), preventing labels from inheriting a
        near-white page colour and rendering invisible in dark mode.
        """
        import dashboard.utils.markdown as md_mod

        test_md = (
            "Some intro text.\n\n"
            "```mermaid\n"
            "graph TD\n"
            "    A[Foo] --> B[Bar]\n"
            "```\n\n"
            "After the diagram."
        )

        result = md_mod.render_markdown_with_callouts(test_md, render_mermaid=True)

        # If mmdc was unavailable, render_markdown_with_callouts returns the raw
        # <pre> block unchanged — skip rather than false-fail.
        if "language-mermaid" in result:
            pytest.skip(
                "mmdc not available in this environment; render fell through to raw <pre> block"
            )

        assert result.lower().find("1a1d23") != -1, (
            "Rendered SVG wrapper must contain the enforced brand ink token "
            "'1a1d23' so labels are legible on any background. "
            f"Got: {result[:500]}"
        )

    def test_mermaid_render_applies_brand_accent(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The rendered SVG must carry the brand teal accent (proves brand theme).

        Stock-default Mermaid would emit lavender/grey node styling; the brand
        ``base`` theme + themeVariables drives the teal accent (#0D9488) into the
        node borders, so its presence proves the brand theme was applied rather
        than the old ``-t default`` theme.
        """
        import dashboard.utils.markdown as md_mod

        test_md = "```mermaid\nflowchart LR\n    X[Start] --> Y[End]\n```\n"

        result = md_mod.render_markdown_with_callouts(test_md, render_mermaid=True)

        if "language-mermaid" in result:
            pytest.skip("mmdc not available; fell through to raw <pre> block")

        assert result.lower().find("0d9488") != -1, (
            "Rendered SVG must contain the brand accent teal '0d9488' — its "
            "absence means stock-default Mermaid theming leaked through. "
            f"Got: {result[:500]}"
        )

    def test_mermaid_render_wraps_in_brand_diagram_div(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rendered SVG must be wrapped in the .mermaid-diagram brand container.

        Both the mmdc and Kroki paths go through ``_render_mermaid_blocks`` which
        wraps the SVG in a div carrying the brand ink colour + Inter font — the
        belt-and-braces legibility net.
        """
        import dashboard.utils.markdown as md_mod

        test_md = "```mermaid\ngraph TD\n    K --> L\n```\n"

        result = md_mod.render_markdown_with_callouts(test_md, render_mermaid=True)

        if "language-mermaid" in result:
            pytest.skip("mmdc not available; render fell through to raw <pre> block")

        assert result.find('class="mermaid-diagram"') != -1, (
            "SVG must be wrapped in the .mermaid-diagram brand container div"
        )
        assert result.lower().find("inter") != -1, (
            "Brand wrapper must set the Inter font family on the diagram container"
        )

    def test_render_mermaid_false_preserves_raw_block(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When render_mermaid=False, the raw language-mermaid block is preserved
        intact for client-side rendering — mmdc is not invoked.
        """
        import dashboard.utils.markdown as md_mod

        test_md = "```mermaid\ngraph TD\n    C --> D\n```\n"

        result = md_mod.render_markdown_with_callouts(test_md, render_mermaid=False)

        # Must contain the original fenced block, not an SVG
        assert result.find("language-mermaid") != -1
        assert result.find("<svg") == -1, (
            "render_mermaid=False must NOT produce an SVG; "
            "the raw mermaid block must be preserved for client-side rendering"
        )
