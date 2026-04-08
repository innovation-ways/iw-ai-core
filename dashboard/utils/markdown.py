"""Markdown to HTML rendering for the IW AI Core dashboard."""

from __future__ import annotations

import markdown as md_lib


def render_markdown(text: str | None) -> str:
    """Convert markdown string to HTML for dashboard rendering.

    The returned string should be used with the ``| safe`` Jinja2 filter
    because the content comes from our own database (design docs, reports).
    """
    if not text:
        return ""
    converter = md_lib.Markdown(
        extensions=["fenced_code", "tables", "nl2br"],
        output_format="html",
    )
    return converter.convert(text)
