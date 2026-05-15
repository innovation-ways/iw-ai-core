"""Unit tests for `orch.chat.filters.normalise`.

OpenCode's `/event` stream emits SSE frames whose `event:` line is absent;
the type and id live inside the JSON payload (`{"id", "type", "properties"}`).
The S02 pre-step spike captured this wire shape verbatim — the dashboard
relay normalises every frame to `{event, data, id}` before fanning it out.

Tests are TDD-RED: written and run BEFORE `orch.chat.filters` exists.
"""

from __future__ import annotations

import json

import pytest

# The httpx_sse import is intentionally at module level — if the dep is
# missing, the test collection fails loudly rather than silently skipping.
from httpx_sse import ServerSentEvent

from orch.chat import filters


def _sse(event: str, data: dict | None, id_: str = "") -> ServerSentEvent:
    """Build a `ServerSentEvent` mimicking what httpx_sse produces."""
    return ServerSentEvent(
        event=event,
        data="" if data is None else json.dumps(data),
        id=id_,
    )


def test_normalise_data_only_frame_extracts_type_and_id_from_payload() -> None:
    """OpenCode's wire format: no `event:` line, type/id are embedded in the JSON."""
    payload = {
        "id": "evt_abcdef",
        "type": "message.part.delta",
        "properties": {"sessionID": "ses_1", "delta": "hello"},
    }
    sse = _sse(event="", data=payload, id_="")  # opencode never sets `event:` or `id:`
    out = filters.normalise(sse)
    assert out == {"event": "message.part.delta", "data": payload, "id": "evt_abcdef"}


def test_normalise_known_event_with_explicit_event_line() -> None:
    """If a future OpenCode version sets `event:` and `id:` lines, honour them."""
    payload = {"sessionID": "ses_1", "messageID": "msg_x"}
    sse = _sse(event="message.part.updated", data=payload, id_="evt_99")
    out = filters.normalise(sse)
    # Both routes must produce `{event, data, id}` triple.
    assert out["event"] == "message.part.updated"
    assert out["data"] == payload
    assert out["id"] == "evt_99"


def test_normalise_unknown_event_passthrough() -> None:
    """Unknown event types must not be dropped — the relay is dumb on purpose."""
    payload = {"id": "evt_z", "type": "some.future.event", "properties": {"foo": 1}}
    sse = _sse(event="", data=payload, id_="")
    out = filters.normalise(sse)
    assert out == {"event": "some.future.event", "data": payload, "id": "evt_z"}


def test_normalise_empty_data_yields_none() -> None:
    """An SSE frame with no `data:` line → normalised `data` should be None.

    `ServerSentEvent` defaults `event="message"` per the WHATWG SSE spec when
    no `event:` line is present, so we expect "message" rather than "".
    """
    sse = _sse(event="", data=None, id_="")
    out = filters.normalise(sse)
    assert out["data"] is None
    assert out["event"] == "message"  # SSE default
    assert out["id"] == ""


def test_normalise_non_json_data_preserved_as_string() -> None:
    """If OpenCode ever sends non-JSON data (e.g. plain text), keep the raw text."""
    sse = ServerSentEvent(event="text.frame", data="ping at 12:03:04", id="42")
    out = filters.normalise(sse)
    assert out["event"] == "text.frame"
    assert out["data"] == "ping at 12:03:04"
    assert out["id"] == "42"


def test_interesting_events_constant_covers_v1_render_set() -> None:
    """The dashboard renders this fixed set of events; the constant is the contract."""
    expected = {
        "message.part.updated",
        "tool.execute.before",
        "tool.execute.after",
        "permission.asked",
        "permission.replied",
        "session.idle",
        "session.updated",
        "session.error",
    }
    assert set(filters.INTERESTING_EVENTS) == expected


def test_normalise_event_line_wins_when_payload_lacks_type() -> None:
    """If the JSON has no `type` key, fall back to the wire-level event."""
    payload = {"id": "evt_x", "properties": {"k": "v"}}
    sse = _sse(event="custom.event", data=payload, id_="evt_x")
    out = filters.normalise(sse)
    assert out["event"] == "custom.event"
    assert out["id"] == "evt_x"


@pytest.mark.parametrize("bad", ['{"id":', "not json {", "[1,2,3"])
def test_normalise_malformed_json_preserved_as_string(bad: str) -> None:
    """Malformed JSON falls back to the raw string — don't crash the relay."""
    sse = ServerSentEvent(event="garbled", data=bad, id="0")
    out = filters.normalise(sse)
    assert out["data"] == bad
    assert out["event"] == "garbled"
