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
    {
        "step_launched",
        "step_completed",
        "step_failed",
        "step_killed",
        "step_crashed",
        "step_timeout",
        # CR-00024: refresh the running table when the soft-warn fires so the
        # operator sees the new "Last seen" / 50% indicator without a reload.
        "step_warning_50pct",
    }
)
# Entity-level status transitions (item/batch lifecycle + step actions)
_STATUS_UPDATE_EVENTS = frozenset(
    {
        # Item lifecycle (emitted by dashboard actions)
        "item_approved",
        "item_unapproved",
        "item_cancelled",
        "item_paused",
        "item_resumed",
        "item_restarted",
        "item_full_restarted",
        # Batch lifecycle (emitted by dashboard actions + daemon)
        "batch_created",
        "batch_approved",
        "batch_paused",
        "batch_resumed",
        "batch_cancelled",
        # Step actions that affect item status display
        "step_restarted",
        "step_skipped",
    }
)
# Event types that show a toast notification
_TOAST_EVENTS = frozenset(
    {
        "step_failed",
        "step_timeout",
        "step_stalled",
        "step_crashed",
        # CR-00024: one-time soft-warn at 50% of timeout (info-level toast).
        "step_warning_50pct",
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
        # Item lifecycle
        "item_approved",
        "item_unapproved",
        "item_cancelled",
        "item_paused",
        "item_resumed",
        "item_restarted",
        "item_full_restarted",
        # Batch lifecycle
        "batch_created",
        "batch_approved",
        "batch_paused",
        "batch_resumed",
        "batch_cancelled",
        # Step actions
        "step_restarted",
        "step_skipped",
        # Lifecycle events
        "code_map_completed",
    }
)
# Test-specific events that trigger test tab refresh
_TEST_UPDATE_EVENTS = frozenset({"test_started", "test_completed", "test_failed"})
# Quality-gate events that trigger quality tab refresh
_QUALITY_UPDATE_EVENTS = frozenset({"quality_started", "quality_completed", "quality_failed"})
# All events we care about (union)
_WATCHED_EVENTS = (
    _RUNNING_UPDATE_EVENTS
    | _STATUS_UPDATE_EVENTS
    | _TOAST_EVENTS
    | _TEST_UPDATE_EVENTS
    | _QUALITY_UPDATE_EVENTS
)

_TOAST_SEVERITY: dict[str, str] = {
    "step_failed": "error",
    "step_timeout": "warning",
    "step_stalled": "warning",
    "step_crashed": "error",
    # CR-00024
    "step_warning_50pct": "info",
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
    "item_approved": "success",
    "item_unapproved": "info",
    "item_cancelled": "warning",
    "item_paused": "warning",
    "item_resumed": "success",
    "item_restarted": "info",
    "item_full_restarted": "info",
    "batch_created": "info",
    "batch_approved": "success",
    "batch_paused": "warning",
    "batch_resumed": "success",
    "batch_cancelled": "warning",
    "step_restarted": "info",
    "step_skipped": "info",
    # Lifecycle events
    "code_map_completed": "success",
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
    """Async generator that polls DB every 5 seconds and yields SSE lines.

    Any unhandled exception inside the poll loop (DB connection drop,
    schema mismatch, logic bug) is surfaced to the client as an
    ``event: error`` frame with a compact summary, and the traceback is
    logged server-side. Without this, an exception would bubble out of
    the generator and Starlette would close the stream silently — the
    browser would see ``readyState=2`` with no explanation, which is the
    same class of failure as the code_qa.py exception-swallowing bug that
    hid itself for four fix cycles on F-00060/S14.
    """
    import logging
    import traceback

    logger = logging.getLogger(__name__)

    try:
        last_id = _get_latest_event_id()
    except Exception as exc:  # noqa: BLE001
        logger.exception("sse: failed to fetch initial last_id")
        payload = json.dumps({"stage": "init", "type": type(exc).__name__, "message": str(exc)})
        yield f"event: error\ndata: {payload}\n\n"
        return

    ping_tick = 0

    while not await request.is_disconnected():
        try:
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

                if event.event_type in _QUALITY_UPDATE_EVENTS:
                    data = json.dumps(
                        {
                            "event_type": event.event_type,
                            "entity_id": event.entity_id,
                            "project_id": event.project_id,
                        }
                    )
                    yield f"event: quality-update\ndata: {data}\nid: {event.id}\n\n"

                if event.event_type in _STATUS_UPDATE_EVENTS:
                    data = json.dumps(
                        {
                            "event_type": event.event_type,
                            "entity_id": event.entity_id,
                            "project_id": event.project_id,
                        }
                    )
                    yield f"event: status-update\ndata: {data}\nid: {event.id}\n\n"

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
        except asyncio.CancelledError:
            # Client disconnected mid-iteration — let Starlette unwind.
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "sse: exception in event generator: %s\n%s",
                exc,
                traceback.format_exc(),
            )
            payload = json.dumps(
                {"stage": "loop", "type": type(exc).__name__, "message": str(exc)[:500]}
            )
            yield f"event: error\ndata: {payload}\n\n"
            return


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

    Clients receive these event types:
    - ``running-update``: refresh the running steps table
    - ``status-update``: item/batch/step lifecycle status transition
    - ``test-update``: refresh the test results tab
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
