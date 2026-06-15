"""Unit tests for the Innovation Ways brand source-of-truth loader.

Covers palette/colour exposure, the Mermaid brand config (base theme + brand
themeVariables + Inter + Neo look + conditional ELK), embedded Inter @font-face,
logo markup, and the init-directive injection contract.
"""

from __future__ import annotations

import dashboard.utils.branding as br


class TestBrandPalette:
    """The loaded palette must expose the teal/ink Innovation Ways identity."""

    def test_palette_is_teal_and_ink(self) -> None:
        """Verifies the brand accent is teal and the ink/text colour is set."""
        colors = br.brand_colors()
        assert colors.get("accent", "").lower() == "#0d9488"
        assert colors.get("ink", "").lower() == "#1a1d23"

    def test_dark_text_token_is_lowercased_ink_without_hash(self) -> None:
        """Verifies the enforced dark label token is the ink hex sans '#'."""
        assert br.brand_dark_text_token() == "1a1d23"


class TestMermaidConfig:
    """The Mermaid config must encode the brand theme so diagrams are on-brand."""

    def test_config_uses_base_theme_and_neo_look(self) -> None:
        """Verifies the brand config selects the base theme with the Neo look."""
        cfg = br.mermaid_config()
        assert cfg["theme"] == "base"
        assert cfg["look"] == "neo"

    def test_theme_variables_carry_brand_accent_and_native_font(self) -> None:
        """Verifies themeVariables drive teal borders, ink text, and a native font.

        Diagram labels use a Chromium-native sans stack (not the embedded Inter
        webfont) so mmdc measures node widths with the same font it renders with,
        avoiding async-webfont width mismatches that clip labels.
        """
        tv = br.mermaid_theme_variables()
        assert tv.get("primaryBorderColor", "").lower() == "#0d9488"
        assert tv.get("nodeBorder", "").lower() == "#0d9488"
        assert tv.get("primaryTextColor", "").lower() == "#1a1d23"
        assert tv.get("fontFamily", "").lower().find("sans-serif") != -1

    def test_elk_layout_added_only_when_requested(self) -> None:
        """Verifies the ELK layout key appears only when elk=True."""
        assert "layout" not in br.mermaid_config(elk=False)
        assert br.mermaid_config(elk=True).get("layout") == "elk"

    def test_diagram_wants_elk_for_graph_family_only(self) -> None:
        """Verifies graph-based diagrams request ELK while sequence diagrams do not."""
        assert br.diagram_wants_elk("flowchart TD\n A-->B") is True
        assert br.diagram_wants_elk("graph LR\n A-->B") is True
        assert br.diagram_wants_elk("erDiagram\n A ||--o{ B : has") is True
        assert br.diagram_wants_elk("sequenceDiagram\n A->>B: hi") is False
        assert br.diagram_wants_elk("pie title X\n 'a': 1") is False
        assert br.diagram_wants_elk("") is False

    def test_diagram_wants_elk_skips_init_and_frontmatter_lines(self) -> None:
        """Verifies type detection ignores leading %%{init}%% / --- frontmatter."""
        src = "%%{init: {'theme':'base'}}%%\nflowchart TD\n A-->B"
        assert br.diagram_wants_elk(src) is True


class TestD2Branding:
    """D2 brand theming must recolour diagrams with the teal/ink palette."""

    def test_d2_preamble_carries_teal_theme_overrides(self) -> None:
        """Verifies the D2 preamble declares theme-overrides with the brand teal."""
        preamble = br.d2_brand_preamble()
        assert preamble.find("theme-overrides") != -1
        assert preamble.find("#0D9488") != -1

    def test_ensure_d2_brand_prepends_preamble(self) -> None:
        """Verifies the brand preamble is prepended to a bare D2 source."""
        out = br.ensure_d2_brand("x -> y")
        assert out.startswith("vars:")
        assert out.find("x -> y") != -1

    def test_ensure_d2_brand_respects_existing_config(self) -> None:
        """Verifies an author-supplied d2-config/theme-overrides is left intact."""
        src = 'vars: {\n  d2-config: {\n    theme-overrides: {B1: "#000000"}\n  }\n}\nx -> y'
        assert br.ensure_d2_brand(src) == src

    def test_d2_layout_defaults_to_elk(self) -> None:
        """Verifies the preferred D2 layout engine is ELK."""
        assert br.d2_layout() == "elk"


class TestInitDirectiveInjection:
    """Brand init injection must add the directive only when absent."""

    def test_ensure_brand_init_prepends_when_missing(self) -> None:
        """Verifies the brand init directive is prepended to bare sources."""
        out = br.ensure_brand_init("flowchart TD\n A-->B", elk=True)
        assert out.startswith("%%{init:")
        assert out.lower().find("0d9488") != -1
        assert out.find("flowchart TD") != -1

    def test_ensure_brand_init_respects_existing_directive(self) -> None:
        """Verifies an author-supplied init block is left intact (not doubled)."""
        src = "%%{init: {'theme':'dark'}}%%\nflowchart TD\n A-->B"
        out = br.ensure_brand_init(src)
        assert out == src
        assert out.count("%%{init") == 1


class TestEmbeddedAssets:
    """Inter font + logo assets must be embeddable for PDF/HTML chrome."""

    def test_inter_font_face_css_embeds_base64_woff2(self) -> None:
        """Verifies the Inter @font-face CSS is produced with base64 woff2 data."""
        css = br.inter_font_face_css()
        assert css.find("@font-face") != -1
        assert css.find("font-family:'Inter'") != -1
        assert css.find("base64,") != -1
        # All four weights present.
        for weight in ("400", "500", "600", "700"):
            assert css.find(f"font-weight:{weight}") != -1

    def test_logo_mark_svg_is_present_and_on_brand(self) -> None:
        """Verifies the pure-path mark SVG loads and carries the teal+ink strokes."""
        svg = br.logo_svg("mark")
        assert svg is not None
        assert svg.find("<svg") != -1
        assert svg.find("0D9488") != -1  # teal "I"
        assert svg.find("1A1D23") != -1  # ink "W"

    def test_logo_data_uri_is_base64_svg(self) -> None:
        """Verifies a logo variant resolves to a base64 svg data URI."""
        uri = br.logo_data_uri("horizontal")
        assert uri is not None
        assert uri.startswith("data:image/svg+xml;base64,")

    def test_brand_lockup_html_combines_mark_and_name(self) -> None:
        """Verifies the header lockup embeds the inline mark and the brand name."""
        html = br.brand_lockup_html()
        assert html.find("iw-lockup") != -1
        assert html.find("<svg") != -1
        assert html.find("Innovation Ways") != -1


class TestJinjaGlobals:
    """The Jinja global bundle must expose the brand surface templates need."""

    def test_brand_jinja_globals_keys(self) -> None:
        """Verifies all brand globals required by templates are present."""
        g = br.brand_jinja_globals()
        for key in (
            "iw_brand",
            "iw_brand_colors",
            "iw_brand_mermaid_config",
            "iw_inter_font_face_css",
            "iw_logo_mark_svg",
            "iw_brand_lockup_html",
        ):
            assert key in g, f"missing brand global {key!r}"
        assert g["iw_brand_mermaid_config"]["theme"] == "base"
