"""Markdown to HTML rendering for the IW AI Core dashboard."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import markdown as md_lib
from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from bs4.element import Tag

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mermaid → SVG rendering helpers
# ---------------------------------------------------------------------------

_MERMAID_CODE_RE = re.compile(
    r'<pre><code class="language-mermaid">(.*?)</code></pre>',
    re.DOTALL,
)

# Puppeteer config for headless Chromium (no sandbox for Linux/WSL)
_PUPPETEER_CONFIG = '{"args":["--no-sandbox","--disable-setuid-sandbox"]}'

# Path to the Playwright-managed Chromium binary used by mmdc
_PLAYWRIGHT_CHROME = (
    Path.home() / ".cache" / "ms-playwright" / "chromium-1217" / "chrome-linux64" / "chrome"
)


def _sanitize_mermaid(source: str) -> str:
    """Apply lightweight fixes for common Mermaid syntax problems.

    Rules applied:

    1. **Sequence diagram semicolons** — arrow-label text containing `;` confuses
       the parser (``CLI->>DB: BEGIN; SELECT FOR UPDATE``).  Replace `;` in labels
       with `,`.

    2. **Bracket/paren inside unquoted node label** — ``{pid}``, ``[pid]``, or
       ``(pid)`` inside a ``NodeID[...]`` label triggers shape parsing.  Convert
       the whole unquoted ``[label]`` to ``["label"]`` (double-quoted labels allow
       arbitrary text including brackets).  Quoted labels like ``NodeID["..."]``
       and subgraph headers like ``subgraph X["..."]`` are left untouched.

    3. **state-v2 → stateDiagram-v2** — LLMs sometimes write the shorthand;
       Mermaid only recognises ``stateDiagram-v2``.

    4. **ELK layout removed for non-flowchart diagrams** — the ELK renderer is
       only valid for ``flowchart``/``graph`` diagrams.  Applying it to
       ``sequenceDiagram``, ``erDiagram``, ``stateDiagram-v2``, etc. breaks
       rendering.  Strip the ``---\\nconfig:\\n  layout: elk\\n---`` frontmatter
       when the diagram type is not a flowchart or graph.
    """
    # Rule 3: state-v2 → stateDiagram-v2
    source = re.sub(r"\bstate-v2\b", "stateDiagram-v2", source)

    # Rule 5: strip '?' from node IDs (invalid in Mermaid)
    # Matches bareword node IDs ending in '?' before whitespace, '[', '{', '(', or '>'
    # e.g. "has_batches?" → "has_batches", "all_proj_done?" → "all_proj_done"
    source = re.sub(r"(\b\w[\w-]*)\?(?=[\s\[\{>\(|]|$)", r"\1", source)

    # Rule 6: replace [*] in flowchart context (stateDiagram-only syntax)
    if re.search(r"^\s*(flowchart|graph)\b", source, re.MULTILINE | re.IGNORECASE):
        source = source.replace("--> [*]", '--> end_node["End"]')
        source = source.replace("[*] -->", 'start_node["Start"] -->')

    # Rule 8: join multi-line flowchart arrows — LLMs sometimes write
    #   nodeId
    #   -->|label| target
    # which is invalid; join so the arrow is on the same line as the source.
    # Only applies inside flowchart/graph blocks (not sequence/stateDiagram).
    if re.search(r"^\s*(flowchart|graph)\b", source, re.MULTILINE | re.IGNORECASE):
        _multiline_arrow = re.compile(
            r"^(\s*)(\w[\w-]*)\s*\n\s*\n?\s*(-->|-.->|==>)(.*)$",
            re.MULTILINE,
        )
        # Iterate to handle multiple consecutive splits; limit iterations to avoid loops
        for _ in range(10):
            new_source = _multiline_arrow.sub(r"\1\2 \3\4", source)
            if new_source == source:
                break
            source = new_source

    lines = source.splitlines()

    # Detect the diagram type (first non-frontmatter line that looks like a type)
    _elk_frontmatter_re = re.compile(
        r"^---\s*\nconfig:\s*\n\s+layout:\s*elk\s*\n---\s*\n", re.MULTILINE
    )
    _flowchart_types = re.compile(r"^\s*(flowchart|graph)\b", re.IGNORECASE)
    # Strip ELK layout for diagram types that don't support it (Rule 4)
    if _elk_frontmatter_re.search(source):
        non_front = _elk_frontmatter_re.sub("", source, count=1).lstrip()
        first_content_line = non_front.splitlines()[0] if non_front else ""
        if not _flowchart_types.match(first_content_line):
            source = _elk_frontmatter_re.sub("", source, count=1)
            lines = source.splitlines()

    in_sequence = any(line.strip().lower() == "sequencediagram" for line in lines)

    # Arrow pattern for sequence diagrams (labels after ':')
    _arrow_re = re.compile(r"^(\s*\S+\s*(?:->>|-->|->>|->)\s*\S+\s*:)(.*)")

    # Node definition: NodeId[label...]
    # We only rewrite unquoted labels — those that DON'T already start with "
    # Pattern: word chars, then '[' not immediately followed by '"'
    _unquoted_node = re.compile(r"^(\s*\w[\w-]*)\[(?!\")")

    # Pattern to detect brackets/parens that need quoting inside node labels
    bracket_chars = re.compile(r"[{}\[\]()]")

    fixed: list[str] = []
    for line in lines:
        # Rule 1: sequence diagram arrow semicolons
        if in_sequence:
            m = _arrow_re.match(line)
            if m:
                label = m.group(2).replace(";", ",")
                line = m.group(1) + label

        # Skip %%{init:...}%% frontmatter
        if line.strip().startswith("%%"):
            fixed.append(line)
            continue

        # Rule 2: convert NodeId[label] → NodeId["label"] if label has brackets
        m2 = _unquoted_node.match(line)
        if m2:
            rest_after_bracket = line[m2.end() :]  # everything after the opening '['
            # Find the matching closing ']' at the top level
            depth = 1
            end_idx = None
            for ci, ch in enumerate(rest_after_bracket):
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        end_idx = ci
                        break
            if end_idx is not None:
                label_content = rest_after_bracket[:end_idx]
                suffix = rest_after_bracket[end_idx + 1 :]  # after the closing ']'
                if bracket_chars.search(label_content):
                    # Wrap in double quotes; escape any existing double quotes
                    quoted_label = label_content.replace('"', "&quot;")
                    line = m2.group(1) + '["' + quoted_label + '"]' + suffix

        fixed.append(line)
    return "\n".join(fixed)


def _render_mermaid_to_svg(mermaid_source: str) -> str | None:
    """Render a Mermaid diagram source string to an SVG string using mmdc.

    Applies lightweight sanitization before rendering.  Falls back to
    Kroki.io if mmdc fails (e.g. complex diagrams that trip up the local
    Mermaid version).

    Returns the SVG string on success, or None if all methods fail.
    """
    sanitized = _sanitize_mermaid(mermaid_source)

    # --- Primary: local mmdc ---
    svg = _render_mermaid_mmdc(sanitized)
    if svg is not None:
        return svg

    # --- Fallback: Kroki.io REST API ---
    svg = _render_mermaid_kroki(sanitized)
    if svg is not None:
        logger.debug("Used Kroki.io fallback for a diagram")
    return svg


def _render_mermaid_mmdc(mermaid_source: str) -> str | None:
    """Render Mermaid to SVG using the local mmdc (npx @mermaid-js/mermaid-cli)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mmd_path = Path(tmpdir) / "diagram.mmd"
        svg_path = Path(tmpdir) / "diagram.svg"
        cfg_path = Path(tmpdir) / "puppeteer.json"

        mmd_path.write_text(mermaid_source, encoding="utf-8")
        cfg_path.write_text(_PUPPETEER_CONFIG, encoding="utf-8")

        env = os.environ.copy()
        if _PLAYWRIGHT_CHROME.exists():
            env["PUPPETEER_EXECUTABLE_PATH"] = str(_PLAYWRIGHT_CHROME)

        try:
            result = subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "npx",
                    "@mermaid-js/mermaid-cli",
                    "-i",
                    str(mmd_path),
                    "-o",
                    str(svg_path),
                    "-b",
                    "white",
                    "--puppeteerConfigFile",
                    str(cfg_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.debug("mmdc failed: %s", exc)
            return None

        if result.returncode != 0:
            logger.debug("mmdc exited %d: %s", result.returncode, result.stderr[:500])
            return None

        if not svg_path.exists() or svg_path.stat().st_size < 100:
            logger.debug("mmdc produced no usable SVG for diagram")
            return None

        return svg_path.read_text(encoding="utf-8")


def _render_mermaid_kroki(mermaid_source: str) -> str | None:
    """Render Mermaid to SVG via the Kroki.io REST API (fallback).

    Sends the diagram source as plain text to https://kroki.io/mermaid/svg.
    Returns the SVG string, or None on any error.
    """
    import base64
    import zlib

    try:
        compressed = zlib.compress(mermaid_source.encode("utf-8"), 9)
        encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
        url = f"https://kroki.io/mermaid/svg/{encoded}"

        result = subprocess.run(  # noqa: S603
            ["curl", "-sf", "--max-time", "15", url],  # noqa: S607
            capture_output=True,
            timeout=20,
        )
        if result.returncode != 0:
            logger.debug("Kroki.io curl failed (rc=%d)", result.returncode)
            return None
        svg = result.stdout.decode("utf-8", errors="replace")
        if "<svg" not in svg:
            logger.debug("Kroki.io returned non-SVG content")
            return None
        return svg
    except Exception as exc:
        logger.debug("Kroki.io fallback failed: %s", exc)
        return None


def _render_mermaid_blocks(html_text: str) -> str:
    """Replace ``<pre><code class="language-mermaid">`` blocks with inline SVGs.

    Falls back to the original ``<pre><code>`` block when all rendering
    methods fail, so the document still displays the raw Mermaid source.
    """

    def _replace(match: re.Match[str]) -> str:
        import html as html_mod

        raw = html_mod.unescape(match.group(1))
        svg = _render_mermaid_to_svg(raw)
        if svg is None:
            # All methods failed — keep the original code block as fallback
            return match.group(0)
        return (
            '<div class="mermaid-diagram" style="overflow-x:auto;margin:1rem 0;">' + svg + "</div>"
        )

    return _MERMAID_CODE_RE.sub(_replace, html_text)


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


def render_markdown_with_callouts(text: str | None, render_mermaid: bool = True) -> str:
    """Convert markdown to HTML and post-process GitHub-style callout blockquotes.

    Converts ``<blockquote><p>[!TYPE]...</p></blockquote>`` patterns into
    ``<div class="callout callout-{type}">`` elements with a header row and body.

    When ``render_mermaid`` is True (the default), any fenced ``mermaid`` code
    blocks are rendered to inline SVG via mmdc before the HTML is returned.
    If mmdc is unavailable or a diagram fails to render, the original code block
    is preserved as a fallback.
    """
    result = render_markdown(text)
    if render_mermaid and "language-mermaid" in result:
        result = _render_mermaid_blocks(result)
    return _convert_callout_blockquotes(result)


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
