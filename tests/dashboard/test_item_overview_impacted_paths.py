"""Tests for F-00076: Impacted Paths panel in item overview fragment.

Verifies that the collapsible "Impacted Paths" section renders correctly
with various scope_extraction sources and empty-state handling.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _template_dir() -> str:
    return str((Path(__file__).parent.parent.parent / "dashboard" / "templates").resolve())


def _env() -> Environment:
    """Mirror the dashboard's Jinja env (filters/globals used by templates)."""
    env = Environment(
        loader=FileSystemLoader(_template_dir()),
        autoescape=select_autoescape(enabled_extensions=("html",)),
    )
    env.filters["localdt"] = lambda _dt, _fmt="%b %d %H:%M": ""
    env.filters["timeago"] = lambda _dt: ""
    env.filters["fmt_ts_time"] = lambda _dt: ""
    env.filters["intcomma"] = lambda n: f"{n:,}" if isinstance(n, int) else str(n)

    def _is_db_stale(request: Any) -> bool:
        status = getattr(request.state, "alembic_guard_status", None)
        if status is None:
            return False
        return not status.ok

    env.globals["is_db_stale"] = _is_db_stale
    return env


def _make_item(
    item_id: str = "F-00076",
    impacted_paths: list[str] | None = None,
    scope_source: str | None = None,
) -> SimpleNamespace:
    """Build a minimal work item object as passed to item_overview.html."""
    config = {}
    if scope_source is not None:
        config["scope_extraction"] = {"source": scope_source}
    return SimpleNamespace(
        id=item_id,
        project_id="iw-ai-core",
        impacted_paths=impacted_paths or [],
        config=config,
    )


def _render_overview(item: SimpleNamespace, steps: list[Any] | None = None) -> str:
    """Render item_overview.html with the given item and steps."""
    tmpl = _env().get_template("fragments/item_overview.html")
    request = SimpleNamespace(state=SimpleNamespace())
    return tmpl.render(
        item=item,
        steps=steps or [],
        request=request,
        current_project=SimpleNamespace(id="iw-ai-core", display_name="Test Project"),
    )


# ---------------------------------------------------------------------------
# Impacted Paths panel renders
# ---------------------------------------------------------------------------


class TestImpactedPathsPanelRenders:
    """Impacted Paths panel is present and shows correct badge for each source."""

    def test_declared_source_shows_green_badge(self) -> None:
        """scope_extraction.source == 'declared' → green 'declared' badge."""
        item = _make_item(
            impacted_paths=["orch/daemon/**", "orch/batch_planner.py"],
            scope_source="declared",
        )
        html = _render_overview(item)
        assert "Impacted Paths" in html
        assert "declared" in html
        assert "bg-success" in html
        assert "orch/daemon/**" in html
        assert "orch/batch_planner.py" in html

    def test_regex_fallback_shows_amber_auto_badge(self) -> None:
        """scope_extraction.source == 'regex_fallback' → amber 'auto' badge."""
        item = _make_item(
            impacted_paths=["dashboard/**/*.py"],
            scope_source="regex_fallback",
        )
        html = _render_overview(item)
        assert "Impacted Paths" in html
        assert "auto" in html
        assert "bg-warning" in html

    def test_none_source_shows_grey_badge(self) -> None:
        """scope_extraction.source absent and empty paths → grey 'none' badge."""
        item = _make_item(impacted_paths=[], scope_source=None)
        item.config = {}  # no scope_extraction at all
        html = _render_overview(item)
        assert "Impacted Paths" in html
        # grey "none" badge
        assert "none" in html
        assert "No paths declared" in html

    def test_empty_paths_shows_empty_state_message(self) -> None:
        """impacted_paths == [] → empty-state message shown."""
        item = _make_item(impacted_paths=[], scope_source="declared")
        html = _render_overview(item)
        assert "No paths declared" in html
        assert "bypass" in html.lower()

    def test_monospace_code_chips_for_globs(self) -> None:
        """Each glob is rendered as a monospace <code> chip."""
        item = _make_item(
            impacted_paths=["*.py", "tests/**/*.py", "docs/**/*.md"],
            scope_source="declared",
        )
        html = _render_overview(item)
        assert "<code" in html
        assert "*.py" in html
        assert "tests/**/*.py" in html

    def test_collapsed_when_six_or_more_globs(self) -> None:
        """Default open=false when impacted_paths has >= 6 entries."""
        item = _make_item(
            impacted_paths=["a.py", "b.py", "c.py", "d.py", "e.py", "f.py"],
            scope_source="declared",
        )
        html = _render_overview(item)
        # The <details> tag should NOT have an `open` attribute
        assert "<details" in html
        assert "open" not in html.split("Impacted Paths")[1].split(">")[0]

    def test_expanded_when_fewer_than_six_globs(self) -> None:
        """Default open=true when impacted_paths has < 6 entries."""
        item = _make_item(
            impacted_paths=["one.py", "two.py"],
            scope_source="declared",
        )
        html = _render_overview(item)
        assert "open" in html

    def test_no_duplicate_globs(self) -> None:
        """Duplicate globs in the list are each rendered as a separate chip."""
        item = _make_item(
            impacted_paths=["a.py", "a.py", "b.py"],
            scope_source="declared",
        )
        html = _render_overview(item)
        # Three chips for three entries (even duplicates)
        assert html.count("<code") == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
