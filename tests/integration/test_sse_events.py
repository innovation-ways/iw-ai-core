"""Tests for SSE event type configuration."""

from __future__ import annotations

from dashboard.routers.sse import (
    _RUNNING_UPDATE_EVENTS,
    _STATUS_UPDATE_EVENTS,
    _TOAST_EVENTS,
    _TOAST_SEVERITY,
    _WATCHED_EVENTS,
)


def test_status_update_events_in_watched_set():
    """All status-update events must be in _WATCHED_EVENTS so SSE streams them."""
    missing = _STATUS_UPDATE_EVENTS - _WATCHED_EVENTS
    assert not missing, f"Status events missing from _WATCHED_EVENTS: {missing}"


def test_all_status_update_events_are_toast_events():
    """Status-update events should also trigger toast notifications."""
    missing = _STATUS_UPDATE_EVENTS - _TOAST_EVENTS
    assert not missing, f"Status events missing from _TOAST_EVENTS: {missing}"


def test_all_toast_events_have_severity():
    """Every toast event must have a severity mapping."""
    missing = _TOAST_EVENTS - set(_TOAST_SEVERITY.keys())
    assert not missing, f"Toast events without severity mapping: {missing}"


def test_running_update_events_unchanged():
    """Running-update events should include the 6 step lifecycle events."""
    assert (
        frozenset(
            {
                "step_launched",
                "step_completed",
                "step_failed",
                "step_killed",
                "step_crashed",
                "step_timeout",
            }
        )
        == _RUNNING_UPDATE_EVENTS
    )


def test_status_update_events_cover_action_emitted_types():
    """All event types emitted by dashboard actions.py should be in _STATUS_UPDATE_EVENTS."""
    action_events = {
        "item_approved",
        "item_unapproved",
        "item_cancelled",
        "item_paused",
        "item_resumed",
        "item_restarted",
        "item_full_restarted",
        "batch_created",
        "batch_approved",
        "batch_paused",
        "batch_resumed",
        "batch_cancelled",
        "step_restarted",
        "step_skipped",
    }
    missing = action_events - _STATUS_UPDATE_EVENTS
    assert not missing, f"Action-emitted events missing from _STATUS_UPDATE_EVENTS: {missing}"


def test_no_overlap_between_running_and_status_events():
    """Running-update and status-update events should not overlap."""
    overlap = _RUNNING_UPDATE_EVENTS & _STATUS_UPDATE_EVENTS
    assert not overlap, f"Unexpected overlap: {overlap}"
