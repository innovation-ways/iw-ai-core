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


def _css_rule_body(css: str, selector: str) -> str | None:
    """Return the declaration block of the CSS rule for ``selector``.

    Matches the first occurrence of ``selector`` followed only by whitespace
    then ``{``, and returns the text between that ``{`` and its ``}``. Returns
    None when no such rule exists. Stronger than a bare substring test: it
    confirms ``selector`` actually heads a rule rather than appearing inside a
    comment or as a prefix of a longer selector.
    """
    pos = 0
    while True:
        idx = css.find(selector, pos)
        if idx == -1:
            return None
        brace = css.find("{", idx + len(selector))
        if brace != -1 and css[idx + len(selector) : brace].strip() == "":
            end = css.find("}", brace)
            if end != -1:
                return css[brace + 1 : end]
        pos = idx + len(selector)


class TestComposerDom:
    """The <span id="chat-assistant-context-pct"> element must exist, start hidden,
    and sit before #chat-assistant-clear in DOM order."""

    def test_context_pct_element_exists(self):
        soup = BeautifulSoup(COMPOSER_HTML.read_text(encoding="utf-8"), "html.parser")
        el = soup.find(id="chat-assistant-context-pct")
        assert el is not None, "composer.html must contain #chat-assistant-context-pct"
        assert el.name == "span", f"#chat-assistant-context-pct must be a <span>, got <{el.name}>"

    def test_context_pct_starts_hidden(self):
        soup = BeautifulSoup(COMPOSER_HTML.read_text(encoding="utf-8"), "html.parser")
        el = soup.find(id="chat-assistant-context-pct")
        assert el is not None, "chat-assistant-context-pct element not found"
        assert "hidden" in el.get("class", []), (
            "chat-assistant-context-pct must start with the 'hidden' class "
            "(no data until first fetch resolves)"
        )
        # It carries no static text — the percentage is filled in by JS once
        # the first context-usage fetch resolves.
        assert el.get_text(strip=True) == "", (
            "chat-assistant-context-pct must start empty; its text is JS-populated"
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
        body = _css_rule_body(CHAT_CSS.read_text(encoding="utf-8"), ".chat-assistant-context-pct")
        assert body is not None, "chat.css must define a .chat-assistant-context-pct base rule"
        assert body.strip() != "", (
            "the .chat-assistant-context-pct base rule must declare styles, not be empty"
        )

    def test_warn_class_exists(self):
        body = _css_rule_body(
            CHAT_CSS.read_text(encoding="utf-8"), ".chat-assistant-context-pct.is-warn"
        )
        assert body is not None, (
            "chat.css must define a .chat-assistant-context-pct.is-warn rule "
            "for the 70-89% amber/warning band"
        )
        assert body.count("color") >= 1, (
            "the .is-warn rule must set a colour for the amber/warning band"
        )

    def test_crit_class_exists(self):
        body = _css_rule_body(
            CHAT_CSS.read_text(encoding="utf-8"), ".chat-assistant-context-pct.is-crit"
        )
        assert body is not None, (
            "chat.css must define a .chat-assistant-context-pct.is-crit rule "
            "for the >=90% destructive band"
        )
        assert body.count("color") >= 1, (
            "the .is-crit rule must set a colour for the >=90% destructive band"
        )


class TestContextPctJsHelpers:
    """_applyContextPct, _refreshContextPct, and the immediate-fetch in
    _activateTab must all be present."""

    def test_apply_context_pct_exists(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert js.count("function _applyContextPct") == 1, (
            "chat.js must define function _applyContextPct(pct) exactly once"
        )

    def test_refresh_context_pct_exists(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert js.count("function _refreshContextPct") == 1, (
            "chat.js must define function _refreshContextPct(tabId) exactly once"
        )

    def test_refresh_context_pct_hides_on_falsy_tab_id(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert "_applyContextPct(NaN)" in js or "NaN" in js, (
            "_refreshContextPct(null / falsy) must call _applyContextPct(NaN) to hide the element"
        )

    def test_activate_tab_calls_refresh_context_pct(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert js.count("function _refreshContextPct") == 1, (
            "_refreshContextPct must be defined exactly once"
        )
        assert "_refreshContextPct(tabId)" in js, (
            "_activateTab must call _refreshContextPct(tabId) for immediate display"
        )

    def test_poll_calls_refresh_context_pct(self):
        js = CHAT_JS.read_text(encoding="utf-8")
        assert "setInterval" in js, "chat.js must use setInterval for polling"
        # Called from >=2 sites — the immediate _activateTab display and the
        # poll — confirming the poll reuses the helper, not a duplicated fetch.
        assert js.count("_refreshContextPct(") >= 2, (
            "the poll must call _refreshContextPct instead of duplicating the fetch"
        )
