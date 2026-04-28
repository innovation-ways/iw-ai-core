"""Reproduction tests for I-00044 — Code View Chat Panel bugs (bugs 1, 2).

These tests assert the *structure* of the templates produced by S01.
They run without a browser (Jinja only) and are fast.

RED: All tests FAIL against pre-S01 templates.
GREEN: All tests PASS after S01's fixes are applied.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _template_dir() -> Path:
    return Path(__file__).parent.parent.parent / "dashboard" / "templates"


@pytest.fixture(scope="module")
def jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_template_dir())),
        autoescape=select_autoescape(enabled_extensions=()),
    )
    env.filters["intcomma"] = lambda n: f"{n:,}" if isinstance(n, int) else str(n)
    env.filters["timeago"] = lambda _dt: ""
    env.filters["fmt_ts_time"] = lambda _ts: ""
    env.filters["localdt"] = lambda _dt, _fmt="%b %d %H:%M": ""
    env.globals["url_for"] = lambda name, **kwargs: kwargs.get("path", f"/{name}")
    env.globals["is_db_stale"] = lambda _request: False
    return env


class TestBug2GridRowConstraint:
    """Bug 2: #page-body must have lg:grid-rows-[1fr] to constrain the
    grid row height and prevent <main> from scrolling away with the chat."""

    def test_page_body_has_grid_rows_1fr(self, jinja_env: Environment):
        mock_request = MagicMock()
        mock_request.url.path = "/project/iw-ai-core/code"
        tpl = jinja_env.get_template("project_code.html")
        html = tpl.render(
            current_project=type("P", (), {"id": "iw-ai-core", "display_name": "IW"})(),
            index_status=None,
            running_job=None,
            last_completed_job=None,
            last_completed_recent=False,
            content_html="<p>x</p>",
            request=mock_request,
        )
        page_body_match = re.search(r'<div[^>]+id="page-body"[^>]*>', html)
        assert page_body_match, "#page-body must be present in project_code.html"
        assert "lg:grid-rows-[1fr]" in page_body_match.group(0), (
            "#page-body must have lg:grid-rows-[1fr] to constrain the grid row "
            "height so the chat panel stays in viewport when long modules are "
            "selected (I-00044 bug 2)"
        )

    def test_page_body_grid_height_preserved(self, jinja_env: Environment):
        mock_request = MagicMock()
        mock_request.url.path = "/project/iw-ai-core/code"
        tpl = jinja_env.get_template("project_code.html")
        html = tpl.render(
            current_project=type("P", (), {"id": "iw-ai-core", "display_name": "IW"})(),
            index_status=None,
            running_job=None,
            last_completed_job=None,
            last_completed_recent=False,
            content_html="<p>x</p>",
            request=mock_request,
        )
        page_body_match = re.search(r'<div[^>]+id="page-body"[^>]*>', html)
        assert page_body_match, "#page-body must be present in project_code.html"
        tag = page_body_match.group(0)
        assert "lg:h-[calc(100vh-12rem)]" in tag, (
            "#page-body must retain lg:h-[calc(100vh-12rem)] — the height "
            "constraint that existed before the fix must not be accidentally "
            "removed (I-00044 bug 2 regression guard)"
        )
        assert "lg:grid-cols-[1fr_var(--chat-width)]" in tag, (
            "#page-body must retain lg:grid-cols-[1fr_var(--chat-width)] — "
            "the column layout must still be present (I-00044 bug 2 regression guard)"
        )


class TestBug1CollapseToggleAffordance:
    """Bug 1: the collapsed state must show a meaningful label (not just a bare chevron)."""

    def test_toggle_tab_has_chat_label(self, jinja_env: Environment):
        tpl = jinja_env.get_template("chat/panel.html")
        html = tpl.render()
        toggle_match = re.search(r'id="chat-toggle-tab"[^>]*>(.{0,500})', html, re.DOTALL)
        assert toggle_match, (
            'id="chat-toggle-tab" must be present in chat/panel.html (I-00044 bug 1)'
        )
        toggle_content = toggle_match.group(0)
        assert "Chat" in toggle_content, (
            "The toggle tab must contain a 'Chat' label visible in the collapsed "
            "state — not just a bare chevron (I-00044 bug 1)"
        )

    def test_toggle_tab_has_aria_label_with_chat(self, jinja_env: Environment):
        tpl = jinja_env.get_template("chat/panel.html")
        html = tpl.render()
        toggle_match = re.search(r'<button[^>]+id="chat-toggle-tab"[^>]*>', html)
        assert toggle_match, (
            'id="chat-toggle-tab" must be a <button> element in chat/panel.html (I-00044 bug 1)'
        )
        toggle_tag = toggle_match.group(0)
        assert "aria-label" in toggle_tag, (
            "The toggle tab must have an aria-label attribute (I-00044 bug 1)"
        )
        aria_label_match = re.search(r'aria-label="([^"]*)"', toggle_tag)
        assert aria_label_match, "aria-label must be a non-empty string"
        aria_label_value = aria_label_match.group(1)
        assert aria_label_value.strip(), "aria-label must not be empty (I-00044 bug 1)"
        assert "chat" in aria_label_value.lower() or "Chat" in aria_label_value, (
            "aria-label must mention 'chat' (case-insensitive) to be accessible (I-00044 bug 1)"
        )

    def test_collapsed_state_is_not_bare_chevron_only(self, jinja_env: Environment):
        tpl = jinja_env.get_template("chat/panel.html")
        html = tpl.render()
        toggle_match = re.search(r'<button[^>]+id="chat-toggle-tab"[^>]*>', html)
        assert toggle_match, (
            'id="chat-toggle-tab" must be present as a <button> — '
            "pre-fix code had only #chat-collapse-btn, not this toggle tab "
            "(I-00044 bug 1)"
        )
        toggle_subtree_start = toggle_match.end()
        toggle_subtree = html[toggle_subtree_start : toggle_subtree_start + 1000]
        has_icon = "<svg" in toggle_subtree
        has_chat_text = "Chat" in toggle_subtree
        assert has_icon or has_chat_text, (
            "The collapsed toggle must contain either an <svg> icon or the text "
            "'Chat' — the pre-fix bare chevron had neither (I-00044 bug 1)"
        )


class TestBug1KeyboardAccessibility:
    """Bug 1 accessibility: the toggle must be a semantic <button>."""

    def test_toggle_tab_is_a_button(self, jinja_env: Environment):
        tpl = jinja_env.get_template("chat/panel.html")
        html = tpl.render()
        toggle_match = re.search(r'<button[^>]+id="chat-toggle-tab"[^>]*>', html)
        assert toggle_match, (
            'id="chat-toggle-tab" must be a <button> element — '
            "not a <div> or <span> (I-00044 bug 1 keyboard accessibility)"
        )

    def test_mobile_elements_unchanged(self, jinja_env: Environment):
        tpl = jinja_env.get_template("chat/panel.html")
        html = tpl.render()
        assert 'id="chat-close-btn"' in html, (
            "id='chat-close-btn' must still be present for mobile drawer close "
            "(I-00044 bug 1 regression guard)"
        )
        assert 'id="chat-drawer-open"' in html, (
            "id='chat-drawer-open' must still be present for mobile drawer open "
            "(I-00044 bug 1 regression guard)"
        )
        assert 'id="chat-drawer-backdrop"' in html, (
            "id='chat-drawer-backdrop' must still be present for mobile drawer "
            "backdrop (I-00044 bug 1 regression guard)"
        )
