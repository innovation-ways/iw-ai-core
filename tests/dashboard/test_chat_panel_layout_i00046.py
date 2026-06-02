"""Reproduction + regression tests for I-00046 — chat panel layout bugs.

Bug (a): toggle button clipped by aside overflow-hidden + duplicate id="chat-panel-slot"
Bug (c): #code-content-root missing min-h-0 causes viewport drift on module select

These tests assert the *structure* of the templates.
They run without a browser (Jinja only) and are fast.

RED: All tests FAIL against pre-fix templates.
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
    """Create a Jinja2 environment pointing at the dashboard templates directory."""
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


def _render_code_page(jinja_env: Environment) -> str:
    """Render project_code.html with minimal context for layout tests."""
    mock_request = MagicMock()
    mock_request.url.path = "/project/iw-ai-core/code"
    tpl = jinja_env.get_template("project_code.html")
    return tpl.render(
        current_project=type("P", (), {"id": "iw-ai-core", "display_name": "IW"})(),
        index_status=None,
        running_job=None,
        last_completed_job=None,
        last_completed_recent=False,
        content_html="<p>x</p>",
        request=mock_request,
    )


class TestChatPanelToggleButton:
    """I-00046 bug (a): toggle button must not be clipped by aside overflow-hidden."""

    def test_no_duplicate_chat_panel_slot_id(self, jinja_env: Environment):
        """id='chat-panel-slot' must appear exactly once in the rendered page.

        FAILS before fix: panel.html wraps content in <div id='chat-panel-slot'>,
        creating a duplicate alongside the outer <aside id='chat-panel-slot'>.
        PASSES after fix: inner wrapper's ID is removed.
        """
        html = _render_code_page(jinja_env)
        count = html.count('id="chat-panel-slot"')
        assert count == 1, (
            f"Expected exactly 1 element with id='chat-panel-slot', found {count}. "
            "Duplicate IDs break JS getElementById and constitute a DOM violation "
            "(I-00046 bug a)."
        )

    def test_aside_does_not_have_overflow_hidden(self, jinja_env: Environment):
        """The <aside id='chat-panel-slot'> must NOT have overflow-hidden.

        FAILS before fix: aside has lg:overflow-hidden which clips the toggle button
        that extends at left:-48px.
        PASSES after fix: overflow-hidden removed.
        """
        html = _render_code_page(jinja_env)
        aside_match = re.search(r'<aside[^>]+id="chat-panel-slot"[^>]*>', html)
        assert aside_match, "Could not find <aside id='chat-panel-slot'> in rendered HTML"
        aside_tag = aside_match.group(0)
        assert "overflow-hidden" not in aside_tag, (
            "<aside id='chat-panel-slot'> must not have overflow-hidden — "
            "it clips the toggle button positioned at left:-48px (I-00046 bug a)"
        )

    def test_aside_has_min_h_0(self, jinja_env: Environment):
        """The <aside id='chat-panel-slot'> must have lg:min-h-0.

        FAILS before fix: aside lacks min-h-0.
        PASSES after fix.
        """
        html = _render_code_page(jinja_env)
        aside_match = re.search(r'<aside[^>]+id="chat-panel-slot"[^>]*>', html)
        assert aside_match, "Could not find <aside id='chat-panel-slot'> in rendered HTML"
        aside_tag = aside_match.group(0)
        assert "min-h-0" in aside_tag, (
            "<aside id='chat-panel-slot'> must have min-h-0 so the chat column "
            "respects its CSS grid row size (I-00046 bug a/c)"
        )

    def test_collapse_and_expand_controls_present(self, jinja_env: Environment):
        """The chat panel's collapse/expand controls must exist in the rendered page.

        Regression guard: ensure the toggle controls were not accidentally
        removed while fixing the duplicate ID issue. I-00057 superseded the
        original I-00046 floating slide-out toggle (#chat-toggle-tab at
        left:-48px) with a pair of in-panel affordances — #chat-collapse-btn
        in the expanded header and #chat-expand-rail in the collapsed slim rail.
        The original I-00046 *intent* — that the panel always exposes a primary
        collapse/expand control — is enforced below against the I-00057 markup.
        """
        html = _render_code_page(jinja_env)
        assert 'id="chat-collapse-btn"' in html, (
            "#chat-collapse-btn must be present in the rendered page — "
            "the primary collapse control (I-00046 regression guard, I-00057 markup)"
        )
        assert 'id="chat-expand-rail"' in html, (
            "#chat-expand-rail must be present in the rendered page — "
            "the primary expand control (I-00046 regression guard, I-00057 markup)"
        )
        # The pre-I-00057 floating toggle pattern must not return — its absolute
        # `left: -48px` position is what caused the original clipping bug.
        floating_msg = (
            "Floating toggle button with style='left: -48px;' must not be present "
            "(I-00057 superseded this pattern; it caused the I-00046 clipping bug)"
        )
        assert "left: -48px" not in html, floating_msg
        assert "left:-48px" not in html, floating_msg


class TestCodeContentRootContainment:
    """I-00046 bug (c): #code-content-root must contain the CSS grid row."""

    def test_code_content_root_has_min_h_0(self, jinja_env: Environment):
        """#code-content-root must have lg:min-h-0.

        FAILS before fix: no class attribute on #code-content-root, so it lacks
        min-h-0 and can grow the 1fr grid row beyond the viewport.
        PASSES after fix.
        """
        html = _render_code_page(jinja_env)
        root_match = re.search(r'<div[^>]+id="code-content-root"[^>]*>', html)
        assert root_match, "Could not find #code-content-root in rendered HTML"
        root_tag = root_match.group(0)
        assert "min-h-0" in root_tag, (
            "#code-content-root must have min-h-0 so the CSS grid 1fr row is not "
            "expanded by module detail content beyond the viewport (I-00046 bug c)"
        )
