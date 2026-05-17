"""Tests that pin the chat panel's wire-protocol contract against opencode SDK.

These tests would FAIL before the I-00087 fix (chat.js never listened for
'message.part.updated' and never read 'properties.delta' / 'properties.part.text').
They PASS after the fix.

Placed in tests/dashboard/ (not tests/unit/) so future tests in the same file
can use the db_session / client fixtures from tests/dashboard/conftest.py.
No DB or FastAPI client is required by the current tests — all assertions are
pure text/regex inspection of chat.js.
"""

from __future__ import annotations

import re
from pathlib import Path

from orch.chat.filters import INTERESTING_EVENTS

CHAT_JS = Path(__file__).resolve().parents[2] / "dashboard/static/chat_assistant/chat.js"

# Pre-S01 namedEvents array contents — the exact strings that lived in chat.js
# before the I-00087 fix. Used as an in-test fixture to prove RED without
# reverting shipped source (reverting shipped source is a banned anti-pattern).
PRE_FIX_NAMED_EVENTS: frozenset[str] = frozenset(
    {
        "message.part",
        "message.snapshot",
        "message.complete",
        "message.updated",
        "tool.call",
        "tool.result",
        "permission.asked",
        "session.idle",
        "error",
        "gap",
        "reconnecting",
    }
)


def _registered_event_names(js_source: str) -> set[str]:
    """Extract every event name passed to EventSource.addEventListener(<name>, …).

    Handles both the array-form (namedEvents.forEach) and direct addEventListener
    calls with string literal arguments.
    """
    direct = set(re.findall(r"addEventListener\(\s*['\"]([\w.]+)['\"]", js_source))
    array_blocks = re.findall(r"namedEvents\s*=\s*\[([\s\S]*?)\]", js_source)
    array_names: set[str] = set()
    for block in array_blocks:
        array_names.update(re.findall(r"['\"]([\w.]+)['\"]", block))
    return direct | array_names


def test_chat_js_registers_every_interesting_event() -> None:
    """Every event in INTERESTING_EVENTS must have a frontend listener.

    A missing listener means the relay forwards the event and the UI silently
    drops it — the exact regression that caused I-00087.
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    registered = _registered_event_names(js)
    missing = set(INTERESTING_EVENTS) - registered
    assert not missing, (
        f"chat.js is missing EventSource listeners for opencode events "
        f"that the relay forwards: {sorted(missing)}"
    )


def test_chat_js_reads_properties_delta_for_streaming_text() -> None:
    """opencode wraps every event payload under properties.*.

    The handler must read properties.delta (streaming chunks) and
    properties.part (finalised text), not the old flat data.text / data.content.
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    assert "properties.delta" in js, (
        "_handleEvent must read properties.delta for message.part.updated frames"
    )
    assert "properties.part" in js, (
        "_handleEvent must read properties.part (or properties.part.text) for finalised text"
    )


def test_chat_js_history_reads_info_and_parts() -> None:
    """_loadHistory must iterate {info, parts} entries (opencode shape).

    The pre-fix code read m.role and m.content, which don't exist on opencode
    messages. Role lives on info.role; text content lives in parts[].text.
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    m = re.search(r"function\s+_loadHistory\b[\s\S]*?\n\s*\}\s*\n", js)
    assert m, "_loadHistory function not found in chat.js"
    body = m.group(0)
    assert ".info" in body, (
        "_loadHistory must read entry.info.role / entry.info.id "
        "(opencode messages have no top-level role field)"
    )
    assert ".parts" in body, (
        "_loadHistory must iterate entry.parts to extract text "
        "(opencode messages have no top-level content field)"
    )


def test_chat_js_preserves_session_storage_key() -> None:
    """Session-continuity invariant: sessionStorage key must use 'iw-chat-session-' + _tabId.

    The user requirement is that the chat panel retains the same opencode
    session across page refresh and between tab switches.
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    assert "'iw-chat-session-' + _tabId" in js, (
        "sessionStorage key 'iw-chat-session-' + _tabId must be preserved "
        "for session continuity across page refresh"
    )


def test_chat_js_passes_last_event_id_on_reconnect() -> None:
    """Replay-after-blip invariant: last_event_id must still be appended to the stream URL.

    When the SSE connection drops and reconnects, the relay uses Last-Event-ID
    to replay events the client missed. Removing this parameter silently breaks
    replay.
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    assert "last_event_id=" in js, (
        "_connectStream must still append ?last_event_id=<id> to the SSE URL "
        "to enable event replay after reconnect"
    )


def test_chat_js_listens_for_session_idle() -> None:
    """session.idle was the one event that worked pre-S01 and must keep working."""
    js = CHAT_JS.read_text(encoding="utf-8")
    registered = _registered_event_names(js)
    assert "session.idle" in registered, (
        "chat.js must keep listening for session.idle (the streaming-finished signal)"
    )


def test_chat_js_distinguishes_properties_from_data() -> None:
    """Handler reads properties.* for opencode-native events and data.* for relay events.

    Opencode-native events wrap payload under properties; relay-synthesised events
    (gap, reconnecting, error) use a flat data shape. Both paths must exist or
    relay events silently break.
    """
    js = CHAT_JS.read_text(encoding="utf-8")
    # opencode-native events: payload extracted via data.properties
    assert "data.properties" in js, (
        "_handleEvent must extract props from data.properties for opencode-native events"
    )
    # relay-synthesised events: gap and reconnecting must still be registered
    registered = _registered_event_names(js)
    assert "gap" in registered, (
        "relay-synthesised 'gap' event must still be registered in namedEvents"
    )
    assert "reconnecting" in registered, (
        "relay-synthesised 'reconnecting' event must still be registered in namedEvents"
    )
    # relay error handler still reads from data directly (flat shape, no properties)
    assert "data.message" in js, (
        "_handleEvent relay error branch must still read data.message "
        "(relay error events have no properties wrapper)"
    )


def test_starter_listener_set_would_have_failed_protocol_check() -> None:
    """RED evidence: the pre-S01 namedEvents array fails the protocol contract check.

    Runs the same logic as test_chat_js_registers_every_interesting_event against
    PRE_FIX_NAMED_EVENTS to confirm the pre-fix code was missing INTERESTING_EVENTS
    members. This is the in-test equivalent of running against old chat.js without
    reverting shipped source.
    """
    missing = set(INTERESTING_EVENTS) - PRE_FIX_NAMED_EVENTS
    assert missing, (
        "PRE_FIX_NAMED_EVENTS unexpectedly satisfies the protocol check — "
        "the fixture may be wrong. "
        f"INTERESTING_EVENTS={sorted(INTERESTING_EVENTS)}, "
        f"PRE_FIX={sorted(PRE_FIX_NAMED_EVENTS)}"
    )
