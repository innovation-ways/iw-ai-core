"""Markdown to HTML rendering for the IW AI Core dashboard."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import markdown as md_lib
from bs4 import BeautifulSoup

from dashboard.utils.branding import (
    brand_dark_text_token,
    d2_layout,
    diagram_wants_elk,
    ensure_brand_init,
    ensure_d2_brand,
    inter_font_face_css,
    mermaid_config_json,
)
from orch.diagram.sanitize import sanitize_mermaid

if TYPE_CHECKING:
    from bs4.element import Tag

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chromium binary resolution
# ---------------------------------------------------------------------------
# Resolution order (all paths must actually exist to be returned):
#   1. $IW_PLAYWRIGHT_CHROME_PATH  (explicit override — keep this name)
#   2. Newest ~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome  (glob)
#   3. shutil.which("chromium" | "chromium-browser" | "google-chrome" |
#                   "google-chrome-stable")
#   4. None  →  callers degrade gracefully (PDF → 503, mmdc → Kroki fallback)


def _resolve_chromium_binary() -> Path | None:
    """Locate a Chromium/Chrome executable for headless PDF + mmdc rendering.

    Resolution order:
      1. $IW_PLAYWRIGHT_CHROME_PATH, if set and the path exists.
      2. The newest ~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome.
         "Newest" means highest numeric suffix; a Path.glob over ``chromium-*``
         followed by sorting on the integer suffix handles it.
         Only returns a candidate whose ``chrome`` file actually exists.
      3. shutil.which for ``chromium``, ``chromium-browser``, ``google-chrome``,
         ``google-chrome-stable``.
      4. None — callers must degrade gracefully (PDF route → 503,
         mmdc → Kroki fallback), exactly as today.
    """
    # Step 1: env var override
    env_path = os.environ.get("IW_PLAYWRIGHT_CHROME_PATH", "")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate
        # Env var is set but the path does not exist — fall through.

    # Step 2: newest ms-playwright Chromium
    ms_playwright_root = Path.home() / ".cache" / "ms-playwright"
    if ms_playwright_root.is_dir():
        # glob for chromium-* directories, extract numeric suffix, sort descending
        chromium_dirs: list[tuple[int, Path]] = []
        for d in ms_playwright_root.iterdir():
            if not d.is_dir() or not d.name.startswith("chromium-"):
                continue
            suffix_str = d.name.removeprefix("chromium-")
            try:
                suffix = int(suffix_str)
            except ValueError:
                continue
            chrome_bin = d / "chrome-linux64" / "chrome"
            if chrome_bin.is_file():
                chromium_dirs.append((suffix, chrome_bin))

        if chromium_dirs:
            # Pick the highest numbered Chromium version
            chromium_dirs.sort(key=lambda x: x[0], reverse=True)
            return chromium_dirs[0][1]

    # Step 3: PATH lookup
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return Path(found)

    # Step 4: nothing found
    return None


_PLAYWRIGHT_CHROME: Path | None = _resolve_chromium_binary()

_MERMAID_CODE_RE = re.compile(
    r'<pre><code class="language-mermaid">(.*?)</code></pre>',
    re.DOTALL,
)

_D2_CODE_RE = re.compile(
    r'<pre><code class="language-d2">(.*?)</code></pre>',
    re.DOTALL,
)

# Puppeteer config for headless Chromium (no sandbox for Linux/WSL)
_PUPPETEER_CONFIG = '{"args":["--no-sandbox","--disable-setuid-sandbox"]}'


def _resolve_d2_binary() -> Path | None:
    """Locate the ``d2`` executable for server-side D2 diagram rendering.

    Resolution order: ``$IW_D2_PATH`` (if it exists) → ``~/.local/bin/d2`` →
    ``shutil.which("d2")`` → None (callers fall back to Kroki, then raw block).
    """
    env_path = os.environ.get("IW_D2_PATH", "")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    local = Path.home() / ".local" / "bin" / "d2"
    if local.is_file():
        return local
    found = shutil.which("d2")
    return Path(found) if found else None


_D2_BINARY: Path | None = _resolve_d2_binary()


# Paged.js polyfill — vendored under dashboard/static/vendor/pagedjs. Drives the
# CSS Paged Media layout (cover, TOC, per-chapter title pages, running header/
# footer) that doc_pdf.html relies on. Kept here so render_pdf_chromium stays the
# single, shared PDF entry point for every project.
_PAGEDJS_PATH = (
    Path(__file__).resolve().parents[1] / "static" / "vendor" / "pagedjs" / "paged.polyfill.js"
)
_PDF_WORKER = Path(__file__).resolve().parent / "pdf_worker.py"


def render_pdf_chromium(html_content: str, timeout: int = 120) -> bytes | None:
    """Render HTML to PDF via Paged.js in an isolated Playwright subprocess.

    The HTML (from doc_pdf.html) sets ``window.PagedConfig = {auto:false}`` and
    defines ``window.buildLayout`` + a ``before`` hook; the worker injects the
    Paged.js polyfill and runs ``PagedPolyfill.preview()`` so CSS Paged Media
    (named pages, running headers/footers via ``string()``/``element()``,
    ``target-counter`` TOC, cover + per-chapter pages) is fully applied before
    printing — with zero browser margins + ``prefer_css_page_size`` (the @page
    boxes map 1:1) and NO Chromium default date/title header.

    Each render runs in a fresh subprocess (``pdf_worker.py``): the sync
    Playwright API is not safe to re-enter inside the long-lived server, so we
    isolate it the way the previous ``--print-to-pdf`` subprocess did. Chromium
    (not WeasyPrint) is required because Mermaid node labels use SVG
    ``<foreignObject>``. Returns None on any failure (caller falls back to HTML).
    """
    if not _PAGEDJS_PATH.exists():
        logger.warning(
            "Paged.js polyfill missing at %s — PDF generation unavailable", _PAGEDJS_PATH
        )
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = Path(tmpdir) / "doc.html"
        pdf_path = Path(tmpdir) / "doc.pdf"
        html_path.write_text(html_content, encoding="utf-8")
        try:
            result = subprocess.run(  # noqa: S603
                [
                    sys.executable,
                    str(_PDF_WORKER),
                    str(html_path),
                    str(pdf_path),
                    str(_PAGEDJS_PATH),
                ],
                timeout=timeout,
                capture_output=True,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.warning("PDF worker aborted: %s", exc)
            return None
        if result.returncode != 0:
            logger.warning(
                "PDF worker failed (rc=%d): %s",
                result.returncode,
                result.stderr.decode(errors="replace")[:500],
            )
            return None
        if not pdf_path.exists():
            logger.warning("PDF worker ran but no PDF was written")
            return None
        return pdf_path.read_bytes()


def _render_mermaid_to_svg(mermaid_source: str) -> str | None:
    """Render a Mermaid diagram source string to an SVG string using mmdc.

    Applies lightweight sanitization, then renders with the Innovation Ways
    brand theme (base theme + brand themeVariables + Inter + Neo look). Graph-
    based diagrams (flowchart/graph/state/class/ER) additionally request the ELK
    layout engine for cleaner routing. Falls back to Kroki.io — with the brand
    init directive injected into the source — if mmdc fails.

    Returns the SVG string on success, or None if all methods fail.
    """
    sanitized = sanitize_mermaid(mermaid_source)
    elk = diagram_wants_elk(sanitized)

    # --- Primary: local mmdc (brand theme via --configFile) ---
    svg = _render_mermaid_mmdc(sanitized, elk=elk)
    if svg is not None:
        return svg

    # --- Fallback: Kroki.io REST API (brand theme via injected init directive) ---
    svg = _render_mermaid_kroki(ensure_brand_init(sanitized, elk=elk))
    if svg is not None:
        logger.debug("Used Kroki.io fallback for a diagram")
    return svg


def _render_mermaid_mmdc(mermaid_source: str, *, elk: bool = False) -> str | None:
    """Render Mermaid to SVG using the local mmdc (npx @mermaid-js/mermaid-cli).

    Uses the Innovation Ways brand theme (``base`` theme + brand themeVariables +
    Inter + Neo look) passed via ``--configFile`` so on-brand styling survives the
    SVG serialisation even when the LLM-authored source carries no init directive.
    The explicit dark ``primaryTextColor`` (brand ink) keeps ``<foreignObject>``
    labels legible on any background.

    Args:
        mermaid_source: Sanitised Mermaid source.
        elk: Request the ELK layout engine (graph-based diagrams only). If the
            local mmdc build lacks ELK and the render fails, it is retried once
            without the layout override so brand theming is never lost.

    Returns:
        The SVG string, or None when mmdc is unavailable or fails (after the
        no-ELK retry).
    """
    env = os.environ.copy()
    if _PLAYWRIGHT_CHROME is not None and _PLAYWRIGHT_CHROME.exists():
        env["PUPPETEER_EXECUTABLE_PATH"] = str(_PLAYWRIGHT_CHROME)

    def _run(use_elk: bool) -> str | None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mmd_path = Path(tmpdir) / "diagram.mmd"
            svg_path = Path(tmpdir) / "diagram.svg"
            cfg_path = Path(tmpdir) / "puppeteer.json"
            mmd_cfg_path = Path(tmpdir) / "mermaid.json"
            css_path = Path(tmpdir) / "fonts.css"

            mmd_path.write_text(mermaid_source, encoding="utf-8")
            cfg_path.write_text(_PUPPETEER_CONFIG, encoding="utf-8")
            mmd_cfg_path.write_text(mermaid_config_json(elk=use_elk), encoding="utf-8")
            # Make the brand Inter webfont available to mmdc's render page so a
            # diagram that explicitly opts into Inter renders with it. (The
            # default brand diagram font is a Chromium-native sans stack — see
            # brand.json — because async webfont loading races mmdc's node-width
            # measurement and clips labels.)
            css_path.write_text(inter_font_face_css(), encoding="utf-8")

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
                        "#ffffff",
                        "--puppeteerConfigFile",
                        str(cfg_path),
                        "-c",
                        str(mmd_cfg_path),
                        "-C",
                        str(css_path),
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

    svg = _run(elk)
    if svg is None and elk:
        # ELK layout package may be absent in this mmdc build — retry without it
        # so the diagram still renders with brand theming (just dagre layout).
        logger.debug("mmdc ELK render failed — retrying with default layout")
        svg = _run(False)
    return svg


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
        # Wrap in a div that forces the brand ink colour as a safety net: any
        # <foreignObject> label <div> or SVG <text> element inside the SVG will
        # inherit the dark token and not render white-on-white when the host
        # page is in dark mode.
        ink = f"#{brand_dark_text_token()}"
        return (
            '<div class="mermaid-diagram" style="overflow-x:auto;margin:1rem 0;'
            f"background:#ffffff;color:{ink};border-radius:6px;padding:0.5rem;"
            'font-family:Inter,system-ui,sans-serif;">' + svg + "</div>"
        )

    return _MERMAID_CODE_RE.sub(_replace, html_text)


def _sanitize_mermaid_blocks(html_text: str) -> str:
    """Rewrite raw ``language-mermaid`` code blocks with sanitised DSL in place.

    Used on the client-render path (``render_mermaid=False``), where the Mermaid
    blocks are left as ``<pre><code class="language-mermaid">`` for the browser
    to render. The browser runtime never runs
    :func:`orch.diagram.sanitize.sanitize_mermaid`, so this applies the shared
    sanitiser server-side and re-emits the (HTML-escaped) source, keeping the
    client preview consistent with what mmdc renders for the HTML/PDF views.

    Args:
        html_text: HTML produced by the markdown converter.

    Returns:
        The HTML with each Mermaid block's source replaced by its sanitised form.
    """
    import html as html_mod

    def _replace(match: re.Match[str]) -> str:
        raw = html_mod.unescape(match.group(1))
        cleaned = sanitize_mermaid(raw)
        return f'<pre><code class="language-mermaid">{html_mod.escape(cleaned)}</code></pre>'

    return _MERMAID_CODE_RE.sub(_replace, html_text)


def _render_d2_to_svg(d2_source: str) -> str | None:
    """Render a D2 diagram source to an SVG string, brand-themed.

    Prepends the Innovation Ways D2 theme-overrides preamble, then renders with
    the local ``d2`` binary (ELK layout, native SVG — no browser). Falls back to
    the Kroki.io D2 endpoint when the binary is unavailable. Returns None if all
    methods fail.
    """
    branded = ensure_d2_brand(d2_source)

    svg = _render_d2_local(branded)
    if svg is not None:
        return svg

    svg = _render_d2_kroki(branded)
    if svg is not None:
        logger.debug("Used Kroki.io fallback for a D2 diagram")
    return svg


def _render_d2_local(d2_source: str) -> str | None:
    """Render D2 to SVG using the local ``d2`` binary. None on failure/absence."""
    if _D2_BINARY is None or not _D2_BINARY.exists():
        return None
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = Path(tmpdir) / "diagram.d2"
        out_path = Path(tmpdir) / "diagram.svg"
        in_path.write_text(d2_source, encoding="utf-8")
        try:
            result = subprocess.run(  # noqa: S603
                [
                    str(_D2_BINARY),
                    "--layout",
                    d2_layout(),
                    "--pad",
                    "24",
                    str(in_path),
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.debug("d2 failed: %s", exc)
            return None
        if result.returncode != 0:
            logger.debug("d2 exited %d: %s", result.returncode, result.stderr[:500])
            return None
        if not out_path.exists() or out_path.stat().st_size < 100:
            logger.debug("d2 produced no usable SVG for diagram")
            return None
        return out_path.read_text(encoding="utf-8")


def _render_d2_kroki(d2_source: str) -> str | None:
    """Render D2 to SVG via the Kroki.io REST API (fallback). None on error."""
    import base64
    import zlib

    try:
        compressed = zlib.compress(d2_source.encode("utf-8"), 9)
        encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
        url = f"https://kroki.io/d2/svg/{encoded}"
        result = subprocess.run(  # noqa: S603
            ["curl", "-sf", "--max-time", "15", url],  # noqa: S607
            capture_output=True,
            timeout=20,
        )
        if result.returncode != 0:
            logger.debug("Kroki.io D2 curl failed (rc=%d)", result.returncode)
            return None
        svg = result.stdout.decode("utf-8", errors="replace")
        if "<svg" not in svg:
            logger.debug("Kroki.io returned non-SVG content for D2")
            return None
        return svg
    except Exception as exc:
        logger.debug("Kroki.io D2 fallback failed: %s", exc)
        return None


def _render_d2_blocks(html_text: str) -> str:
    """Replace ``<pre><code class="language-d2">`` blocks with inline brand SVGs.

    Falls back to the original ``<pre><code>`` block when rendering fails, so the
    document still displays the raw D2 source.
    """

    def _replace(match: re.Match[str]) -> str:
        import html as html_mod

        raw = html_mod.unescape(match.group(1))
        svg = _render_d2_to_svg(raw)
        if svg is None:
            return match.group(0)
        ink = f"#{brand_dark_text_token()}"
        return (
            '<div class="d2-diagram" style="overflow-x:auto;margin:1rem 0;'
            f'background:#ffffff;color:{ink};border-radius:6px;padding:0.5rem;">' + svg + "</div>"
        )

    return _D2_CODE_RE.sub(_replace, html_text)


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

    Fenced ``d2`` blocks are ALWAYS rendered server-side (regardless of
    ``render_mermaid``) because, unlike Mermaid, D2 has no client-side renderer —
    leaving them unrendered would show raw DSL on the page.
    """
    result = render_markdown(text)
    if "language-mermaid" in result:
        if render_mermaid:
            result = _render_mermaid_blocks(result)
        else:
            # Client-side render path: the browser Mermaid runtime does NOT apply
            # sanitize_mermaid, so rewrite each raw block with the sanitised DSL.
            # Without this the client sees raw LLM DSL — e.g. a ``layout: elk``
            # directive on a ``stateDiagram-v2``, which the browser cannot lay
            # out ("Unknown layout algorithm: elk") and renders as a "Syntax
            # error in text" diagram. Sanitising here keeps the client preview
            # consistent with the server-rendered HTML/PDF.
            result = _sanitize_mermaid_blocks(result)
    if "language-d2" in result:
        result = _render_d2_blocks(result)
    return _convert_callout_blockquotes(result)


def _convert_callout_blockquotes(html: str) -> str:
    """Convert GitHub-style ``[!TYPE]`` blockquotes to styled callout divs.

    Scans the parsed HTML for ``<blockquote>`` elements whose first ``<p>``
    child starts with a ``[!NOTE|TIP|WARNING|DANGER|IMPORTANT]`` marker and
    replaces each with a ``<div class="callout callout-{type}">`` structure
    containing a header and body element.  Blockquotes without a recognised
    marker are left untouched.

    Args:
        html: HTML string produced by the markdown converter.

    Returns:
        HTML string with callout blockquotes transformed into styled divs.
    """
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
