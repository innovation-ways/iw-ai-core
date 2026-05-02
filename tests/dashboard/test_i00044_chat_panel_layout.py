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
    """Bug 1: the collapsed state must show a meaningful label, not a bare chevron.

    I-00057 superseded the original I-00044 fix: the floating slide-out tab
    (#chat-toggle-tab) was replaced by a pair of in-panel affordances —
    #chat-collapse-btn (header button shown when expanded) and #chat-expand-rail
    (slim rail shown when collapsed). The original I-00044 *intent* — a labelled,
    non-bare-chevron collapse/expand affordance with a "Chat" cue — is still
    enforced below against the I-00057 successor markup.
    """

    def test_collapsed_rail_has_chat_label(self, jinja_env: Environment):
        tpl = jinja_env.get_template("chat/panel.html")
        html = tpl.render()
        rail_match = re.search(r'id="chat-expand-rail"[^>]*>(.{0,600})', html, re.DOTALL)
        assert rail_match, (
            'id="chat-expand-rail" must be present in chat/panel.html — '
            "the collapsed-state affordance that replaced the I-00044 toggle tab "
            "(I-00057 successor to I-00044 bug 1)"
        )
        rail_content = rail_match.group(0)
        assert "Chat" in rail_content, (
            "The collapsed rail must contain a 'Chat' label — not just a bare "
            "chevron (I-00044 bug 1 intent, enforced via I-00057 markup)"
        )

    def test_expand_and_collapse_controls_have_aria_labels_with_chat(self, jinja_env: Environment):
        tpl = jinja_env.get_template("chat/panel.html")
        html = tpl.render()
        for selector, kind in (
            (r'<[a-z]+[^>]+id="chat-expand-rail"[^>]*>', "expand rail"),
            (r'<button[^>]+id="chat-collapse-btn"[^>]*>', "collapse button"),
        ):
            match = re.search(selector, html)
            assert match, f"{kind} must be present (I-00057 successor to I-00044 bug 1)"
            tag = match.group(0)
            aria_label_match = re.search(r'aria-label="([^"]*)"', tag)
            assert aria_label_match, f"{kind} must have an aria-label attribute"
            assert aria_label_match.group(1).strip(), f"{kind} aria-label must not be empty"
            assert "chat" in aria_label_match.group(1).lower(), (
                f"{kind} aria-label must mention 'chat' (case-insensitive) (I-00044 bug 1 intent)"
            )

    def test_collapsed_state_is_not_bare_chevron_only(self, jinja_env: Environment):
        tpl = jinja_env.get_template("chat/panel.html")
        html = tpl.render()
        rail_match = re.search(r'id="chat-expand-rail"[^>]*>', html)
        assert rail_match, (
            'id="chat-expand-rail" must be present — the I-00057 successor '
            "to the I-00044 toggle tab"
        )
        rail_subtree_start = rail_match.end()
        rail_subtree = html[rail_subtree_start : rail_subtree_start + 1000]
        has_icon = "<svg" in rail_subtree
        has_chat_text = "Chat" in rail_subtree
        assert has_icon or has_chat_text, (
            "The collapsed rail must contain either an <svg> icon or the text "
            "'Chat' — the pre-fix bare chevron had neither (I-00044 bug 1)"
        )


class TestBug1KeyboardAccessibility:
    """Bug 1 accessibility: the collapse control must be a semantic <button>.

    I-00057 successor: the active toggle in the expanded state is
    #chat-collapse-btn (a <button>). The collapsed-state #chat-expand-rail is
    a div with role="button" so it is keyboard-reachable as well.
    """

    def test_collapse_button_is_a_button_element(self, jinja_env: Environment):
        tpl = jinja_env.get_template("chat/panel.html")
        html = tpl.render()
        match = re.search(r'<button[^>]+id="chat-collapse-btn"[^>]*>', html)
        assert match, (
            'id="chat-collapse-btn" must be a <button> element — not a <div> '
            "or <span> (I-00044 bug 1 keyboard accessibility, I-00057 markup)"
        )

    def test_expand_rail_is_keyboard_role_button(self, jinja_env: Environment):
        tpl = jinja_env.get_template("chat/panel.html")
        html = tpl.render()
        rail_match = re.search(r'<[a-z]+[^>]+id="chat-expand-rail"[^>]*>', html)
        assert rail_match, "id='chat-expand-rail' must be present"
        rail_tag = rail_match.group(0)
        assert 'role="button"' in rail_tag, (
            "Collapsed rail must declare role='button' so keyboard users can "
            "expand the panel (I-00044 bug 1 keyboard accessibility)"
        )

    def test_mobile_drawer_elements_unchanged(self, jinja_env: Environment):
        tpl = jinja_env.get_template("chat/panel.html")
        html = tpl.render()
        # I-00057 removed #chat-close-btn; collapse is now handled by
        # #chat-collapse-btn in both desktop and drawer modes.
        assert 'id="chat-drawer-open"' in html, (
            "id='chat-drawer-open' must still be present for mobile drawer open "
            "(I-00044 bug 1 regression guard)"
        )
        assert 'id="chat-drawer-backdrop"' in html, (
            "id='chat-drawer-backdrop' must still be present for mobile drawer "
            "backdrop (I-00044 bug 1 regression guard)"
        )
