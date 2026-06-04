"""Tests for CR-00036: Merge button renders when MERGE step is in awaiting_approval.

The item overview fragment must render an `approve_merge_button` (labeled "Merge")
when the MERGE step has status `awaiting_approval`, and must NOT render
`restart_merge_button` or `abandon_merge_button` in that case.
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


def _make_step(
    step_id: str,
    status: str,
    *,
    is_synthetic: bool = False,
    agent_label: str = "agent",
) -> SimpleNamespace:
    return SimpleNamespace(
        step_id=step_id,
        status=status,
        agent_label=agent_label,
        step_label=None,
        description=None,
        started_at=None,
        duration_secs=None,
        run_count=1,
        fix_cycle_count=0,
        error_message=None,
        is_synthetic=is_synthetic,
        # CR-00066: context window usage tracking
        context_tokens_peak=None,
        context_tokens_last=None,
        context_window_tokens=None,
        # CR-00056 S11: has_prompt for prompt column rendering
        has_prompt=False,
    )


def _render_item_overview(steps: list[Any]) -> str:
    tmpl = _env().get_template("fragments/item_overview.html")
    item = SimpleNamespace(id="CR-00036", project_id="iw-ai-core")
    request = SimpleNamespace(state=SimpleNamespace())
    return tmpl.render(item=item, steps=steps, request=request)


class TestAwaitingApprovalMergeButton:
    """CR-00036 AC5: MERGE step in awaiting_approval shows the Merge button."""

    def test_awaiting_approval_renders_merge_button(self) -> None:
        """MERGE step with status awaiting_approval renders the Merge button."""
        html = _render_item_overview([_make_step("MERGE", "awaiting_approval")])
        # The approve_merge_button POSTs to approve-merge
        assert "/project/iw-ai-core/api/item/CR-00036/approve-merge" in html
        # Button label is the visible word "Merge"
        assert "\n    Merge\n" in html

    def test_awaiting_approval_does_not_render_restart_merge(self) -> None:
        """MERGE step with awaiting_approval must NOT show Restart Merge."""
        html = _render_item_overview([_make_step("MERGE", "awaiting_approval")])
        assert "restart-merge" not in html
        assert "Retry Merge" not in html

    def test_awaiting_approval_does_not_render_abandon_merge(self) -> None:
        """MERGE step with awaiting_approval must NOT show Abandon Merge."""
        html = _render_item_overview([_make_step("MERGE", "awaiting_approval")])
        assert "abandon-merge" not in html
        assert "Abandon" not in html

    def test_failed_merge_still_shows_restart_and_abandon(self) -> None:
        """MERGE step with status failed/merge_failed shows Restart + Abandon."""
        html = _render_item_overview([_make_step("MERGE", "failed")])
        assert "restart-merge" in html
        assert "Retry Merge" in html

    def test_merge_failed_shows_restart_and_abandon(self) -> None:
        """MERGE step with status merge_failed shows both Restart and Abandon."""
        html = _render_item_overview([_make_step("MERGE", "merge_failed")])
        assert "restart-merge" in html
        assert "Retry Merge" in html
        assert "abandon-merge" in html
        assert "Abandon" in html

    def test_completed_merge_renders_no_action_buttons(self) -> None:
        """MERGE step with status completed (auto-merge on) renders no action buttons."""
        html = _render_item_overview([_make_step("MERGE", "completed")])
        assert "restart-merge" not in html
        assert "abandon-merge" not in html
        assert "approve-merge" not in html


if __name__ == "__main__":  # pragma: no cover - manual debug
    pytest.main([__file__, "-v"])
