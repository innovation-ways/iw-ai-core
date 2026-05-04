"""Template smoke test: chat panel renders the New chat button."""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _template_dir() -> str:
    return str(Path(__file__).parent.parent.parent / "dashboard" / "templates")


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=select_autoescape(enabled_extensions=()),
    )


class TestNewChatButton:
    """TDD: assert the New chat button exists in the rendered panel template."""

    def test_new_chat_button_present(self):
        """AC4 — panel.html must include <button id="chat-new-btn">."""
        tmpl = _env().get_template("chat/panel.html")
        html = tmpl.render()
        assert 'id="chat-new-btn"' in html

    def test_new_chat_button_has_correct_aria_label(self):
        """The button must have an accessible aria-label."""
        tmpl = _env().get_template("chat/panel.html")
        html = tmpl.render()
        assert 'aria-label="Start a new chat' in html

    def test_new_chat_button_is_tap_sized(self):
        """The button must use the .tap utility class (min 44px touch target)."""
        tmpl = _env().get_template("chat/panel.html")
        html = tmpl.render()
        assert 'class="tap' in html
        assert "chat-new-btn" in html

    def test_new_chat_button_uses_existing_utility_classes(self):
        """Button must use only existing Tailwind utility classes (no new ones)."""
        tmpl = _env().get_template("chat/panel.html")
        html = tmpl.render()
        btn_match = re.search(r'<button id="chat-new-btn"([^>]*)>', html)
        assert btn_match is not None
        classes = btn_match.group(1)
        # Must contain these expected utilities
        assert "inline-flex" in classes
        assert "items-center" in classes
        assert "justify-center" in classes
        assert "text-xs" in classes
        assert "px-2" in classes
        assert "py-1" in classes
        assert "rounded" in classes
        assert "border" in classes
        assert "border-border" in classes
        assert "hover:bg-muted" in classes
