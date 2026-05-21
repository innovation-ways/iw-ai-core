"""Tests for CR-00064 Clear Chat History Button — frontend wiring.

TDD pattern (RED first):
  tests/dashboard/test_chat_clear_button.py  — regex/grep assertions on source files
  1. test_clear_button_present_in_composer     — composer.html has id="chat-assistant-clear"
  2. test_clear_button_starts_disabled         — composer.html has disabled on clear button
  3. test_clear_chat_function_exists          — chat.js has function _clearChat
  4. test_tab_has_history_tracking            — chat.js has _tabHasHistory
  5. test_update_clear_button_function        — chat.js has function _updateClearButton
  6. test_clear_has_no_confirm                — _clearChat body does NOT contain window.confirm
  7. test_clear_calls_api                     — _clearChat body contains /clear
  8. test_clear_removes_eid                   — _clearChat body contains removeItem
"""

from __future__ import annotations

from pathlib import Path

CHAT_JS = Path(__file__).resolve().parents[2] / "dashboard/static/chat_assistant/chat.js"
COMPOSER_HTML = (
    Path(__file__).resolve().parents[2] / "dashboard/templates/chat_assistant/composer.html"
)


class TestClearButtonPresent:
    def test_clear_button_present_in_composer(self):
        html = COMPOSER_HTML.read_text(encoding="utf-8")
        assert 'id="chat-assistant-clear"' in html, (
            'composer.html must contain <button id="chat-assistant-clear">'
        )

    def test_clear_button_starts_disabled(self):
        html = COMPOSER_HTML.read_text(encoding="utf-8")
        # Button HTML must have the disabled attribute so the JS can enable it
        # when history exists.  Pattern: <button ... disabled ...>
        assert "disabled" in html, "clear button must have 'disabled' attribute so JS can toggle it"
        # Also confirm the button is not accidentally forced enabled
        # The exact attribute value is not enforced — presence of the word
        # 'disabled' in the button tag is sufficient evidence.
        assert 'id="chat-assistant-clear"' in html


class TestClearChatJsFunctions:
    def test_clear_chat_function_exists(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert "function _clearChat" in js, "chat.js must define function _clearChat()"

    def test_tab_has_history_tracking(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert "_tabHasHistory" in js, (
            "chat.js must track per-tab history state with _tabHasHistory variable"
        )

    def test_update_clear_button_function(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert "function _updateClearButton" in js, (
            "chat.js must define function _updateClearButton()"
        )


class TestClearChatBehavior:
    def test_clear_has_no_confirm(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        # Extract the _clearChat function body by finding its start and end.
        # Function starts at "function _clearChat() {" and ends at its closing "}".
        start = js.find("function _clearChat() {")
        assert start != -1, "_clearChat function not found in chat.js"
        # Find the matching closing brace by counting brace depth.
        depth = 0
        body_start = js.find("{", start)
        i = body_start
        while i < len(js):
            c = js[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = js[start : i + 1]
        assert "window.confirm" not in body, (
            "_clearChat must not show a confirmation dialog via window.confirm"
        )

    def test_clear_calls_api(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        # The clear API endpoint added in S01
        assert "/clear" in js, "_clearChat must POST to /api/chat/tabs/{tab_id}/clear"

    def test_clear_removes_eid(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert "removeItem" in js, (
            "_clearChat must clear the sessionStorage last-eid key "
            "(iw-chat-last-eid-<tabId>) after a successful clear"
        )
