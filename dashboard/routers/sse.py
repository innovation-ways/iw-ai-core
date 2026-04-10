"""Server-Sent Events endpoint for real-time dashboard updates."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from orch.db.models import DaemonEvent
from orch.db.session import SessionLocal

router = APIRouter(prefix="/api")

# Event types that trigger a running-table refresh
_RUNNING_UPDATE_EVENTS = frozenset(
    {"step_launched", "step_completed", "step_killed", "step_crashed", "step_timeout"}
)
# Event types that show a toast notification
_TOAST_EVENTS = frozenset(
    {
        "step_failed",
        "step_timeout",
        "step_stalled",
        "step_crashed",
        "batch_completed",
        "batch_completed_with_errors",
        "item_merged",
        "merge_conflict",
        "poll_error",
        "batch_archiving",
        "batch_archived",
        "batch_archive_failed",
        "test_started",
        "test_completed",
        "test_failed",
    }
)
# Test-specific events that trigger test tab refresh
_TEST_UPDATE_EVENTS = frozenset({"test_started", "test_completed", "test_failed"})
# All events we care about (union)
_WATCHED_EVENTS = _RUNNING_UPDATE_EVENTS | _TOAST_EVENTS | _TEST_UPDATE_EVENTS

_TOAST_SEVERITY: dict[str, str] = {
    "step_failed": "error",
    "step_timeout": "warning",
    "step_stalled": "warning",
    "step_crashed": "error",
    "batch_completed": "success",
    "batch_completed_with_errors": "warning",
    "item_merged": "info",
    "merge_conflict": "error",
    "poll_error": "error",
    "batch_archiving": "info",
    "batch_archived": "success",
    "batch_archive_failed": "error",
    "test_started": "info",
    "test_completed": "success",
    "test_failed": "error",
}


def _fetch_new_events(last_id: int) -> list[DaemonEvent]:
    """Synchronous DB fetch — runs inside asyncio.to_thread."""
    db = SessionLocal()
    try:
        return list(
            db.scalars(
                select(DaemonEvent)
                .where(
                    DaemonEvent.id > last_id,
                    DaemonEvent.event_type.in_(list(_WATCHED_EVENTS)),
                )
                .order_by(DaemonEvent.id)
                .limit(50)
            ).all()
        )
    finally:
        db.close()


async def _event_generator(request: Request) -> AsyncGenerator[str, None]:
    """Async generator that polls DB every 5 seconds and yields SSE lines."""
    last_id = _get_latest_event_id()
    ping_tick = 0

    while not await request.is_disconnected():
        events: list[DaemonEvent] = await asyncio.to_thread(_fetch_new_events, last_id)

        for event in events:
            last_id = max(last_id, event.id)

            if event.event_type in _RUNNING_UPDATE_EVENTS:
                data = json.dumps(
                    {
                        "event_type": event.event_type,
                        "entity_id": event.entity_id,
                        "project_id": event.project_id,
                    }
                )
                yield f"event: running-update\ndata: {data}\nid: {event.id}\n\n"

            if event.event_type in _TEST_UPDATE_EVENTS:
                data = json.dumps(
                    {
                        "event_type": event.event_type,
                        "entity_id": event.entity_id,
                        "project_id": event.project_id,
                    }
                )
                yield f"event: test-update\ndata: {data}\nid: {event.id}\n\n"

            if event.event_type in _TOAST_EVENTS:
                severity = _TOAST_SEVERITY.get(event.event_type, "info")
                data = json.dumps(
                    {
                        "message": event.message or event.event_type,
                        "type": severity,
                        "event_type": event.event_type,
                        "entity_id": event.entity_id,
                        "project_id": event.project_id,
                    }
                )
                yield f"event: toast\ndata: {data}\nid: {event.id}\n\n"

        # Send keep-alive comment every ~30 seconds (6 × 5s)
        ping_tick += 1
        if ping_tick >= 6:
            yield f": ping {datetime.now(UTC).isoformat()}\n\n"
            ping_tick = 0

        await asyncio.sleep(5)


def _get_latest_event_id() -> int:
    """Fetch the max event id so we only stream new events after connection."""
    db = SessionLocal()
    try:
        from sqlalchemy import func

        result = db.scalar(select(func.max(DaemonEvent.id)))
        return result or 0
    finally:
        db.close()


@router.get("/stream/events")
async def stream_events(request: Request) -> Any:
    """SSE stream for real-time dashboard updates.

    Clients receive two event types:
    - ``running-update``: refresh the running steps table
    - ``toast``: display a notification toast
    """
    return StreamingResponse(
        _event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
