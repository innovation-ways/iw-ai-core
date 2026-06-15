"""Innovation Ways brand source-of-truth for document rendering.

Loads ``ai-dev/doc-system/brand/brand.json`` once and derives every brand artifact the
rendering pipeline needs from that single file: the colour palette, the Mermaid
``themeVariables`` config, an embeddable Inter ``@font-face`` block (base64 from
``dashboard/static/fonts/inter/*.woff2``), and Innovation Ways logo markup drawn
from ``ai-dev/iw-assets/``.

Every consumer — the server-side Mermaid renderer, the client-side Mermaid init,
the PDF template, and the HTML-view fallback — reads from here so the brand can
never drift across surfaces again. Resolution is cached; call
:func:`reset_brand_cache` in tests that mutate ``brand.json``.
"""

from __future__ import annotations

import base64
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Repo root = two levels up from dashboard/utils/branding.py
_PLATFORM_ROOT = Path(__file__).resolve().parents[2]
_BRAND_JSON = _PLATFORM_ROOT / "ai-dev" / "doc-system" / "brand" / "brand.json"
_INTER_FONT_DIR = _PLATFORM_ROOT / "dashboard" / "static" / "fonts" / "inter"
_ASSETS_DIR = _PLATFORM_ROOT / "ai-dev" / "iw-assets"

# Inter weights shipped as subsetted woff2 in the static fonts dir.
_INTER_WEIGHTS = (("400", 400), ("500", 500), ("600", 600), ("700", 700))

# Mermaid diagram types whose graph-based layout benefits from the ELK engine.
# Sequence/gantt/pie/journey/timeline ignore (or break under) a layout override,
# so ELK is only requested for this family.
_ELK_DIAGRAM_RE = (
    "flowchart",
    "graph",
    "statediagram",
    "classdiagram",
    "erdiagram",
)

# Fallback palette + diagram theme used only if brand.json is missing/corrupt,
# so rendering degrades to a sane on-brand default instead of crashing.
_FALLBACK_BRAND: dict[str, Any] = {
    "name": "Innovation Ways",
    "colors": {
        "primary": "#1A1D23",
        "ink": "#1A1D23",
        "accent": "#0D9488",
        "accentStrong": "#115E59",
        "accentLight": "#CCFBF1",
        "background": "#F8FAFC",
        "surface": "#FFFFFF",
        "border": "#E2E8F0",
        "text": "#1A1D23",
        "textMuted": "#71757E",
        "line": "#475569",
    },
    "fonts": {"heading": "Inter", "body": "Inter", "mono": "JetBrains Mono"},
    "logo": {"text": "Innovation Ways"},
    "diagrams": {
        "look": "neo",
        "theme": "base",
        "themeVariables": {
            "primaryColor": "#CCFBF1",
            "primaryTextColor": "#1A1D23",
            "primaryBorderColor": "#0D9488",
            "lineColor": "#475569",
            "background": "#FFFFFF",
            "mainBkg": "#CCFBF1",
            "nodeBorder": "#0D9488",
            "textColor": "#1A1D23",
            "fontFamily": "Inter",
        },
    },
}


