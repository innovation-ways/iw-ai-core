"""Reproduction + regression tests for I-00065 Bug 1 — "+ New" visible when collapsed.

Bug 1: The "+ New" button (#chat-new-btn) is visible inside the collapsed rail
because it is missing from the data-collapsed="true" CSS hide selector.

RED before fix:  '#chat-new-btn' is NOT in the hide selector → button leaks into rail.
GREEN after fix: '#chat-new-btn' IS in the hide selector → button hidden when collapsed.

These tests assert the *structure* of the template's <style> block.
They run without a browser (pure file content) and are fast.
"""

from __future__ import annotations

from pathlib import Path


def _panel_html_path() -> Path:
    """Return the path to the chat panel template."""
    return Path(__file__).parent.parent.parent / "dashboard" / "templates" / "chat" / "panel.html"


def _style_block(panel_html: str) -> str:
    """Extract the <style> block from panel.html (everything before </style>)."""
    return panel_html.split("</style>")[0]


class TestNewChatButtonHiddenWhenCollapsed:
    """I-00065 Bug 1: #chat-new-btn must be hidden when the panel is collapsed."""

    def test_i00065_new_button_hidden_when_collapsed(self):
        """#chat-panel[data-collapsed="true"] #chat-new-btn must appear in the
        collapsed-state hide rule so the '+ New' button is not visible in the rail.

        FAILS before fix: #chat-new-btn is absent from the selector list → button
        is always visible regardless of collapsed state.
        PASSES after fix: #chat-new-btn is grouped with the other collapsed-hide selectors.
        """
        panel_html = _panel_html_path().read_text()
        style_block = _style_block(panel_html)

        # The exact selector clause that hides the button when collapsed
        expected_clause = '#chat-panel[data-collapsed="true"] #chat-new-btn'
        assert expected_clause in style_block, (
            f"Expected '{expected_clause}' to be in the data-collapsed='true' hide rule "
            "so the New button is not visible in the collapsed rail. "
            "Without this, #chat-new-btn is always visible (I-00065 Bug 1)."
        )

    def test_i00065_all_expanded_header_elements_hidden_when_collapsed(self):
        """Regression guard: all six expanded-header elements that should be hidden
        when the panel is collapsed must be present in the collapsed-state selector.

        The full set: #chat-context-label, #chat-messages, #chat-scroll-to-bottom-wrap,
        #chat-composer, #chat-new-btn, #chat-collapse-btn.
        """
        panel_html = _panel_html_path().read_text()
        style_block = _style_block(panel_html)

        expected_hidden = {
            "chat-context-label",
            "chat-messages",
            "chat-scroll-to-bottom-wrap",
            "chat-composer",
            "chat-new-btn",
            "chat-collapse-btn",
        }
        missing = {id_ for id_ in expected_hidden if id_ not in style_block}
        assert not missing, (
            f"These IDs are missing from the data-collapsed='true' hide rule: {missing}. "
            "They will remain visible when the panel is collapsed (I-00065 Bug 1 regression)."
        )
