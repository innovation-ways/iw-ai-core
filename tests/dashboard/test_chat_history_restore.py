"""TDD RED tests for CR-00063 S01 — Restore Chat Message History on Browser Reload.

These tests verify that:
  1. `_loadTabHistory` renders tool-call and tool-result parts from history.
  2. `_loadTabHistory` surfaces errors to the user instead of swallowing them.
  3. `_bootstrapTabs` falls back to the most recently active tab by `last_active_at`.

All assertions are regex/grep-based against the vanilla-ES5 chat.js source,
consistent with the patterns in test_chat_panel_event_protocol.py.
"""

from __future__ import annotations

import re
from pathlib import Path

CHAT_JS = Path(__file__).resolve().parents[2] / "dashboard/static/chat_assistant/chat.js"


def _extract_function_body(js_source: str, fn_name: str) -> str | None:
    """Return the body text of the named function, or None if not found.

    Searches for a ``function <fn_name>(`` declaration and returns everything
    up to the next top-level closing ``}`` on its own line.  Handles the fact
    that the body may contain nested function expressions (e.g. ``.then()``)
    and does not terminate early on those inner closing braces.
    """
    # Find the function start
    start_pat = r"function\s+" + re.escape(fn_name) + r"\b"
    start_m = re.search(start_pat, js_source)
    if not start_m:
        return None
    # Scan character-by-character from the start, counting brace depth.
    # Depth starts at 0 before the opening brace and becomes 1 at it.
    depth = 0
    i = start_m.start()
    started = False
    while i < len(js_source):
        ch = js_source[i]
        if ch == "{":
            depth += 1
            started = True
        elif ch == "}":
            depth -= 1
            if started and depth == 0:
                # Include the closing brace and the trailing newline
                end = i + 1
                while end < len(js_source) and js_source[end] == "\n":
                    end += 1
                return js_source[start_m.start() : end]
        elif ch == "\n" and not started:
            # keep scanning
            pass
        i += 1
    return None


def test_load_tab_history_renders_tool_calls() -> None:
    """`_loadTabHistory` must call `_appendToolCall` for each tool-use part.

    Before the fix the loop only handled role === 'user' and role === 'assistant'
    text messages, silently skipping tool calls. After the fix the loop must
    also iterate over parts and invoke `_appendToolCall` for type === 'tool-use'
    (or 'tool_use').
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    body = _extract_function_body(js, "_loadTabHistory")
    assert body is not None, "_loadTabHistory function not found in chat.js"
    assert body.count("_appendToolCall") >= 1, (
        "_loadTabHistory must call _appendToolCall for tool-use parts "
        "(opencode 'tool-use' / Pi 'tool_use')"
    )


def test_load_tab_history_renders_tool_results() -> None:
    """`_loadTabHistory` must call `_appendToolResult` for each tool-result part."""
    js = CHAT_JS.read_text(encoding="utf-8")
    body = _extract_function_body(js, "_loadTabHistory")
    assert body is not None, "_loadTabHistory function not found in chat.js"
    assert body.count("_appendToolResult") >= 1, (
        "_loadTabHistory must call _appendToolResult for tool-result parts "
        "(opencode 'tool-result' / Pi 'tool_result')"
    )


def test_load_tab_history_removes_silent_error_suppression() -> None:
    """`_loadTabHistory` must not swallow errors silently.

    The pre-fix `.catch(function () { /* silently ignore */ })` leaves the user
    with an empty panel and no feedback on 503 / 404 / network errors.
    After the fix the catch handler must call `_appendSystemMessage`.
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    body = _extract_function_body(js, "_loadTabHistory")
    assert body is not None, "_loadTabHistory function not found in chat.js"
    assert "silently ignore" not in body, (
        "_loadTabHistory still contains 'silently ignore' — "
        "the silent .catch suppression must be replaced with a user-visible error"
    )


def test_load_tab_history_throws_on_non_ok() -> None:
    """Non-200 responses must throw so the .catch handler fires and shows an error.

    The pre-fix guard is `if (!r.ok) return null;` which silently skips rendering.
    After the fix it must `throw new Error('HTTP ' + r.status)` so errors are
    surfaced via `_appendSystemMessage`.
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    body = _extract_function_body(js, "_loadTabHistory")
    assert body is not None, "_loadTabHistory function not found in chat.js"
    assert body.count("throw new Error") >= 1, (
        "_loadTabHistory must throw on non-ok response so .catch fires "
        "and displays an error to the user"
    )


def test_bootstrap_tabs_uses_last_active_at_fallback() -> None:
    """`_bootstrapTabs` must select the most recently active tab when sessionStorage is cleared.

    Before the fix: `_activateTab(target ? target.id : _tabs[0].id)` always fell
    back to index 0 when the stored tab ID was stale or absent. After the fix the
    fallback must compare `last_active_at` timestamps across tabs and pick the highest.
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    body = _extract_function_body(js, "_bootstrapTabs")
    assert body is not None, "_bootstrapTabs function not found in chat.js"
    assert body.count("last_active_at") >= 1, (
        "_bootstrapTabs must compare `last_active_at` timestamps to pick the "
        "most recently active tab when sessionStorage is cleared, "
        "instead of blindly falling back to _tabs[0]"
    )
