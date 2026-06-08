"""Unit tests for ``orch.chat.pi.event_normalizer.normalize_pi_event`` (F-00087).

Invariant #6 — extension_ui_request → permission.asked translation preserves
id and unpacks tool, args, question from the confirm message envelope.

Covers every row in the §Scope event-mapping table:
    - message_update / text_delta → message.part.added
    - tool_execution_start → tool.execution.start
    - tool_execution_update → tool.execution.update
    - tool_execution_end → tool.execution.end
    - agent_start → session.start
    - agent_end → session.idle
    - extension_ui_request (confirm, title=iw-chat-approvals) → permission.asked
    - extension_ui_request (other title / non-confirm method) → passthrough
    - extension_error → session.error
    - turn_start / turn_end / compaction_start / compaction_end /
      auto_retry_start / auto_retry_end → passthrough as-is
    - unknown event type → passthrough with original type field
    - normalizer does NOT add tab_id (that is RelayManager's job)
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from orch.chat.pi.event_normalizer import normalize_pi_event

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm(pi_event: dict[str, Any]) -> dict[str, Any]:
    """Call normalize_pi_event and assert the result is non-None before returning it.

    Args:
        pi_event: Raw Pi event dict to normalize.

    Returns:
        The normalized event dict (asserts non-None internally).
    """
    result = normalize_pi_event(pi_event)
    assert result is not None, f"normalize_pi_event returned None for input: {pi_event!r}"
    return result


# ---------------------------------------------------------------------------
# message_update / text_delta → message.part.added
# ---------------------------------------------------------------------------


def test_message_update_text_delta_becomes_message_part_added() -> None:
    """message_update with assistantMessageEvent.type=text_delta → message.part.added."""
    pi_event = {
        "type": "message_update",
        "assistantMessageEvent": {"type": "text_delta", "delta": "Hello, world!"},
    }
    result = _norm(pi_event)

    assert result["event"] == "message.part.added"
    assert result["data"]["part"]["type"] == "text"
    assert result["data"]["part"]["text"] == "Hello, world!"


def test_message_update_non_text_delta_passes_through() -> None:
    """message_update with a non-text_delta assistantMessageEvent → passthrough."""
    pi_event = {
        "type": "message_update",
        "assistantMessageEvent": {"type": "something_else", "content": "x"},
    }
    result = _norm(pi_event)
    # Not message.part.added — falls through to passthrough.
    assert result["event"] == "message_update"
    assert result["data"] == pi_event


# ---------------------------------------------------------------------------
# Tool execution lifecycle
# ---------------------------------------------------------------------------


def test_tool_execution_start_maps_to_correct_event() -> None:
    """tool_execution_start is normalized to tool.execution.start with tool and args preserved."""
    pi_event = {"type": "tool_execution_start", "tool": "bash", "args": {"cmd": "ls"}}
    result = _norm(pi_event)

    assert result["event"] == "tool.execution.start"
    assert result["data"]["tool"] == "bash"
    assert result["data"]["args"] == {"cmd": "ls"}


def test_tool_execution_update_maps_to_correct_event() -> None:
    """tool_execution_update is normalized to tool.execution.update with payload preserved."""
    pi_event = {"type": "tool_execution_update", "progress": 50, "output": "part1"}
    result = _norm(pi_event)

    assert result["event"] == "tool.execution.update"
    assert result["data"]["progress"] == 50
    assert result["data"]["output"] == "part1"
    assert "type" not in result["data"]


def test_tool_execution_end_maps_to_correct_event() -> None:
    """tool_execution_end is normalized to tool.execution.end with result and extra fields
    preserved.
    """
    pi_event = {"type": "tool_execution_end", "result": "done!", "tool": "bash"}
    result = _norm(pi_event)

    assert result["event"] == "tool.execution.end"
    assert result["data"]["result"] == "done!"
    # Extra fields preserved.
    assert result["data"]["tool"] == "bash"
    assert "type" not in result["data"]


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


def test_agent_start_becomes_session_start() -> None:
    """agent_start is normalized to session.start with payload preserved and type key removed."""
    pi_event = {"type": "agent_start", "session_id": "abc"}
    result = _norm(pi_event)

    assert result["event"] == "session.start"
    assert result["data"]["session_id"] == "abc"
    assert "type" not in result["data"]


def test_agent_end_becomes_session_idle() -> None:
    """agent_end is normalized to session.idle with payload preserved and type key removed."""
    pi_event = {"type": "agent_end", "reason": "done"}
    result = _norm(pi_event)

    assert result["event"] == "session.idle"
    assert result["data"]["reason"] == "done"
    assert "type" not in result["data"]


# ---------------------------------------------------------------------------
# Extension UI (approval flow) — invariant #6
# ---------------------------------------------------------------------------


def test_extension_ui_request_confirm_with_iw_title_becomes_permission_asked() -> None:
    """confirm extension_ui_request titled 'iw-chat-approvals' → permission.asked.

    Pi 0.79 emits method/title/message (id is a random UUID); the tool, args,
    and question are packed into the message as a JSON envelope and must be
    unpacked into the permission.asked payload, with the id preserved.
    """
    pi_event = {
        "type": "extension_ui_request",
        "id": "a1b2c3d4-uuid",
        "method": "confirm",
        "title": "iw-chat-approvals",
        "message": json.dumps(
            {
                "tool": "bash",
                "args": {"cmd": "rm temp.txt"},
                "question": "Allow bash to run 'rm temp.txt'?",
            }
        ),
    }
    result = _norm(pi_event)

    assert result["event"] == "permission.asked", (
        f"expected permission.asked, got {result['event']!r}"
    )
    data = result["data"]
    assert data["id"] == "a1b2c3d4-uuid"
    assert data["tool"] == "bash"
    assert data["args"] == {"cmd": "rm temp.txt"}
    assert data["question"] == "Allow bash to run 'rm temp.txt'?"


def test_extension_ui_request_confirm_with_malformed_message_degrades() -> None:
    """A confirm with a non-JSON message still routes, using the raw message as question."""
    pi_event = {
        "type": "extension_ui_request",
        "id": "uuid-2",
        "method": "confirm",
        "title": "iw-chat-approvals",
        "message": "not json at all",
    }
    result = _norm(pi_event)

    assert result["event"] == "permission.asked"
    data = result["data"]
    assert data["id"] == "uuid-2"
    assert data["tool"] is None
    assert data["args"] == {}
    assert data["question"] == "not json at all"


def test_extension_ui_request_with_other_title_passes_through() -> None:
    """A confirm from a different extension title → extension.ui_request passthrough."""
    pi_event = {
        "type": "extension_ui_request",
        "id": "uuid-3",
        "method": "confirm",
        "title": "some-other-extension",
        "message": "{}",
    }
    result = _norm(pi_event)

    assert result["event"] == "extension.ui_request"
    # The original event is preserved in data.
    assert result["data"] == pi_event


def test_extension_ui_request_non_confirm_method_passes_through() -> None:
    """A non-confirm method (e.g. notify) with the iw title does NOT route to approval."""
    pi_event = {
        "type": "extension_ui_request",
        "id": "uuid-4",
        "method": "notify",
        "title": "iw-chat-approvals",
        "message": "fyi",
    }
    result = _norm(pi_event)
    assert result["event"] == "extension.ui_request", (
        "only method=='confirm' should route to permission.asked"
    )


# ---------------------------------------------------------------------------
# Extension errors
# ---------------------------------------------------------------------------


def test_extension_error_becomes_session_error() -> None:
    """extension_error is normalized to session.error with message and code preserved."""
    pi_event = {"type": "extension_error", "message": "Extension crashed", "code": 1}
    result = _norm(pi_event)

    assert result["event"] == "session.error"
    assert result["data"]["message"] == "Extension crashed"
    assert result["data"]["code"] == 1
    assert "type" not in result["data"]


# ---------------------------------------------------------------------------
# Passthrough event types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_type",
    [
        "turn_start",
        "turn_end",
        "compaction_start",
        "compaction_end",
        "auto_retry_start",
        "auto_retry_end",
    ],
)
def test_passthrough_event_types_preserve_data(event_type: str) -> None:
    """Documented passthrough events are returned with their original type as event key."""
    pi_event = {"type": event_type, "extra": "value"}
    result = _norm(pi_event)

    assert result["event"] == event_type, f"event type {event_type!r} should pass through as-is"
    assert result["data"]["extra"] == "value"
    assert "type" not in result["data"]


# ---------------------------------------------------------------------------
# Unknown event type — passthrough with original type field (invariant #6 edge)
# ---------------------------------------------------------------------------


def test_unknown_event_type_passes_through() -> None:
    """An unrecognised event type must pass through as-is; frontend ignores unknowns."""
    pi_event = {"type": "future_event_type_v99", "payload": {"k": "v"}}
    result = _norm(pi_event)

    # The event field uses the original type string.
    assert result["event"] == "future_event_type_v99"
    # The full original event is preserved in data.
    assert result["data"] == pi_event


# ---------------------------------------------------------------------------
# Invariant: normalizer does NOT add tab_id
# ---------------------------------------------------------------------------


def test_normalizer_does_not_add_tab_id() -> None:
    """normalize_pi_event must never stamp tab_id — that is RelayManager's job."""
    pi_events = [
        {"type": "agent_start"},
        {"type": "agent_end"},
        {
            "type": "message_update",
            "assistantMessageEvent": {"type": "text_delta", "delta": "hi"},
        },
        {
            "type": "extension_ui_request",
            "id": "abc-uuid",
            "method": "confirm",
            "title": "iw-chat-approvals",
            "message": json.dumps({"tool": "bash", "args": {}, "question": "?"}),
        },
        {"type": "unknown_xyz"},
    ]
    for pi_event in pi_events:
        result = normalize_pi_event(pi_event)
        assert result is not None
        assert "tab_id" not in result, (
            f"normalizer should NOT add tab_id (found in result for {pi_event!r})"
        )
        # Also check the nested data dict.
        assert "tab_id" not in result.get("data", {}), (
            f"normalizer should NOT add tab_id inside data (found for {pi_event!r})"
        )


# ---------------------------------------------------------------------------
# None / malformed input
# ---------------------------------------------------------------------------


def test_missing_type_returns_none() -> None:
    """An event with no 'type' key should return None (silently dropped)."""
    result = normalize_pi_event({"no_type_here": True})
    assert result is None


def test_non_string_type_returns_none() -> None:
    """An event with a non-string 'type' field should return None."""
    result = normalize_pi_event({"type": 42})
    assert result is None
