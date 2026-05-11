"""Tests for I-00078: Dashboard layout — invisible dark-mode scrollbars, double
vertical scrollbar hiding the footer, and a full-width footer with the theme toggle
inside it.

Verifies:
1. Footer is a full-width sibling of the sidebar (not nested in the content column).
2. Theme toggle lives in the footer, not the sidebar.
3. App shell uses a dynamic-viewport unit (h-dvh / 100dvh).
4. .iw-pipeline-strip has bottom padding for scrollbar spacing.
5. Dark-mode scrollbar thumb uses high-contrast colour (not --border) with hover +
   Firefox fallback; --scrollbar-thumb CSS var is defined.
6. Theme toggle is outside the htmx swap target (not wiped by poll refresh).
7. Exactly one content scroller: <main overflow-y-auto>, shell/body overflow-hidden.
8. Theme toggle still wired after the move (onclick present, id="theme-icon" unique).

All tests MUST fail on pre-fix base.html / theme.css / styles.css and pass on
the fix branch.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
THEME_CSS = REPO_ROOT / "dashboard/static/theme.css"
STYLES_CSS = REPO_ROOT / "dashboard/static/styles.css"


# ---------------------------------------------------------------------------
# Client fixture — mirrors the style used in all other dashboard tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a TestClient that overrides get_db to use the test db_session."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# AC3 / AC4 — footer structural invariants
# ---------------------------------------------------------------------------


def test_i00078_footer_is_full_width_sibling_of_sidebar(client: TestClient):
    """The LLM-usage footer must NOT be nested inside the main content column;
    it must be a sibling of the [sidebar + content] row so it spans the full
    window width. Pre-fix this FAILS because <footer> sits inside the .flex-1
    main column."""
    html = client.get("/").text

    # The sidebar <aside id="sidebar"> ... </aside> closes before <footer> opens.
    aside_end = html.index("</aside>")
    footer_start = html.index("<footer")
    assert footer_start > aside_end, "footer must come after the sidebar closes"

    # The <footer> opening tag must carry a full-width class (w-full).
    footer_tag = html[footer_start : footer_start + 400]
    assert re.search(r'\bclass="[^"]*\bw-full\b[^"]*"', footer_tag), (
        "footer must carry w-full so it spans the full window width"
    )

    # The old fixed-viewport shell wrapper must be absent.
    assert 'class="flex h-screen overflow-hidden"' not in html, (
        "the old h-screen shell wrapper must be gone"
    )


def test_i00078_theme_toggle_in_footer_not_sidebar(client: TestClient):
    """The 'Toggle theme' button moved from the sidebar into the footer.
    Pre-fix this FAILS — the button is inside <aside id="sidebar">."""
    html = client.get("/").text

    # Slice the sidebar and confirm toggle is NOT in it.
    aside_start = html.index('id="sidebar"')
    aside_end = html.index("</aside>", aside_start)
    sidebar_html = html[aside_start:aside_end]
    assert "toggleDarkMode()" not in sidebar_html, "theme toggle must no longer be in the sidebar"

    # Slice the footer and confirm toggle IS in it.
    footer_start = html.index("<footer")
    footer_end = html.index("</footer>", footer_start)
    footer_html = html[footer_start:footer_end]
    assert "toggleDarkMode()" in footer_html, "theme toggle must be inside the footer"


def test_i00078_theme_toggle_outside_htmx_swap_target(client: TestClient):
    """The htmx poll target (hx-swap="innerHTML") must NOT contain the toggle.
    Regression guard: a poll that swaps the wrong element wipes the button.
    Pre-fix this FAILS — before the fix the hx-swap was on <footer> itself."""
    html = client.get("/").text

    footer_start = html.index("<footer")
    footer_end = html.index("</footer>", footer_start)
    footer_html = html[footer_start:footer_end]

    # The hx-swap="innerHTML" lives on an inner <div> (the meters container).
    # Find it and confirm toggleDarkMode() is NOT inside it.
    swap_attr = 'hx-swap="innerHTML"'
    swap_pos = footer_html.find(swap_attr)
    assert swap_pos != -1, 'hx-swap="innerHTML" attribute must be present in the footer'

    # Find the start of the element carrying the attribute (the opening <div ...>).
    # Scan backwards from swap_pos to the '<' of the opening tag.
    tag_start = footer_html.rfind("<", 0, swap_pos)
    assert tag_start != -1, "could not find opening tag for hx-swap element"

    # Find the matching close tag — walk forward from tag_start to the first </div>.
    depth = 0
    pos = tag_start
    while pos < len(footer_html):
        if footer_html[pos : pos + 5] == "<div ":
            depth += 1
        elif footer_html[pos : pos + 6] == "</div>":
            depth -= 1
            if depth == 0:
                break
        pos += 1

    swap_subtree = footer_html[tag_start : pos + 6]
    assert "toggleDarkMode()" not in swap_subtree, (
        "toggleDarkMode() must not be inside the htmx-swap subtree — "
        "a poll refresh would wipe the button"
    )


# ---------------------------------------------------------------------------
# AC3 — single vertical scrollbar / dynamic viewport
# ---------------------------------------------------------------------------


def test_i00078_shell_uses_dynamic_viewport_height(client: TestClient):
    """The app shell must be sized with a dynamic-viewport unit (h-dvh / 100dvh)
    rather than h-screen / 100vh, so it does not overflow the visual viewport.
    Pre-fix this FAILS — base.html uses h-screen."""
    html = client.get("/").text

    assert ("h-dvh" in html) or ("100dvh" in html), (
        "shell height should use a dynamic viewport unit (h-dvh / 100dvh)"
    )

    # The old fixed-viewport shell wrapper must be gone.
    assert 'class="flex h-screen overflow-hidden"' not in html, (
        "the old h-screen / fixed-viewport shell wrapper must be absent"
    )


def test_i00078_only_main_is_the_scroller(client: TestClient):
    """<main> must carry overflow-y-auto (the designated content scroller),
    and the shell / <body> must carry overflow-hidden so there is exactly one
    content scrollbar. Pre-fix this FAILS — body itself scrolls."""
    html = client.get("/").text

    # <main> must exist and carry overflow-y-auto.
    main_tag_match = re.search(r"<main\b[^>]*>", html)
    assert main_tag_match, "<main> tag not found"
    main_tag = main_tag_match.group(0)
    assert re.search(r"\boverflow-y-auto\b", main_tag), (
        "<main> must carry overflow-y-auto so it is the content scroller"
    )

    # The <body> (or shell wrapper) must carry overflow-hidden.
    body_match = re.search(r"<body\b[^>]*>", html)
    assert body_match, "<body> tag not found"
    body_tag = body_match.group(0)
    assert re.search(r"\boverflow-hidden\b", body_tag), (
        "<body> must carry overflow-hidden to prevent a second scrollbar"
    )


# ---------------------------------------------------------------------------
# AC2 — pipeline strip scrollbar spacing
# ---------------------------------------------------------------------------


def test_i00078_pipeline_strip_has_scrollbar_spacing():
    """.iw-pipeline-strip must carry bottom padding so the horizontal scrollbar
    is separated from the step pills. Pre-fix this FAILS — no padding-bottom."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    # Find the .iw-pipeline-strip { ... } block.
    m = re.search(r"\.iw-pipeline-strip\s*\{([^}]*)\}", css)
    assert m, ".iw-pipeline-strip rule must exist in styles.css"

    block = m.group(1)

    # Must declare padding-bottom (or padding shorthand) with a non-zero value.
    # We split into two checks for clarity:
    # 1. The property must exist somewhere in the block.
    has_padding = re.search(r"padding(?:-bottom)?\s*:", block)
    assert has_padding, ".iw-pipeline-strip must declare padding (or padding-bottom)"

    # 2. The value must not be exactly 0 or 0px (anything else is fine).
    padding_val = re.search(r"padding(?:-bottom)?:\s*([^;]+)", block)
    assert padding_val, "could not parse padding value"
    value = padding_val.group(1).strip()
    assert value not in ("0", "0px"), f".iw-pipeline-strip padding must be non-zero, got: {value}"