@lru_cache(maxsize=1)
def get_brand() -> dict[str, Any]:
    """Return the parsed ``brand.json`` document (cached).

    Returns:
        The full brand dict. Falls back to a built-in on-brand default when
        ``brand.json`` is absent or unparseable so callers never crash.
    """
    try:
        return json.loads(_BRAND_JSON.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load brand.json (%s) — using fallback palette", exc)
        return dict(_FALLBACK_BRAND)


def brand_colors() -> dict[str, str]:
    """Return the brand colour palette (hex strings keyed by semantic name)."""
    colors = get_brand().get("colors", {})
    return colors if isinstance(colors, dict) else dict(_FALLBACK_BRAND["colors"])


def _diagrams() -> dict[str, Any]:
    """Return the ``diagrams`` block, falling back to the default theme."""
    diagrams = get_brand().get("diagrams", {})
    if not isinstance(diagrams, dict) or "themeVariables" not in diagrams:
        return dict(_FALLBACK_BRAND["diagrams"])
    return diagrams


def mermaid_theme_variables() -> dict[str, str]:
    """Return the Mermaid ``base``-theme ``themeVariables`` for the brand."""
    tv = _diagrams().get("themeVariables", {})
    return tv if isinstance(tv, dict) else dict(_FALLBACK_BRAND["diagrams"]["themeVariables"])


def brand_dark_text_token() -> str:
    """Return the enforced dark label colour (ink) without the leading ``#``.

    Used by the diagram wrapper so labels stay legible on any background.
    """
    return str(brand_colors().get("ink", "#1A1D23")).lstrip("#").lower()


def diagram_wants_elk(diagram_source: str | None) -> bool:
    """Return True when the diagram type is graph-based and benefits from ELK.

    Args:
        diagram_source: Raw Mermaid source (the fenced block body). None/empty
            returns False.

    Returns:
        True for flowchart/graph/state/class/ER diagrams, False otherwise
        (sequence, gantt, pie, journey, timeline, mindmap, …).
    """
    if not diagram_source:
        return False
    for raw_line in diagram_source.splitlines():
        line = raw_line.strip().lower()
        if not line or line.startswith(("%%", "---")):
            continue
        return line.startswith(_ELK_DIAGRAM_RE)
    return False


def mermaid_config(*, elk: bool = False) -> dict[str, Any]:
    """Build the Mermaid config dict for the brand (mmdc ``--configFile`` JSON).

    Args:
        elk: When True, request the ELK layout engine (only valid for graph-based
            diagram types — callers should gate on :func:`diagram_wants_elk`).

    Returns:
        A config dict with ``theme``, ``look``, ``themeVariables`` and optionally
        ``layout``.
    """
    diagrams = _diagrams()
    config: dict[str, Any] = {
        "theme": diagrams.get("theme", "base"),
        "look": diagrams.get("look", "neo"),
        "themeVariables": mermaid_theme_variables(),
        # Render labels as native SVG <text> rather than HTML <foreignObject>.
        # foreignObject text is re-laid-out by whatever browser re-renders the
        # SVG (the PDF Chromium pass), so when the embedded brand font differs
        # from the one mmdc measured node widths with, labels clip at the node
        # edge. SVG <text> is measured and positioned once by mmdc and renders
        # identically everywhere — no clipping. It also sidesteps the
        # foreignObject incompatibilities that ruled out WeasyPrint.
        "flowchart": {"htmlLabels": False, "useMaxWidth": True},
        "class": {"htmlLabels": False},
    }
    if elk:
        config["layout"] = "elk"
    return config


def mermaid_config_json(*, elk: bool = False) -> str:
    """Return :func:`mermaid_config` serialised to a JSON string."""
    return json.dumps(mermaid_config(elk=elk))


def mermaid_init_directive(*, elk: bool = False) -> str:
    """Return a ``%%{init: ...}%%`` directive carrying the brand theme.

    Used to inject the brand into a diagram source before rendering via engines
    that take no config file (e.g. the Kroki fallback) and on the client side.
    """
    return "%%{init: " + json.dumps(mermaid_config(elk=elk)) + "}%%"


def ensure_brand_init(diagram_source: str, *, elk: bool = False) -> str:
    """Prepend the brand init directive to a diagram unless one already exists.

    If the author already supplied a ``%%{init ...}%%`` block we leave it intact
    (explicit author intent wins); otherwise the brand directive is prepended.

    Args:
        diagram_source: Raw Mermaid source.
        elk: Whether to request ELK layout in the injected directive.

    Returns:
        The diagram source guaranteed to carry an init directive.
    """
    if "%%{init" in diagram_source:
        return diagram_source
    return mermaid_init_directive(elk=elk) + "\n" + diagram_source


def d2_theme_overrides() -> dict[str, str]:
    """Return the D2 ``theme-overrides`` colour-slot map for the brand."""
    overrides = _diagrams().get("d2ThemeOverrides", {})
    return overrides if isinstance(overrides, dict) else {}


def d2_layout() -> str:
    """Return the preferred D2 layout engine (default ``elk``)."""
    return str(_diagrams().get("d2Layout", "elk"))


def d2_brand_preamble() -> str:
    """Return a D2 ``vars.d2-config.theme-overrides`` preamble for brand colours.

    Prepending this to a D2 source recolours every shape/connection with the
    Innovation Ways teal/ink palette — the D2 analogue of the Mermaid
    ``%%{init}%%`` directive. Returns an empty string when no overrides are
    configured.
    """
    overrides = d2_theme_overrides()
    if not overrides:
        return ""
    lines = "\n".join(f'      {slot}: "{hex_}"' for slot, hex_ in overrides.items())
    return "vars: {\n  d2-config: {\n    theme-overrides: {\n" + lines + "\n    }\n  }\n}\n"


def ensure_d2_brand(diagram_source: str) -> str:
    """Prepend the brand D2 preamble unless the source already configures D2.

    Args:
        diagram_source: Raw D2 source.

    Returns:
        The D2 source guaranteed to carry the brand theme overrides (author-
        supplied ``d2-config``/``theme-overrides`` is left untouched).
    """
    if "theme-overrides" in diagram_source or "d2-config" in diagram_source:
        return diagram_source
    preamble = d2_brand_preamble()
    if not preamble:
        return diagram_source
    return preamble + diagram_source


@lru_cache(maxsize=1)
def inter_font_face_css() -> str:
    """Return ``@font-face`` rules embedding Inter as base64 woff2 (cached).

    Embedding guarantees the brand font renders in headless-Chromium PDF output
    regardless of whether Inter is installed on the host. Returns an empty string
    if no font files are found.
    """
    rules: list[str] = []
    for suffix, weight in _INTER_WEIGHTS:
        font_file = _INTER_FONT_DIR / f"Inter-{suffix}.woff2"
        try:
            b64 = base64.b64encode(font_file.read_bytes()).decode("ascii")
        except OSError:
            continue
        rules.append(
            "@font-face{font-family:'Inter';font-style:normal;"
            f"font-weight:{weight};font-display:swap;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}"
        )
    return "".join(rules)


def _asset_path(rel: str | None) -> Path | None:
    """Resolve a brand-relative asset path under the platform repo root."""
    if not rel:
        return None
    candidate = _PLATFORM_ROOT / rel
    return candidate if candidate.is_file() else None


@lru_cache(maxsize=8)
def logo_svg(variant: str = "mark") -> str | None:
    """Return the raw inline SVG markup for a brand logo variant (cached).

    Args:
        variant: One of the keys under ``logo`` in brand.json
            (``mark``, ``markWhite``, ``horizontal``, ``horizontalWhite``,
            ``wordmark``). Defaults to the pure-path ``mark`` (font-safe).

    Returns:
        The SVG file contents, or None when the asset is missing.
    """
    rel = get_brand().get("logo", {}).get(variant)
    path = _asset_path(rel)
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


@lru_cache(maxsize=8)
def logo_data_uri(variant: str = "horizontal") -> str | None:
    """Return a base64 ``data:`` URI for a brand logo variant (cached).

    Suitable for an ``<img src>`` that must resolve inside headless-Chromium PDF
    rendering (no file-path dependency). Returns None when the asset is missing.
    """
    svg = logo_svg(variant)
    if svg is None:
        return None
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def brand_lockup_html() -> str:
    """Return a font-safe header lockup: the inline IW mark + wordmark in Inter.

    The packaged horizontal logo uses live Space-Grotesk ``<text>`` which is not
    guaranteed in PDF output, so the chrome composes the pure-path mark with the
    brand name set in our embedded Inter font instead.
    """
    mark = logo_svg("mark") or ""
    name = get_brand().get("logo", {}).get("text", "Innovation Ways")
    return (
        '<span class="iw-lockup">'
        f'<span class="iw-lockup-mark">{mark}</span>'
        f'<span class="iw-lockup-name">{name}</span>'
        "</span>"
    )


def brand_jinja_globals() -> dict[str, Any]:
    """Return the brand globals to register on the Jinja2 template environment.

    Exposes one consistent brand surface to every template (PDF, client Mermaid
    init, HTML chrome) so they all read from ``brand.json``.
    """
    return {
        "iw_brand": get_brand(),
        "iw_brand_colors": brand_colors(),
        "iw_brand_mermaid_config": mermaid_config(),
        "iw_inter_font_face_css": inter_font_face_css(),
        "iw_logo_mark_svg": logo_svg("mark") or "",
        "iw_logo_data_uri": logo_data_uri("horizontal") or "",
        "iw_brand_lockup_html": brand_lockup_html(),
    }


def reset_brand_cache() -> None:
    """Clear all cached brand lookups (for tests that mutate brand.json)."""
    get_brand.cache_clear()
    inter_font_face_css.cache_clear()
    logo_svg.cache_clear()
    logo_data_uri.cache_clear()
