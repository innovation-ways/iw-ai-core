"""Template smoke tests for F-00055 chat UI — work-item chips, feed, phase strip."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _template_dir() -> str:
    return str((Path(__file__).parent.parent.parent / "dashboard" / "templates").resolve())


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=select_autoescape(enabled_extensions=()),
    )


class TestWorkItemChipTemplate:
    """AC10 — work_item_chip.html renders with correct data-* attributes and type glyphs."""

    @pytest.fixture
    def tmpl(self):
        return _env().get_template("chat/parts/work_item_chip.html")

    def test_feature_chip_has_f_glyph(self, tmpl):
        html = tmpl.render(n=1, work_item_id="F-00042", work_item_type="feature")
        assert "citation-chip--workitem" in html
        assert "citation-chip--feature" in html
        assert 'data-workitem-id="F-00042"' in html
        assert 'data-workitem-type="feature"' in html
        assert ">F-00042<" in html
        assert ">F<" in html

    def test_change_request_chip_has_cr_glyph(self, tmpl):
        html = tmpl.render(n=2, work_item_id="CR-00010", work_item_type="change_request")
        assert "citation-chip--change_request" in html
        assert 'data-workitem-id="CR-00010"' in html
        assert ">CR<" in html

    def test_incident_chip_has_i_glyph(self, tmpl):
        html = tmpl.render(n=3, work_item_id="I-00099", work_item_type="incident")
        assert "citation-chip--incident" in html
        assert 'data-workitem-id="I-00099"' in html
        assert ">I<" in html

    def test_has_aria_haspopup_dialog(self, tmpl):
        html = tmpl.render(n=1, work_item_id="F-00042", work_item_type="feature")
        assert 'aria-haspopup="dialog"' in html

    def test_has_aria_label_work_item_id(self, tmpl):
        html = tmpl.render(n=1, work_item_id="F-00042", work_item_type="feature")
        assert 'aria-label="Work item F-00042"' in html

    def test_has_data_cite(self, tmpl):
        html = tmpl.render(n=1, work_item_id="F-00042", work_item_type="feature")
        assert 'data-cite="1"' in html


class TestWorkItemFeedTemplate:
    """F-00055 AC1 — work_item_feed.html renders Linear-style feed."""

    @pytest.fixture
    def tmpl(self):
        return _env().get_template("chat/parts/work_item_feed.html")

    def test_renders_header(self, tmpl):
        html = tmpl.render(
            items=[],
            project_id="test-project",
            count=0,
            retrieval_cutoff=None,
            confidence=None,
        )
        assert "History" in html
        assert "work-item-feed" in html

    def test_renders_single_item(self, tmpl):
        html = tmpl.render(
            items=[
                {
                    "id": "F-00042",
                    "created_at": "2026-04-15",
                    "title": "Add retry logic",
                    "summary": "The daemon now retries 3 times on failure.",
                }
            ],
            project_id="test-project",
            count=1,
            retrieval_cutoff=None,
            confidence=None,
        )
        assert "F-00042" in html
        assert "Add retry logic" in html
        assert "2026-04-15" in html

    def test_renders_multiple_items(self, tmpl):
        html = tmpl.render(
            items=[
                {
                    "id": "F-00001",
                    "created_at": "2026-01-01",
                    "title": "First",
                    "summary": "First item.",
                },
                {
                    "id": "F-00002",
                    "created_at": "2026-02-01",
                    "title": "Second",
                    "summary": "Second item.",
                },
            ],
            project_id="test-project",
            count=2,
            retrieval_cutoff=None,
            confidence=None,
        )
        assert html.count("work-item-feed-item") == 2

    def test_no_summary_shows_placeholder(self, tmpl):
        html = tmpl.render(
            items=[
                {
                    "id": "F-00099",
                    "created_at": "2026-04-01",
                    "title": "No summary",
                    "summary": None,
                }
            ],
            project_id="test-project",
            count=1,
            retrieval_cutoff=None,
            confidence=None,
        )
        assert "(no summary available)" in html

    def test_work_item_id_link(self, tmpl):
        html = tmpl.render(
            items=[{"id": "F-00042", "created_at": "2026-04-01", "title": "T", "summary": "S"}],
            project_id="my-project",
            count=1,
            retrieval_cutoff=None,
            confidence=None,
        )
        assert "/project/my-project/item/F-00042" in html

    def test_trust_strip_with_count_and_cutoff(self, tmpl):
        html = tmpl.render(
            items=[],
            project_id="test-project",
            count=5,
            retrieval_cutoff="2026-04-15",
            confidence="high",
        )
        assert "Based on 5 work items" in html
        assert "2026-04-15" in html
        assert "high" in html


class TestPhaseStripTemplate:
    """AC6 — phase_strip.html renders with role=status."""

    @pytest.fixture
    def tmpl(self):
        return _env().get_template("chat/parts/phase_strip.html")

    def test_has_role_status(self, tmpl):
        html = tmpl.render()
        assert 'role="status"' in html

    def test_has_aria_live_polite(self, tmpl):
        html = tmpl.render()
        assert 'aria-live="polite"' in html

    def test_has_phase_strip_class(self, tmpl):
        html = tmpl.render()
        assert 'class="phase-strip"' in html
