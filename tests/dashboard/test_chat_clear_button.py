"""Tests for CR-00064 Clear Chat History Button — frontend wiring.

Asserts the composer template ships the clear button with the right
attributes, and that chat.js defines and wires the clear-chat functions.
Each test verifies a specific structural fact that would fail if the
production wiring regressed.
"""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

CHAT_JS = Path(__file__).resolve().parents[2] / "dashboard/static/chat_assistant/chat.js"
COMPOSER_HTML = (
    Path(__file__).resolve().parents[2] / "dashboard/templates/chat_assistant/composer.html"
)


def _js_function_text(js: str, name: str) -> str:
    """Return the full source of JS function ``name`` — its declaration line
    through the matching closing brace.

    Raises AssertionError if the function is missing or its braces are
    unbalanced, so a renamed/removed function fails loudly instead of
    silently passing an ``in`` check against the whole file.
    """
    start = js.find("function " + name)
    assert start != -1, f"function {name} not found in chat.js"
    brace_open = js.find("{", start)
    assert brace_open != -1, f"no opening brace for function {name}"
    depth = 0
    i = brace_open
    while i < len(js):
        if js[i] == "{":
            depth += 1
        elif js[i] == "}":
            depth -= 1
            if depth == 0:
                return js[start : i + 1]
        i += 1
    raise AssertionError(f"unbalanced braces in function {name}")


class TestClearButtonPresent:
    """Tests that the clear conversation button is present in the chat composer."""

    def test_clear_button_present_in_composer(self):
        """Verifies that the clear button is present in the composer template."""
        soup = BeautifulSoup(COMPOSER_HTML.read_text(encoding="utf-8"), "html.parser")
        btn = soup.find(id="chat-assistant-clear")
        assert btn is not None, 'composer.html must contain id="chat-assistant-clear"'
        assert btn.name == "button", f"#chat-assistant-clear must be a <button>, got <{btn.name}>"

    def test_clear_button_starts_disabled(self):
        """Verifies that the clear button starts in a disabled state."""
        soup = BeautifulSoup(COMPOSER_HTML.read_text(encoding="utf-8"), "html.parser")
        btn = soup.find(id="chat-assistant-clear")
        assert btn is not None, "#chat-assistant-clear button not found"
        # The button itself must ship disabled — a fresh tab has no history;
        # the JS enables it once messages exist. Checking the attribute is on
        # the button (not merely the word 'disabled' somewhere in the file).
        assert btn.has_attr("disabled"), (
            "clear button must ship with the 'disabled' attribute so JS toggles it"
        )


class TestClearChatJsFunctions:
    """Tests for the clearChat JavaScript function behavior."""

    def test_clear_chat_function_exists(self):
        """Verifies that the clearChat JavaScript function exists in chat.js."""
        js = CHAT_JS.read_text(encoding="utf-8")
        assert js.count("function _clearChat") == 1, (
            "chat.js must define function _clearChat() exactly once"
        )

    def test_tab_has_history_tracking(self):
        """Verifies that tab state tracks conversation history length."""
        js = CHAT_JS.read_text(encoding="utf-8")
        # A tracker declared but never read does not actually track anything —
        # require at least a declaration plus one use.
        assert js.count("_tabHasHistory") >= 2, (
            "chat.js must declare AND consult _tabHasHistory to track per-tab history"
        )

    def test_update_clear_button_function(self):
        """Verifies that the updateClearButton function exists and updates button state."""
        js = CHAT_JS.read_text(encoding="utf-8")
        assert js.count("function _updateClearButton") == 1, (
            "chat.js must define function _updateClearButton() exactly once"
        )
        # Defining it is pointless unless something invokes it.
        assert js.count("_updateClearButton(") >= 2, (
            "_updateClearButton must be called, not just defined"
        )


class TestClearChatBehavior:
    """Tests for the clear chat action's expected behavior."""

    def test_clear_has_no_confirm(self):
        """Verifies that the clear action does not show a confirm dialog."""
        js = CHAT_JS.read_text(encoding="utf-8")
        body = _js_function_text(js, "_clearChat")
        assert "window.confirm" not in body, (
            "_clearChat must not show a confirmation dialog via window.confirm"
        )

    def test_clear_calls_api(self):
        """Verifies that the clear function calls the API endpoint."""
        js = CHAT_JS.read_text(encoding="utf-8")
        body = _js_function_text(js, "_clearChat")
        # The call must live INSIDE _clearChat, not merely somewhere in chat.js.
        assert body.count("/clear") >= 1, "_clearChat must call the .../clear endpoint"
        assert "POST" in body, "_clearChat must use the POST method to clear history"

    def test_clear_removes_eid(self):
        """Verifies that clearing a tab removes the conversation EID from state."""
        js = CHAT_JS.read_text(encoding="utf-8")
        body = _js_function_text(js, "_clearChat")
        assert body.count("removeItem") >= 1, (
            "_clearChat must call sessionStorage.removeItem after a successful clear"
        )
        assert "iw-chat-last-eid-" in body, (
            "_clearChat must drop the iw-chat-last-eid-<tabId> sessionStorage key"
        )
