"""Browser smoke tests for I-00033 Code view layout bugs (bugs 1, 2, 3).

Modeled after tests/dashboard/browser/test_chat_panel_smoke.py.
Uses the shared dashboard_server + playwright_session fixtures from conftest.py.

Run with:
    uv run pytest tests/dashboard/browser/test_code_layout_fixes.py -m browser -v
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

# playwright-cli `eval` wraps the return value between `### Result` and the
# trailing `### Ran Playwright code` block — extract just the value.
_EVAL_RESULT_RE = re.compile(r"###\s*Result\s*\n(?P<value>.*?)(?:\n###\s+|\Z)", re.DOTALL)
_SNAPSHOT_LINK_RE = re.compile(r"\[Snapshot\]\((?P<path>[^)]+\.yml)\)")


def _snap(session: str) -> str:
    """Capture a snapshot and inline its YAML body so callers can grep it."""
    out = subprocess.check_output(["playwright-cli", f"-s={session}", "snapshot"], text=True)
    match = _SNAPSHOT_LINK_RE.search(out)
    if not match:
        return out
    yml_path = Path(match.group("path"))
    if not yml_path.is_absolute():
        yml_path = Path.cwd() / yml_path
    body = yml_path.read_text(encoding="utf-8") if yml_path.is_file() else ""
    return out + "\n" + body


def _eval(session: str, code: str) -> str:
    """Evaluate JS in the page and return the result value as a string.

    `code` may be either a `() => ...` arrow function (preferred) or a bare
    expression — the helper wraps bare expressions automatically.
    """
    if not code.lstrip().startswith(("(", "function")):
        code = f"() => ({code})"
    out = subprocess.check_output(["playwright-cli", f"-s={session}", "eval", code], text=True)
    match = _EVAL_RESULT_RE.search(out)
    if not match:
        return out.strip()
    # Strip surrounding quotes from string results: `"foo"` → `foo`.
    value = match.group("value").strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return value


def _click(session: str, selector: str) -> None:
    """Click an element by CSS selector via JS.

    playwright-cli's `click` only takes refs from a snapshot, not CSS selectors,
    so we dispatch a real click() via the DOM API instead.
    """
    _eval(
        session,
        f"() => {{ const el = document.querySelector({selector!r}); if (el) el.click(); }}",
    )


class TestBug1LastRunBannerDismissalPersists:
    """Bug 1: dismissing the banner must persist across reload via localStorage."""

    def test_bug1_last_run_banner_dismissal_persists(self, playwright_session):
        """Dismiss banner → reload → banner is hidden (display:none or absent)."""
        session = playwright_session

        snap_before = _snap(session)
        if "code-last-run-banner" not in snap_before:
            pytest.skip("No 'last run' banner present — no completed job in DB")

        close_btn_snap = _snap(session)
        assert 'aria-label="Dismiss last-run banner"' in close_btn_snap, (
            "Close button with aria-label='Dismiss last-run banner' must exist (I-00033 bug 1)"
        )

        _click(session, '[aria-label="Dismiss last-run banner"]')

        is_hidden = _eval(
            session,
            "String(document.getElementById('code-last-run-banner') === null || "
            "getComputedStyle(document.getElementById('code-last-run-banner')).display === 'none')",
        )
        assert is_hidden == "true", (
            "Banner must be hidden immediately after clicking dismiss (I-00033 bug 1)"
        )

        subprocess.run(
            ["playwright-cli", "-s=" + session, "reload"],
            check=True,
            capture_output=True,
            timeout=15,
        )

        snap_after = _snap(session)
        banner_absent = (
            "code-last-run-banner" not in snap_after.lower()
            or "dismiss last-run banner" not in snap_after.lower()
        )
        assert banner_absent, (
            "After reload, the banner must still be absent — dismissal persisted "
            "via localStorage (I-00033 bug 1)"
        )


class TestBug2ScrollContainerIsArchitectureCard:
    """Bug 2: scroll container is the Architecture card, not #code-content-root."""

    def test_bug2_scroll_container_is_architecture_card(self, playwright_session):
        """Nearest overflow-y:auto ancestor of .prose-doc is the card, not column."""
        session = playwright_session

        val = _eval(
            session,
            "(function(){"
            "var p=document.querySelector('.prose-doc');"
            "if(!p)return 'NO_PROSE';"
            "var e=p;"
            "while(e){"
            "var y=getComputedStyle(e).overflowY;"
            "if(y==='auto')return (e.className||'')+'|id='+(e.id||'');"
            "e=e.parentElement;"
            "}"
            "return 'NONE';"
            "})()",
        )

        assert val != "NO_PROSE", ".prose-doc element not found — is architecture content loaded?"
        assert "id=code-content-root" not in val, (
            "#code-content-root must NOT be the scroll container — "
            "the scroll container must be the Architecture card (I-00033 bug 2)"
        )
        assert "bg-card" in val or "h-full" in val, (
            f"The scroll container must have bg-card (the Architecture card) — "
            f"got: {val!r} (I-00033 bug 2)"
        )


class TestBug3ChatCollapseTogglesCssVariable:
    """Bug 3: collapsing the chat sets --chat-width to 48px via CSS variable."""

    def test_bug3_chat_collapse_shrinks_grid_track(self, playwright_session):
        """Collapse chat → --chat-width==48px AND text column grows; expand → restored."""
        session = playwright_session

        initial_chat_width = _eval(
            session,
            "getComputedStyle(document.documentElement).getPropertyValue('--chat-width').trim()",
        )

        _click(session, "#chat-collapse-btn")

        collapsed_chat_width = _eval(
            session,
            "getComputedStyle(document.documentElement).getPropertyValue('--chat-width').trim()",
        )
        assert collapsed_chat_width == "48px", (
            f"After collapse, --chat-width must be '48px' (not {collapsed_chat_width!r}) — "
            "the grid track CSS variable must be updated, not just the inline width "
            "(I-00033 bug 3)"
        )

        _click(session, "#chat-collapse-btn")

        restored_chat_width = _eval(
            session,
            "getComputedStyle(document.documentElement).getPropertyValue('--chat-width').trim()",
        )
        assert restored_chat_width == initial_chat_width, (
            f"After expand, --chat-width must be restored to {initial_chat_width!r} "
            f"(not {restored_chat_width!r}) — the CSS variable must be restored from "
            "the saved chatWidth, not clobbered (I-00033 bug 3)"
        )
