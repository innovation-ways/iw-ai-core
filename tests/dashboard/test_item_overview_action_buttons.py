"""Regression: action_button macros must render when invoked from imported macros.

The four button macros in ``components/action_button.html`` (kill_button,
restart_button, skip_button, restart_merge_button) call
``write_button_attrs(request)`` from inside their macro body. When a parent
template imports them via ``{% from ... import ... %}`` *without*
``with context``, Jinja2 isolates the macro scope and ``request`` becomes
undefined — the page renders to a 500.

This was hit on 2026-04-27 when the item-detail page tried to render an item
with a step in ``in_progress`` status (CR-00023). The fix adds ``with context``
to the four templates that import these macros.

This test renders ``fragments/item_overview.html`` for steps in each status
that triggers a button (``in_progress`` → kill, ``failed`` → restart+skip,
``MERGE`` failed → restart-merge) and asserts the render succeeds with the
button HTML present.
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

    # Mirror dashboard/middlewares/alembic_guard.is_db_stale exactly. Critical:
    # this attribute access (`request.state`) is what trips the real bug — when
    # `request` is Jinja2's Undefined (because the macro was imported without
    # `with context`), this raises UndefinedError. A lazy `lambda request: False`
    # would silently swallow Undefined and the test would falsely pass.
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
    )


def _render_item_overview(steps: list[Any]) -> str:
    tmpl = _env().get_template("fragments/item_overview.html")
    item = SimpleNamespace(id="CR-00023", project_id="iw-ai-core")
    # The real Starlette Request is irrelevant here — write_button_attrs only
    # forwards it into is_db_stale (mocked above). Any truthy object works.
    request = SimpleNamespace(state=SimpleNamespace())
    return tmpl.render(item=item, steps=steps, request=request)


class TestItemOverviewRenders:
    """Each step status that triggers a button must render without UndefinedError."""

    def test_in_progress_step_renders_kill_button(self) -> None:
        html = _render_item_overview([_make_step("S01", "in_progress")])
        assert "/project/iw-ai-core/api/confirm/kill-step/CR-00023/S01" in html
        assert "Kill" in html

    def test_failed_step_renders_restart_and_skip(self) -> None:
        html = _render_item_overview([_make_step("S01", "failed")])
        assert "/project/iw-ai-core/api/confirm/restart-step/CR-00023/S01" in html
        assert "/project/iw-ai-core/api/confirm/skip-step/CR-00023/S01" in html

    def test_needs_fix_step_renders_restart_and_skip(self) -> None:
        html = _render_item_overview([_make_step("S01", "needs_fix")])
        assert "/project/iw-ai-core/api/confirm/restart-step/CR-00023/S01" in html
        assert "/project/iw-ai-core/api/confirm/skip-step/CR-00023/S01" in html

    def test_failed_merge_renders_restart_merge_button(self) -> None:
        html = _render_item_overview([_make_step("MERGE", "failed")])
        assert "/project/iw-ai-core/api/confirm-item/restart-merge/CR-00023" in html
        assert "Retry Merge" in html

    def test_completed_step_renders_no_action_buttons(self) -> None:
        html = _render_item_overview([_make_step("S01", "completed")])
        assert "kill-step" not in html
        assert "restart-step" not in html
        assert "skip-step" not in html


class TestDbStaleDisablesButtons:
    """When is_db_stale → True, write_button_attrs must inject ``disabled``."""

    def test_kill_button_disabled_when_db_stale(self) -> None:
        env = _env()
        env.globals["is_db_stale"] = lambda _request: True
        tmpl = env.get_template("fragments/item_overview.html")
        item = SimpleNamespace(id="CR-00023", project_id="iw-ai-core")
        request = SimpleNamespace(state=SimpleNamespace())
        html = tmpl.render(
            item=item,
            steps=[_make_step("S01", "in_progress")],
            request=request,
        )
        assert "disabled" in html
        assert "make db-migrate" in html


class TestRunningPageRenders:
    """The system /running page imports the same macros — same regression risk."""

    def test_running_table_fragment_renders_with_in_progress_row(self) -> None:
        env = _env()
        tmpl = env.get_template("fragments/running_table.html")
        running_rows = [
            SimpleNamespace(
                project_id="iw-ai-core",
                project_name="iw-ai-core",
                item_id="CR-00023",
                step_id="S01",
                run_id=1,
                agent_label="agent",
                status="in_progress",
                started_at=None,
                runtime_secs=10,
            )
        ]
        request = SimpleNamespace(state=SimpleNamespace())
        # Render must not raise UndefinedError on `request` inside kill_button.
        html = tmpl.render(running_rows=running_rows, request=request)
        assert "/project/iw-ai-core/api/confirm/kill-step/CR-00023/S01" in html


class TestStepRowFragmentRenders:
    """fragments/step_row.html imports kill_button — same risk."""

    def test_step_row_renders_kill_button(self) -> None:
        env = _env()
        tmpl = env.get_template("fragments/step_row.html")
        row = SimpleNamespace(
            project_id="iw-ai-core",
            project_name="iw-ai-core",
            item_id="CR-00023",
            step_id="S01",
            run_id=1,
            agent_label="agent",
            status="in_progress",
            started_at=None,
            runtime_secs=10,
        )
        request = SimpleNamespace(state=SimpleNamespace())
        html = tmpl.render(row=row, request=request)
        assert "/project/iw-ai-core/api/confirm/kill-step/CR-00023/S01" in html


if __name__ == "__main__":  # pragma: no cover - manual debug
    pytest.main([__file__, "-v"])
