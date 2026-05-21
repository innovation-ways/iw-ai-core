"""CR-00067 S04: template-render tests for the context % indicator.

Verifies the composer template ships the required DOM element with the right
defaults; the colour-band CSS rules; and the JS helper functions exist.
"""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

CHAT_CSS = Path(__file__).resolve().parents[2] / "dashboard/static/chat_assistant/chat.css"
COMPOSER_HTML = (
    Path(__file__).resolve().parents[2] / "dashboard/templates/chat_assistant/composer.html"
)
CHAT_JS = Path(__file__).resolve().parents[2] / "dashboard/static/chat_assistant/chat.js"


class TestComposerDom:
    """The <span id="chat-assistant-context-pct"> element must exist, start hidden,
    and sit before #chat-assistant-clear in DOM order."""

    def test_context_pct_element_exists(self):
        html = COMPOSER_HTML.read_text(encoding="utf-8")
        assert 'id="chat-assistant-context-pct"' in html, (
            "composer.html must contain <span id='chat-assistant-context-pct'>"
        )

    def test_context_pct_starts_hidden(self):
        html = COMPOSER_HTML.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        el = soup.find(id="chat-assistant-context-pct")
        assert el is not None, "chat-assistant-context-pct element not found"
        assert "hidden" in el.get("class", []), (
            "chat-assistant-context-pct must start with the 'hidden' class "
            "(no data until first fetch resolves)"
        )

    def test_context_pct_before_clear_button(self):
        """Both elements must be siblings in the same flex row; context_pct must
        appear before clear in DOM order."""
        html = COMPOSER_HTML.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        context_el = soup.find(id="chat-assistant-context-pct")
        clear_el = soup.find(id="chat-assistant-clear")
        assert context_el is not None, "chat-assistant-context-pct not found"
        assert clear_el is not None, "#chat-assistant-clear not found"
        # Find common parent and use its children (which both elements belong to)
        parent = context_el.parent
        assert parent is clear_el.parent, (
            "context_pct and clear must share the same direct parent container"
        )
        siblings = list(parent.children)
        assert context_el in siblings, "context_pct not a direct child of its parent"
        assert clear_el in siblings, "clear not a direct child of its parent"
        assert siblings.index(context_el) < siblings.index(clear_el), (
            "chat-assistant-context-pct must appear before #chat-assistant-clear "
            "in DOM order (left of Clear in the flex row)"
        )


class TestContextPctCss:
    """Colour-band rules in chat.css."""

    def test_base_rule_exists(self):
        css = CHAT_CSS.read_text(encoding="utf-8")
        assert ".chat-assistant-context-pct" in css, (
            "chat.css must define a .chat-assistant-context-pct base rule"
        )

    def test_warn_class_exists(self):
        css = CHAT_CSS.read_text(encoding="utf-8")
        assert ".chat-assistant-context-pct.is-warn" in css, (
            "chat.css must define a .chat-assistant-context-pct.is-warn rule "
            "for the 70-89% amber/warning band"
        )

    def test_crit_class_exists(self):
        css = CHAT_CSS.read_text(encoding="utf-8")
        assert ".chat-assistant-context-pct.is-crit" in css, (
            "chat.css must define a .chat-assistant-context-pct.is-crit rule "
            "for the >=90% destructive band"
        )


class TestContextPctJsHelpers:
    """_applyContextPct, _refreshContextPct, and the immediate-fetch in
    _activateTab must all be present."""

    def test_apply_context_pct_exists(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert "function _applyContextPct" in js, (
            "chat.js must define function _applyContextPct(pct)"
        )

    def test_refresh_context_pct_exists(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert "function _refreshContextPct" in js, (
            "chat.js must define function _refreshContextPct(tabId)"
        )

    def test_refresh_context_pct_hides_on_falsy_tab_id(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert "_applyContextPct(NaN)" in js or "NaN" in js, (
            "_refreshContextPct(null / falsy) must call _applyContextPct(NaN) to hide the element"
        )

    def test_activate_tab_calls_refresh_context_pct(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert "_refreshContextPct(tabId)" in js, (
            "_activateTab must call _refreshContextPct(tabId) for immediate display"
        )

    def test_poll_calls_refresh_context_pct(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert "setInterval" in js, "chat.js must use setInterval for polling"
        assert "_refreshContextPct" in js, (
            "Poll (setInterval) must call _refreshContextPct instead of duplicating fetch"
        )