# ---------------------------------------------------------------------------
# AC1 — dark-mode scrollbar visibility
# ---------------------------------------------------------------------------


def test_i00078_dark_scrollbar_high_contrast_thumb():
    """Dark-mode scrollbar thumb must not be painted with the low-contrast
    --border token; there must also be a :hover state, Firefox fallback,
    and a --scrollbar-thumb CSS var defined in both :root and .dark.
    Pre-fix this FAILS — thumb used var(--border)."""
    css = THEME_CSS.read_text(encoding="utf-8")

    # 1. The ::-webkit-scrollbar-thumb block must exist.
    m = re.search(r"::-webkit-scrollbar-thumb\s*\{([^}]*)\}", css)
    assert m, "::-webkit-scrollbar-thumb rule must exist in theme.css"

    # 2. It must NOT use var(--border) — the pre-fix bug.
    thumb_block = m.group(1)
    assert "var(--border)" not in thumb_block, (
        "scrollbar thumb must not use var(--border) — "
        "it is nearly invisible against the dark background"
    )

    # 3. Must have a hover state.
    assert "::-webkit-scrollbar-thumb:hover" in css, (
        "::-webkit-scrollbar-thumb:hover rule must exist"
    )

    # 4. Firefox scrollbar-color and scrollbar-width declarations must exist.
    assert "scrollbar-color" in css, "needs Firefox scrollbar-color"
    assert "scrollbar-width" in css, "needs Firefox scrollbar-width"

    # 5. --scrollbar-thumb CSS custom property must be defined in :root.
    root_block = re.search(r":root\s*\{([^}]*)\}", css, re.DOTALL)
    assert root_block, ":root block not found in theme.css"
    assert "--scrollbar-thumb" in root_block.group(1), "--scrollbar-thumb must be defined in :root"

    # 6. --scrollbar-thumb must also be defined in .dark.
    dark_block = re.search(r"\.dark\s*\{([^}]*)\}", css, re.DOTALL)
    assert dark_block, ".dark block not found in theme.css"
    assert "--scrollbar-thumb" in dark_block.group(1), (
        "--scrollbar-thumb must be redefined in .dark"
    )


# ---------------------------------------------------------------------------
# AC4 — theme toggle still wired after the move
# ---------------------------------------------------------------------------


def test_i00078_theme_toggle_still_wired(client: TestClient):
    """The footer's toggle button must still have onclick="toggleDarkMode()"
    and there must be exactly one id="theme-icon" element in the page.
    Pre-fix this FAILS — the button was in the sidebar with no footer entry."""
    html = client.get("/").text

    footer_start = html.index("<footer")
    footer_end = html.index("</footer>", footer_start)
    footer_html = html[footer_start:footer_end]

    # The button must carry the onclick handler.
    toggle_btn_match = re.search(r"<button[^>]*toggleDarkMode\(\)[^>]*>", footer_html)
    assert toggle_btn_match, 'footer must contain a <button onclick="toggleDarkMode()">'

    # There must be exactly one id="theme-icon" in the whole page.
    theme_icon_count = html.count('id="theme-icon"')
    assert theme_icon_count == 1, (
        f'there must be exactly one id="theme-icon", found {theme_icon_count}'
    )
