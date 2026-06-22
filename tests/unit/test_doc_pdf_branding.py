"""Unit tests for Innovation Ways branding of the PDF document template.

Renders ``dashboard/templates/pdf/doc_pdf.html`` with the brand Jinja globals and
verifies the output is on-brand (teal accent, embedded Inter, IW logo lockup) and
no longer carries the old indigo/Discord ``#5865f2`` palette.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

import dashboard.utils.branding as br

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "dashboard" / "templates"


def _render_pdf_html() -> str:
    """Render the PDF template with brand globals and a stub doc/project.

    Returns:
        The rendered HTML string fed to headless Chromium for PDF output.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.globals.update(br.brand_jinja_globals())
    template = env.get_template("pdf/doc_pdf.html")
    doc = SimpleNamespace(
        title="Sample Research Document",
        doc_type=SimpleNamespace(value="research"),
        version=3,
        status=SimpleNamespace(value="draft"),
    )
    project = SimpleNamespace(display_name="IW AI Core Platform")
    return template.render(
        doc=doc,
        project=project,
        rendered_content="<p>Body content.</p>",
        generated_at="2026-06-14 12:00:00",
    )


def test_pdf_uses_brand_accent_not_indigo() -> None:
    """Verifies the PDF chrome uses the brand teal accent and drops indigo #5865f2."""
    html = _render_pdf_html().lower()
    assert html.find("#0d9488") != -1, "PDF must use the brand teal accent"
    assert html.find("5865f2") == -1, "PDF must not carry the old indigo/Discord palette"


def test_pdf_embeds_inter_font() -> None:
    """Verifies Inter is embedded as @font-face so PDF output renders on-brand."""
    html = _render_pdf_html()
    assert html.find("@font-face") != -1
    assert html.find("font-family:'Inter'") != -1
    assert html.find("base64,") != -1


def test_pdf_includes_logo_lockup() -> None:
    """Verifies the IW logo lockup (inline mark + wordmark) feeds the paged layout."""
    html = _render_pdf_html()
    # The cover/divider lockup is assembled client-side by the paged-layout
    # builder from the .fb-lockup box plus the brand mark + name carried in the
    # #docmeta JSON. tojson escapes the inline SVG markup, so it appears as the
    # <svg escape rather than a literal <svg tag.
    assert html.find("fb-lockup") != -1
    assert html.find("markWhiteSvg") != -1
    assert html.find("\\u003csvg") != -1
    assert html.find("Innovation Ways") != -1


def test_pdf_renders_doc_metadata() -> None:
    """Verifies the document title and metadata survive rendering."""
    html = _render_pdf_html()
    assert html.find("Sample Research Document") != -1
    assert html.find("Body content.") != -1
