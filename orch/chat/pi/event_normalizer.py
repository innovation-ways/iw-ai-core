"""Pi RPC event → OpenCode-shaped envelope translator (F-00087).

Every event emitted by the Pi subprocess over its JSONL stdout is translated
here into the same envelope shape that OpenCode events use.  This lets the
existing frontend (F-00086) and RelayManager handle Pi events without knowing
anything about Pi's internals.

**Invariant**: this normalizer does NOT add ``tab_id`` — that is RelayManager's
job (F-00086 invariant #2).

References: F-00087 §Scope event-mapping table, R-00072 §2.
"""

from __future__ import annotations

import json
from typing import Any

# The IW chat-approvals extension raises its approval prompts via
# ``ctx.ui.confirm`` with this exact dialog title.  Pi (>=0.79) does NOT
# namespace ``extension_ui_request`` ids by extension — the id is a random
# UUID — so routing keys on the confirm ``title`` instead.  The structured
# payload (tool name + args) travels in the confirm ``message`` as a JSON
# envelope; see ``.pi/extensions/iw-chat-approvals/index.ts``.
_IW_APPROVALS_TITLE = "iw-chat-approvals"

_PASSTHROUGH_TYPES = frozenset(
    {
        "turn_start",
        "turn_end",
        "compaction_start",
        "compaction_end",
        "auto_retry_start",
        "auto_retry_end",
    }
)


def normalize_pi_event(pi_event: dict[str, Any]) -> dict[str, Any] | None:
    """Translate a Pi RPC event into an OpenCode-shaped envelope.

    Returns ``None`` for events that should be silently dropped.

    The returned dict always contains a top-level ``"event"`` key whose
    value is the OpenCode-side event name, and a ``"data"`` key carrying
    the payload.  ``tab_id`` is NOT added here — RelayManager stamps it.

    References: F-00087 §Scope event-mapping table.
    """
    event_type = pi_event.get("type")
    if not isinstance(event_type, str):
        return None

    # ------------------------------------------------------------------
    # Streaming text delta — message.part.added
    # ------------------------------------------------------------------
    if event_type == "message_update":
        assistant_event = pi_event.get("assistantMessageEvent", {})
        if isinstance(assistant_event, dict) and assistant_event.get("type") == "text_delta":
            delta = assistant_event.get("delta", "")
            return {
                "event": "message.part.added",
                "data": {
                    "part": {
                        "type": "text",
                        "text": delta,
                    }
                },
            }
        # Other message_update subtypes — passthrough.
        return {"event": "message_update", "data": pi_event}

    # ------------------------------------------------------------------
    # Tool execution lifecycle
    # ------------------------------------------------------------------
    if event_type == "tool_execution_start":
        return {
            "event": "tool.execution.start",
            "data": {
                "tool": pi_event.get("tool"),
                "args": pi_event.get("args"),
                **{k: v for k, v in pi_event.items() if k not in ("type", "tool", "args")},
            },
        }

    if event_type == "tool_execution_update":
        return {
            "event": "tool.execution.update",
            "data": {k: v for k, v in pi_event.items() if k != "type"},
        }

    if event_type == "tool_execution_end":
        return {
            "event": "tool.execution.end",
            "data": {
                "result": pi_event.get("result"),
                **{k: v for k, v in pi_event.items() if k not in ("type", "result")},
            },
        }

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    if event_type == "agent_start":
        return {
            "event": "session.start",
            "data": {k: v for k, v in pi_event.items() if k != "type"},
        }

    if event_type == "agent_end":
        return {
            "event": "session.idle",
            "data": {k: v for k, v in pi_event.items() if k != "type"},
        }

    # ------------------------------------------------------------------
    # Extension UI (approval flow)
    # ------------------------------------------------------------------
    if event_type == "extension_ui_request":
        method = pi_event.get("method")
        title = pi_event.get("title", "")
        if method == "confirm" and isinstance(title, str) and title.startswith(_IW_APPROVALS_TITLE):
            # Route to the F-00086 approval modal.  The iw-chat-approvals
            # extension packs {tool, args, question} into the confirm message
            # as JSON; degrade gracefully to the raw message if it is not.
            tool: Any = None
            args: Any = {}
            message = pi_event.get("message", "")
            question = message
            if isinstance(message, str):
                try:
                    parsed = json.loads(message)
                except (ValueError, TypeError):
                    parsed = None
                if isinstance(parsed, dict):
                    tool = parsed.get("tool")
                    args = parsed.get("args", {})
                    question = parsed.get("question", message)
            return {
                "event": "permission.asked",
                "data": {
                    "id": pi_event.get("id", ""),
                    "tool": tool,
                    "args": args,
                    "question": question,
                },
            }
        # Other extension UI requests — passthrough for future extensibility.
        return {
            "event": "extension.ui_request",
            "data": pi_event,
        }

    # ------------------------------------------------------------------
    # Extension errors
    # ------------------------------------------------------------------
    if event_type == "extension_error":
        return {
            "event": "session.error",
            "data": {k: v for k, v in pi_event.items() if k != "type"},
        }

    # ------------------------------------------------------------------
    # Passthrough events — frontend ignores unknown types gracefully
    # ------------------------------------------------------------------
    if event_type in _PASSTHROUGH_TYPES:
        return {"event": event_type, "data": {k: v for k, v in pi_event.items() if k != "type"}}

    # ------------------------------------------------------------------
    # Unknown event type — passthrough with original type field
    # ------------------------------------------------------------------
    return {"event": event_type, "data": pi_event}
