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


# ---------------------------------------------------------------------------
# _event_generator exception surfacing — regression guard for the "silent SSE"
# class of failure. Without the catch-all, an exception in the poll loop
# bubbles out and Starlette closes the stream with no payload, leaving
# browser_verification agents blind to the root cause (this was the failure
# mode that hid the F-00060 Q&A pipeline defect for four fix cycles).
# ---------------------------------------------------------------------------


def test_event_generator_surfaces_init_failures_as_error_frame(monkeypatch):
    """If the initial _get_latest_event_id() raises, the client must see
    ``event: error`` with type+message before the stream closes — not a
    silent disconnect."""
    import asyncio
    import json
    from unittest.mock import MagicMock

    from dashboard.routers import sse as sse_module

    def _boom() -> int:
        raise RuntimeError("simulated DB outage")

    monkeypatch.setattr(sse_module, "_get_latest_event_id", _boom)

    request = MagicMock()
    request.is_disconnected = MagicMock(return_value=asyncio.sleep(0, result=False))

    async def collect() -> list[str]:
        out: list[str] = []
        async for chunk in sse_module._event_generator(request):
            out.append(chunk)
        return out

    frames = asyncio.run(collect())
    assert any(f.startswith("event: error\n") for f in frames), (
        f"expected an 'event: error' frame; got {frames!r}"
    )
    error_frame = next(f for f in frames if f.startswith("event: error\n"))
    # data line follows "event: error\n" — assert the payload is parseable JSON
    data_line = error_frame.split("\n")[1]
    assert data_line.startswith("data: ")
    payload = json.loads(data_line[len("data: ") :])
    assert payload["type"] == "RuntimeError"
    assert "simulated DB outage" in payload["message"]
    assert payload["stage"] == "init"


def test_event_generator_surfaces_loop_failures_as_error_frame(monkeypatch):
    """Exception during the poll loop must be surfaced with stage='loop'."""
    import asyncio
    import json
    from unittest.mock import MagicMock

    from dashboard.routers import sse as sse_module

    # Initial fetch succeeds so we enter the loop.
    monkeypatch.setattr(sse_module, "_get_latest_event_id", lambda: 0)

    calls = {"n": 0}

    def _fetch_fails_on_second_call(_last_id: int) -> list[object]:
        calls["n"] += 1
        if calls["n"] == 1:
            return []
        raise ValueError("simulated schema drift")

    monkeypatch.setattr(sse_module, "_fetch_new_events", _fetch_fails_on_second_call)

    # Let the loop run twice: first iteration returns [], second raises.
    disconnect_calls = {"n": 0}

    async def _not_disconnected() -> bool:
        disconnect_calls["n"] += 1
        return disconnect_calls["n"] > 3  # bail out after a few iterations if no error

    request = MagicMock()
    request.is_disconnected = _not_disconnected

    # Patch asyncio.sleep to no-op so the test runs fast.
    async def _no_sleep(_secs: float) -> None:
        return None

    monkeypatch.setattr(sse_module.asyncio, "sleep", _no_sleep)

    async def collect() -> list[str]:
        out: list[str] = []
        async for chunk in sse_module._event_generator(request):
            out.append(chunk)
        return out

    frames = asyncio.run(collect())
    error_frames = [f for f in frames if f.startswith("event: error\n")]
    assert error_frames, f"expected an 'event: error' frame; got {frames!r}"
    payload = json.loads(error_frames[0].split("\n")[1][len("data: ") :])
    assert payload["type"] == "ValueError"
    assert "simulated schema drift" in payload["message"]
    assert payload["stage"] == "loop"
