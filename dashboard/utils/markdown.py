"""Markdown to HTML rendering for the IW AI Core dashboard."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import markdown as md_lib
from bs4 import BeautifulSoup

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


def wrap_h2_sections_collapsible(html: str) -> str:
    """Wrap each H2 (and the content following it up to the next H2 or end)
    in a <details> block with a <summary> derived from the H2 text.

    The FIRST H2 in document order is rendered with the ``open`` attribute.
    Subsequent H2s render closed by default. Text outside any H2 (e.g. the
    leading H1 + paragraph) is left untouched.

    Idempotent: running the helper twice is a no-op (the second pass detects
    that H2s are already inside a <details> and returns the input unchanged).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Idempotency: if an H2 is already inside a <summary>, skip wrapping.
    for h2 in soup.find_all("h2"):
        if h2.parent and h2.parent.name in ("summary", "details"):
            return html

    body_tag = soup.find("body")
    body: Tag | BeautifulSoup = body_tag if body_tag else soup
    h2_elements = [el for el in body.find_all(["h2"], recursive=False) if el.parent is body]
    if not h2_elements:
        return html

    for idx, h2 in enumerate(h2_elements):
        is_first = idx == 0
        summary_text = h2.get_text(strip=True)
        h2.clear()

        details = soup.new_tag("details")
        if is_first:
            details["open"] = ""

        summary_tag = soup.new_tag("summary")
        summary_tag.string = summary_text
        details.append(summary_tag)

        sibling = h2.next_sibling
        while sibling is not None:
            next_sibling = sibling.next_sibling
            # Stop when we hit the next H2 (at the body level).
            if isinstance(sibling, str) and sibling.strip() == "":
                sibling = next_sibling
                continue
            if hasattr(sibling, "name") and sibling.name == "h2" and sibling.parent is body:
                break
            details.append(sibling)
            sibling = next_sibling

        h2.insert_before(details)
        details.append(h2)

    return str(soup)
