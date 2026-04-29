"""Markdown to HTML rendering for the IW AI Core dashboard."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import markdown as md_lib

if TYPE_CHECKING:
    from bs4.element import Tag

TYPE_MAP = {
    "NOTE": ("note", "Note"),
    "TIP": ("tip", "Tip"),
    "WARNING": ("warning", "Warning"),
    "DANGER": ("danger", "Danger"),
    "IMPORTANT": ("important", "Important"),
}

CALLOUT_RE = re.compile(
    r"<p>\s*\[!(NOTE|TIP|WARNING|DANGER|IMPORTANT)\]",
    re.IGNORECASE,
)


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


def render_markdown_with_callouts(text: str | None) -> str:
    """Convert markdown to HTML and post-process GitHub-style callout blockquotes.

    Converts ``<blockquote><p>[!TYPE]...</p></blockquote>`` patterns into
    ``<div class="callout callout-{type}">`` elements with a header row and body.
    """
    html = render_markdown(text)
    return _convert_callout_blockquotes(html)


def _convert_callout_blockquotes(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    for blockquote in soup.find_all("blockquote"):
        callout_divs: list[Tag] = []
        non_callout_elements: list[Tag] = []

        for p in blockquote.find_all("p"):
            p_str = str(p)
            match = CALLOUT_RE.search(p_str)
            if match:
                callout_type = match.group(1).upper()
                type_class, type_label = TYPE_MAP.get(callout_type, ("note", callout_type))
                inner = p.get_text(separator=" ", strip=True)
                inner = re.sub(r"\[!(NOTE|TIP|WARNING|DANGER|IMPORTANT)\]\s*", "", inner)

                callout_div = soup.new_tag("div", attrs={"class": f"callout callout-{type_class}"})
                header = soup.new_tag("div", attrs={"class": "callout-header"})
                header.string = type_label
                body = soup.new_tag("div", attrs={"class": "callout-body"})
                body.string = inner
                callout_div.append(header)
                callout_div.append(body)
                callout_divs.append(callout_div)
            else:
                non_callout_elements.append(p)

        if callout_divs:
            for el in non_callout_elements:
                el.unwrap()
            for el in callout_divs:
                blockquote.insert_before(el)
            blockquote.decompose()

    return str(soup)
