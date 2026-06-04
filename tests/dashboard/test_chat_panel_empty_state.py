"""Reproduction + regression tests for I-00065 Bug 2 — greeting block duplicates on "+ New".

Bug 2: Clicking "+ New" appends a new "Ask about this module" greeting block instead
of replacing the existing one, because showEmptyState never removes the pre-existing
#chat-empty-state element before inserting a new one.

RED before fix:  showEmptyState removes <article>s but never removes #chat-empty-state →
                each click stacks another greeting.
GREEN after fix: showEmptyState removes any existing #chat-empty-state before inserting.

These tests read panel.js as text and assert structural properties of showEmptyState.
They run without a browser and are fast.
"""

from __future__ import annotations

import re
from pathlib import Path


def _panel_js_path() -> Path:
    """Return the path to the chat panel JavaScript."""
    return Path(__file__).parent.parent.parent / "dashboard" / "static" / "chat" / "panel.js"


def _show_empty_state_body(panel_js: str) -> str:
    """Extract the showEmptyState function body from panel.js."""
    # The function starts at "function showEmptyState()" and ends at the closing "}"
    # We locate the start, then find the matching closing brace by counting braces.
    start_marker = "function showEmptyState()"
    start = panel_js.index(start_marker)
    # Find the opening { after the function signature
    openbrace = panel_js.index("{", start)
    # Walk forward counting { and } to find the matching closebrace
    depth = 1
    pos = openbrace + 1
    while depth > 0 and pos < len(panel_js):
        if panel_js[pos] == "{":
            depth += 1
        elif panel_js[pos] == "}":
            depth -= 1
        pos += 1
    end = pos
    return panel_js[start:end]


class TestShowEmptyStateRemovesExistingBeforeInsert:
    """I-00065 Bug 2: showEmptyState must remove any pre-existing #chat-empty-state
    element before inserting a fresh one, so multiple "+ New" clicks never stack
    duplicate greeting blocks."""

    def test_i00065_show_empty_state_removes_existing_before_insert(self):
        """showEmptyState must look up any existing #chat-empty-state element and
        call .remove() on it before inserting a new one.

        FAILS before fix: showEmptyState only removes <article> bubbles; no lookup
        or removal of #chat-empty-state → each call appends another greeting.
        PASSES after fix: showEmptyState removes existing #chat-empty-state before insert.
        """
        panel_js = _panel_js_path().read_text()
        body = _show_empty_state_body(panel_js)

        # Must look up the existing element by ID
        lookup_pattern = re.compile(r"getElementById\s*\(\s*['\"]chat-empty-state['\"]\s*\)")
        assert lookup_pattern.search(body), (
            "showEmptyState must call getElementById('chat-empty-state') "
            "to look up any existing greeting element. "
            "Without this, repeated '+ New' clicks stack duplicate greetings "
            "(I-00065 Bug 2)."
        )

        # Must call .remove() on the result
        assert ".remove()" in body, (
            "showEmptyState must call .remove() on the existing greeting element "
            "to prevent duplicate blocks on repeated '+ New' clicks (I-00065 Bug 2)."
        )

        # The lookup must appear BEFORE the insertBefore call
        lookup_match = lookup_pattern.search(body)
        assert lookup_match is not None, (
            "getElementById('chat-empty-state') must appear before insertBefore "
            "so the removal happens before the new element is inserted "
            "(I-00065 Bug 2)."
        )
        lookup_offset = lookup_match.start()
        insert_offset = body.index("insertBefore")
        assert lookup_offset < insert_offset, (
            "getElementById('chat-empty-state') must appear before insertBefore "
            "so the removal happens before the new element is inserted "
            "(I-00065 Bug 2)."
        )

    def test_i00065_show_empty_state_uses_guard_pattern(self):
        """Bonus regression guard: showEmptyState must use an explicit guard to
        avoid calling .remove() on null.

        Accepted patterns:
          if (existingEmpty) existingEmpty.remove();
          if (existing) existing.remove();
          existingEmpty?.remove();

        Any of these prevents a TypeError when no prior #chat-empty-state exists.
        """
        panel_js = _panel_js_path().read_text()
        body = _show_empty_state_body(panel_js)

        # At least one of the accepted guard idioms must be present
        guard_patterns = [
            re.compile(r"if\s*\(\s*\w+\s*\)\s*\w+\.remove\(\)"),
            re.compile(r"\w+\?\.remove\(\)"),
        ]
        assert any(p.search(body) for p in guard_patterns), (
            "showEmptyState must guard the .remove() call to avoid TypeError "
            "when no prior #chat-empty-state exists. "
            "Expected one of: 'if (var) var.remove();', 'var?.remove();' "
            "(I-00065 Bug 2 guard)."
        )
