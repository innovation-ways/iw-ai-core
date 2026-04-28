"""Reproduction tests for I-00033 — Code view layout bugs (bugs 1, 2, 3).

These tests assert the *structure* of the templates produced by S01.
They run without a browser (Jinja only) and are fast.

RED: All three tests FAIL against pre-S01 templates.
GREEN: All three tests PASS after S01's fixes are applied.
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
    # base.html (extended by every page template) calls `url_for(...)` for
    # static asset URLs. FastAPI normally injects this via the request, but
    # we render with a raw Jinja environment — provide a stub so templates
    # that pull in base.html don't blow up at render time.
    env.globals["url_for"] = lambda name, **kwargs: kwargs.get("path", f"/{name}")
    # base.html also calls is_db_stale(request) — registered on the real env
    # in dashboard/app.py. Stub it for layout tests where DB state is
    # irrelevant.
    env.globals["is_db_stale"] = lambda _request: False
    return env


class TestBug1LastRunBannerDismissButton:
    """Bug 1: the 'Last run' banner MUST have a dismiss button wired to the job id."""

    def test_last_run_banner_has_dismiss_button(self, jinja_env: Environment):
        tpl = jinja_env.get_template("fragments/code_job_report.html")
        html = tpl.render(
            last_completed_job=type(
                "J",
                (),
                {
                    "id": 12345,
                    "files_indexed": 10,
                    "chunks_created": 100,
                },
            )(),
            last_completed_duration="1m 23s",
            current_project=type("P", (), {"id": "iw-ai-core"})(),
        )
        assert 'data-dismiss-job-id="12345"' in html, (
            "Dismiss button must carry the specific job id (I-00033 bug 1)"
        )
        assert 'data-project-id="iw-ai-core"' in html, (
            "Dismiss button must carry the specific project id (I-00033 bug 1)"
        )
        assert 'aria-label="Dismiss last-run banner"' in html, (
            "Dismiss button must have the correct aria-label (I-00033 bug 1)"
        )
        has_banner_script = (
            "iw_code_lastrun_dismissed" in html or "/static/code/last_run_banner.js" in html
        )
        assert has_banner_script, (
            "The localStorage dismissal key must appear either inline or "
            "via a referenced <script src='/static/code/last_run_banner.js'> tag "
            "(I-00033 bug 1)"
        )


class TestBug2ScrollContainer:
    """Bug 2: scroll container moved from outer column to Architecture card."""

    def test_code_content_root_does_not_own_scroll(self, jinja_env: Environment):
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
        assert 'id="code-content-root"' in html, (
            "#code-content-root must be present in project_code.html"
        )
        root_block_match = re.search(r'<div[^>]+id="code-content-root"[^>]*>', html)
        assert root_block_match, "Could not find opening tag of #code-content-root (I-00033 bug 2)"
        root_block = root_block_match.group(0)
        assert "overflow-y-auto" not in root_block, (
            "#code-content-root must NOT have overflow-y-auto after I-00033 bug 2 — "
            "the scroll container has been moved to the Architecture card"
        )

    def test_page_body_has_gap_4(self, jinja_env: Environment):
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
        assert page_body_match, "Could not find #page-body in project_code.html"
        assert "lg:gap-4" in page_body_match.group(0), (
            "#page-body must have lg:gap-4 for the desktop gutter between text "
            "and chat (I-00033 bug 2)"
        )


class TestBug2ArchitectureCardOwnsScroll:
    """Bug 2 (companion): the Architecture card IS the scroll container."""

    def test_architecture_card_owns_scroll(self, jinja_env: Environment):
        tpl = jinja_env.get_template("fragments/code_architecture_view.html")
        html = tpl.render(content_html="<p>x</p>", project_id="iw-ai-core")

        m = re.search(r'<div\s+[^>]*class="([^"]*)"', html)
        assert m, (
            "No <div> with a class attribute found in code_architecture_view.html render "
            "(I-00033 bug 2)"
        )
        root_classes = m.group(1).split()

        assert "overflow-y-auto" in root_classes, (
            "Architecture card root must own the scroll container with overflow-y-auto "
            "(I-00033 bug 2)"
        )
        assert "h-full" in root_classes, (
            "Architecture card root must have h-full so overflow-y-auto has a definite "
            "height container — without a definite height no scrollbar appears "
            "(I-00033 bug 2)"
        )
        assert "overflow-hidden" not in root_classes, (
            "overflow-hidden must be removed from the card root — it conflicts with "
            "overflow-y-auto and prevents the scrollbar from rendering "
            "(I-00033 bug 2)"
        )
