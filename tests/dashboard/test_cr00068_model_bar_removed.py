"""Reproduction + regression tests for CR-00068 — per-tab model bar removed.

CR-00068 removes the redundant per-tab model bar (#chat-assistant-tab-model-bar)
and all its supporting JavaScript from the chat assistant panel. The model picker
remains accessible via the settings panel.

These tests assert the model bar and its DOM/JS infrastructure are absent.
They run without a browser (pure file content) and are fast.
"""

from __future__ import annotations

from pathlib import Path


def _panel_html_path() -> Path:
    """Return the path to the chat panel template."""
    base = Path(__file__).parent.parent.parent
    return base / "dashboard" / "templates" / "chat_assistant" / "panel.html"


def _chat_js_path() -> Path:
    """Return the path to the chat JS file."""
    base = Path(__file__).parent.parent.parent
    return base / "dashboard" / "static" / "chat_assistant" / "chat.js"


def _style_block(panel_html: str) -> str:
    """Extract the <style> block from panel.html (everything before </style>)."""
    return panel_html.split("</style>")[0]


class TestModelBarAbsentFromTemplate:
    """panel.html must not contain the model bar element or its IDs."""

    def test_model_bar_div_absent(self):
        """id="chat-assistant-tab-model-bar" must NOT appear in panel.html.

        If this assertion fails, the per-tab model bar div was re-introduced
        and CR-00068 has been partially or fully reverted.
        """
        content = _panel_html_path().read_text()
        assert 'id="chat-assistant-tab-model-bar"' not in content, (
            'id="chat-assistant-tab-model-bar" found in panel.html. '
            "The model bar div must be removed (CR-00068)."
        )

    def test_model_dropdown_absent(self):
        """id="chat-assistant-tab-model-dropdown" must NOT appear in panel.html."""
        content = _panel_html_path().read_text()
        assert 'id="chat-assistant-tab-model-dropdown"' not in content, (
            'id="chat-assistant-tab-model-dropdown" found in panel.html. '
            "The model dropdown div must be removed (CR-00068)."
        )

    def test_model_label_absent(self):
        """id="chat-assistant-tab-model-label" must NOT appear in panel.html."""
        content = _panel_html_path().read_text()
        assert 'id="chat-assistant-tab-model-label"' not in content, (
            'id="chat-assistant-tab-model-label" found in panel.html. '
            "The model label span must be removed (CR-00068)."
        )


class TestModelBarCssRuleRemoved:
    """The collapsed-state hide rule must not reference the model bar element."""

    def test_model_bar_not_in_collapsed_hide_selector(self):
        """#chat-assistant-tab-model-bar must NOT appear in the
        data-collapsed="true" hide selector list.

        Removing the bar element means its ID must also be removed from
        the collapsed-state CSS rule. If this fails, the CSS selector list
        would still reference a non-existent element.
        """
        panel_html = _panel_html_path().read_text()
        style_block = _style_block(panel_html)

        assert "chat-assistant-tab-model-bar" not in style_block, (
            "#chat-assistant-tab-model-bar found in the <style> block of panel.html. "
            "It must be removed from the collapsed-state hide rule (CR-00068)."
        )

    def test_collapsed_hide_selector_still_valid(self):
        """The collapsed-state hide selector list must still terminate correctly.

        After removing the model-bar line, the remaining selectors must still
        form a valid CSS rule ending with '{ display: none; }'.
        """
        panel_html = _panel_html_path().read_text()
        style_block = _style_block(panel_html)

        # Extract the collapsed-state block (everything between the
        # #chat-assistant-panel[data-collapsed="true"] rule opening and its closing brace)
        collapsed_rule_start = '#chat-assistant-panel[data-collapsed="true"]'
        start_idx = style_block.find(collapsed_rule_start)
        assert start_idx != -1, "Collapsed-state CSS rule not found in panel.html style block"

        # Find the closing brace of this rule (unbalanced to avoid nested braces)
        rule_text = style_block[start_idx:]
        brace_depth = 0
        end_idx = 0
        for i, ch in enumerate(rule_text):
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    end_idx = i + 1
                    break

        collapsed_rule = rule_text[:end_idx]
        assert "{ display: none; }" in collapsed_rule, (
            'Collapsed-state hide rule is malformed — expected "{ display: none; }" '
            "at the end of the selector block. The selector list may be missing a "
            "trailing comma after removing the model-bar line (CR-00068)."
        )


class TestModelBarJsRemoved:
    """chat.js must not reference the removed model bar element IDs or functions."""

    def test_model_bar_element_ids_absent_from_js(self):
        """chat.js must not reference chat-assistant-tab-model-bar,
        chat-assistant-tab-model-dropdown, or chat-assistant-tab-model-label."""
        content = _chat_js_path().read_text()

        forbidden_ids = [
            "chat-assistant-tab-model-bar",
            "chat-assistant-tab-model-dropdown",
            "chat-assistant-tab-model-label",
        ]
        for id_ in forbidden_ids:
            assert id_ not in content, (
                f'String "{id_}" found in chat.js. '
                f"The model bar element was removed (CR-00068) — "
                f"this reference must also be removed."
            )

    def test_model_bar_functions_absent_from_js(self):
        """chat.js must not define or call the removed model-bar functions."""
        content = _chat_js_path().read_text()

        forbidden_functions = [
            "_updateTabModelBar",
            "_hideTabModelBar",
            "_populateTabModelDropdown",
            "_selectTabModel",
        ]
        for fn in forbidden_functions:
            assert fn not in content, (
                f'Function "{fn}" found in chat.js. '
                f"This function was removed as part of CR-00068 — "
                f"all calls and definitions must be removed."
            )

    def test_available_models_variable_removed(self):
        """_availableModels state variable must be absent from chat.js.

        This variable only existed to back the removed per-tab model dropdown.
        Its presence indicates dead model-bar code remains.
        """
        content = _chat_js_path().read_text()
        assert "_availableModels" not in content, (
            "_availableModels found in chat.js. "
            "This variable was only used by the removed per-tab model dropdown "
            "(CR-00068) — it must be removed."
        )


class TestTabStripModelBadgeRetained:
    """The small model badge on each tab-strip button is separate and must be kept."""

    def test_tab_strip_model_badge_class_still_present_in_js(self):
        """chat-assistant-tab-model-badge CSS class must still appear in chat.js.

        This class styles the per-tab badge on tab-strip buttons (distinct from
        the removed bar). If it is missing, the tab-strip badge was accidentally
        removed along with the bar.
        """
        content = _chat_js_path().read_text()
        assert content.count("chat-assistant-tab-model-badge") >= 1, (
            "chat-assistant-tab-model-badge class not found in chat.js. "
            "The tab-strip model badge class must be retained — "
            "only the per-tab model bar was removed (CR-00068)."
        )

    def test_tab_strip_model_badge_includes_are_intact(self):
        """Verify the tab-strip include and other includes in panel.html are intact.

        CR-00068 only removes the model bar div and its CSS selector.
        It must not disturb the tab strip, skills tray, history dropdown,
        messages area, or composer includes.
        """
        content = _panel_html_path().read_text()
        required_includes = [
            "chat_assistant/tab_strip.html",
            "chat_assistant/skills_tray.html",
            "chat_assistant/history_dropdown.html",
            "chat_assistant/composer.html",
            "chat_assistant/closed_tabs_dropdown.html",
            "chat_assistant/message.html",
        ]
        missing = [inc for inc in required_includes if inc not in content]
        assert not missing, (
            f"panel.html is missing required includes {missing!r}. "
            "CR-00068 must not disturb the panel's include structure."
        )
