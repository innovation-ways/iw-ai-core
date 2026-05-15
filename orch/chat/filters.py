"""Event-shape normalisation for OpenCode SSE frames.

OpenCode's `/event` stream sends `data:`-only SSE frames (no `event:` or
`id:` lines). The actual type/id live INSIDE the JSON payload, e.g.::

    data: {"id":"evt_abc","type":"message.part.delta","properties":{...}}

The S02 pre-step spike captured this wire shape verbatim. The relay
normalises every frame to a `{event, data, id}` triple so downstream
subscribers see one consistent shape regardless of whether OpenCode
(today) or a future runtime (with proper `event:`/`id:` lines) emits the
event.

Unknown event types are passed through verbatim — never dropped.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from httpx_sse import ServerSentEvent

# Events the dashboard cares about for rendering. The relay still forwards
# everything; this constant exists for the UI / docs to enumerate what the
# v1 chat panel knows how to render.
INTERESTING_EVENTS: tuple[str, ...] = (
    "message.part.updated",
    "tool.execute.before",
    "tool.execute.after",
    "permission.asked",
    "permission.replied",
    "session.idle",
    "session.updated",
    "session.error",
)


def normalise(sse: ServerSentEvent) -> dict[str, Any]:
    """Convert an `httpx_sse.ServerSentEvent` to `{event, data, id}`.

    Resolution order for `event` and `id`:

    1. Try to JSON-parse `sse.data`. If it's a dict with `type`/`id` keys,
       those win (this is the opencode wire shape).
    2. Otherwise, fall back to the wire-level `sse.event` / `sse.id`.

    `data` is the parsed JSON value if parsing succeeds, otherwise the raw
    `sse.data` string (or `None` if data is empty).
    """
    raw = sse.data
    if not raw:
        data: Any = None
    else:
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            data = raw  # preserve as string

    event_name = sse.event or ""
    event_id = sse.id or ""
    if isinstance(data, dict):
        t = data.get("type")
        if isinstance(t, str) and t:
            event_name = t
        i = data.get("id")
        if isinstance(i, str) and i:
            event_id = i

    return {"event": event_name, "data": data, "id": event_id}
