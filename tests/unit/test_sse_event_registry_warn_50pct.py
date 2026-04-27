"""CR-00024 AC7: dashboard SSE pipeline registers step_warning_50pct.

Pure-Python registry assertions — no fixtures needed.
"""

from __future__ import annotations

from dashboard.routers import sse


def test_step_warning_50pct_is_a_toast_event() -> None:
    """AC7: the SSE pump considers step_warning_50pct a watched toast event."""
    assert "step_warning_50pct" in sse._TOAST_EVENTS


def test_step_warning_50pct_severity_is_info() -> None:
    """AC7: severity maps to info (not warning/error)."""
    assert sse._TOAST_SEVERITY["step_warning_50pct"] == "info"


def test_step_warning_50pct_refreshes_running_table() -> None:
    """The 50%-warn refreshes the running-table fragment for live operator visibility."""
    assert "step_warning_50pct" in sse._RUNNING_UPDATE_EVENTS


def test_existing_step_event_severities_unchanged() -> None:
    """AC7 defensive: pre-CR-00024 event types keep their severity mapping."""
    assert sse._TOAST_SEVERITY["step_crashed"] == "error"
    assert sse._TOAST_SEVERITY["step_timeout"] == "warning"
    assert sse._TOAST_SEVERITY["step_stalled"] == "warning"


def test_step_warning_50pct_in_watched_events_union() -> None:
    """The watched-events filter (used by the SSE pump query) includes the new type."""
    assert "step_warning_50pct" in sse._WATCHED_EVENTS
