"""Multi-session SSE relay between `OpencodeClient` and dashboard browsers.

`SessionRelay` runs ONE upstream pump task per OpenCode session, holds a
ring buffer of the most recent events (for tab-refresh replay via
`Last-Event-ID`), and fans events out to N browser subscribers. A slow
subscriber's queue is allowed to fill and overflow with dropped events
— the others must not stall.

`RelayManager` owns the dict of sid → SessionRelay and lazily creates
relays on first subscribe.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import deque
from typing import TYPE_CHECKING, Any

import httpx

from orch.chat import filters

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from orch.chat.opencode_client import OpencodeClient

logger = logging.getLogger(__name__)

_DEFAULT_BUFFER_SIZE = 256
_DEFAULT_SUBSCRIBER_QUEUE_SIZE = 256
_RECONNECT_BACKOFF_MIN = 0.3  # seconds
_RECONNECT_BACKOFF_MAX = 3.0  # seconds
_RELAY_ERROR_EVENT = "relay.error"
_RELAY_GAP_EVENT = "gap"


class SessionRelay:
    """Owns the upstream pump + ring buffer + subscriber fan-out for ONE session."""

    def __init__(
        self,
        client: OpencodeClient,
        sid: str,
        buffer_size: int = _DEFAULT_BUFFER_SIZE,
        *,
        subscriber_queue_size: int = _DEFAULT_SUBSCRIBER_QUEUE_SIZE,
    ) -> None:
        self._client = client
        self._sid = sid
        self._buffer: deque[dict[str, Any]] = deque(maxlen=buffer_size)
        self._subscribers: list[asyncio.Queue[dict[str, Any] | None]] = []
        self._subscriber_queue_size = subscriber_queue_size
        self._pump_task: asyncio.Task[None] | None = None
        self._stopped = False
        self._last_seen_id: str | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._pump_task is not None and not self._pump_task.done():
            return
        self._stopped = False
        self._pump_task = asyncio.create_task(self._pump(), name=f"relay-pump-{self._sid}")

    async def stop(self) -> None:
        self._stopped = True
        task = self._pump_task
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, BaseException):
                await task
        self._pump_task = None
        # Sentinel-wake any waiting subscribers so their iteration ends.
        for q in list(self._subscribers):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(None)

    def is_running(self) -> bool:
        return self._pump_task is not None and not self._pump_task.done()

    def subscriber_count(self) -> int:
        return len(self._subscribers)

    # ------------------------------------------------------------------
    # Subscriber-facing API
    # ------------------------------------------------------------------

    def subscribe(
        self,
        last_event_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Return an async iterator over normalised event dicts.

        On entry: if ``last_event_id`` is provided, snapshot the ring
        buffer and replay events newer than ``last_event_id`` (or the
        full buffer if ``last_event_id`` cannot be located — assume it
        has aged out). When ``last_event_id`` is None, no replay
        happens; the subscriber only sees future events.

        Registration is synchronous so the queue is in place before the
        next pump iteration.
        """
        if last_event_id is None:
            replay: list[dict[str, Any]] = []
        else:
            replay = self._compute_replay(last_event_id)
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(
            maxsize=self._subscriber_queue_size
        )
        self._subscribers.append(queue)
        return self._iter_subscription(queue, replay)

    def _compute_replay(self, last_event_id: str) -> list[dict[str, Any]]:
        snapshot = list(self._buffer)
        for i, ev in enumerate(snapshot):
            if ev.get("id") == last_event_id:
                return snapshot[i + 1 :]
        # last_event_id not found — assume it aged out. Replay everything we
        # have and prepend a one-time `gap` warning so the browser can surface
        # to the user that some events were dropped (per design's Boundary
        # Behavior row). When the buffer is empty there's nothing to warn
        # about, so no gap event is emitted.
        if not snapshot:
            return snapshot
        gap_event: dict[str, Any] = {
            "event": _RELAY_GAP_EVENT,
            "data": {
                "reason": "last_event_id_aged_out",
                "last_event_id": last_event_id,
                "buffer_size": len(snapshot),
            },
            "id": "",
        }
        return [gap_event, *snapshot]

    async def _iter_subscription(
        self,
        queue: asyncio.Queue[dict[str, Any] | None],
        replay: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            for ev in replay:
                yield ev
            while True:
                item = await queue.get()
                if item is None:
                    return
                yield item
        finally:
            with contextlib.suppress(ValueError):
                self._subscribers.remove(queue)

    # ------------------------------------------------------------------
    # Upstream pump
    # ------------------------------------------------------------------

    async def _pump(self) -> None:
        backoff = _RECONNECT_BACKOFF_MIN
        consecutive_persistent_errors = 0
        while not self._stopped:
            try:
                async for sse in self._client.stream_events(last_event_id=self._last_seen_id):
                    if self._stopped:
                        return
                    ev = filters.normalise(sse)
                    self._buffer.append(ev)
                    ev_id = ev.get("id")
                    if isinstance(ev_id, str) and ev_id:
                        self._last_seen_id = ev_id
                    self._broadcast(ev)
                    # Cooperative yield: in production the upstream socket
                    # provides natural backpressure between events; in tests
                    # with a queued fake client we must yield explicitly so
                    # consumers can drain their queues and not be dropped.
                    await asyncio.sleep(0)
                # Iterator exhausted cleanly — upstream closed. Reconnect.
                if self._stopped:
                    return
                backoff = _RECONNECT_BACKOFF_MIN
                consecutive_persistent_errors = 0
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                raise
            except httpx.ReadError as exc:
                logger.info(
                    "relay upstream ReadError on sid=%s: %s; retry in %.2fs",
                    self._sid,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(_RECONNECT_BACKOFF_MAX, backoff * 2)
            except (httpx.HTTPError, OSError) as exc:
                consecutive_persistent_errors += 1
                logger.error(
                    "relay upstream error on sid=%s: %s (consecutive=%d)",
                    self._sid,
                    exc,
                    consecutive_persistent_errors,
                )
                self._broadcast(
                    {
                        "event": _RELAY_ERROR_EVENT,
                        "data": {
                            "sid": self._sid,
                            "error": type(exc).__name__,
                            "message": str(exc),
                            "consecutive": consecutive_persistent_errors,
                        },
                        "id": "",
                    }
                )
                await asyncio.sleep(backoff)
                backoff = min(_RECONNECT_BACKOFF_MAX, backoff * 2)

    def _broadcast(self, ev: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                logger.warning(
                    "relay subscriber on sid=%s is slow; dropping event id=%s",
                    self._sid,
                    ev.get("id"),
                )


class RelayManager:
    """Owns sid → `SessionRelay` and lazily spawns pumps."""

    def __init__(self, client: OpencodeClient) -> None:
        self._client = client
        self._relays: dict[str, SessionRelay] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_relay(self, sid: str) -> SessionRelay:
        async with self._lock:
            relay = self._relays.get(sid)
            if relay is None:
                relay = SessionRelay(self._client, sid)
                self._relays[sid] = relay
                await relay.start()
            elif not relay.is_running():
                await relay.start()
            return relay

    async def drop_relay(self, sid: str) -> None:
        async with self._lock:
            relay = self._relays.pop(sid, None)
        if relay is not None:
            await relay.stop()

    async def shutdown(self) -> None:
        async with self._lock:
            relays = list(self._relays.values())
            self._relays.clear()
        for r in relays:
            await r.stop()
