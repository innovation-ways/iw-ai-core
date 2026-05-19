"""Unit tests for `orch.chat.opencode.relay_manager.SessionRelay` / `RelayManager`.

Tests are TDD-RED — written and run BEFORE the relay exists.

The relay multiplexes one OpenCode `/event` SSE stream onto N subscribers, holds
a per-session ring buffer (`maxlen=256`) for tab-refresh replay via
`Last-Event-ID`, and is robust to slow / cancelled subscribers.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx_sse import ServerSentEvent

from orch.chat.opencode.relay_manager import RelayManager, SessionRelay

# ---------------------------------------------------------------------------
# Fake client — drives the upstream pump deterministically.
# ---------------------------------------------------------------------------


class _FakeClient:
    """Mimics `OpencodeClient.stream_events()`.

    Yields whatever the test pushes via `feed()`.  Closed when `close_stream()`
    is called or when `_stop_after` events have been emitted.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[ServerSentEvent | None] = asyncio.Queue()
        self.connect_calls: list[str | None] = []  # last_event_id observed per call

    def feed(self, event: ServerSentEvent) -> None:
        self._queue.put_nowait(event)

    def close_stream(self) -> None:
        """Tell the upstream iterator that no more events are coming."""
        self._queue.put_nowait(None)

    def stream_events(self, *, last_event_id: str | None = None) -> AsyncIterator[ServerSentEvent]:
        self.connect_calls.append(last_event_id)
        queue = self._queue

        async def _iter() -> AsyncIterator[ServerSentEvent]:
            while True:
                item = await queue.get()
                if item is None:
                    return
                yield item

        return _iter()


def _sse(type_: str, props: dict[str, Any], id_: str) -> ServerSentEvent:
    """Build a `ServerSentEvent` mimicking opencode's data-only frame shape."""
    return ServerSentEvent(
        event="",
        data=json.dumps({"id": id_, "type": type_, "properties": props}),
        id="",
    )


# ---------------------------------------------------------------------------
# Fan-out + per-subscriber delivery
# ---------------------------------------------------------------------------


async def _collect(stream: AsyncIterator[dict], n: int, timeout: float = 2.0) -> list[dict]:
    """Collect up to *n* events from *stream*.

    When ``n == 0``, the caller is asserting that nothing should arrive; we
    drain whatever shows up within ``timeout`` and return it (so the caller
    can assert the list is empty).
    """
    out: list[dict] = []

    async def _go() -> None:
        async for ev in stream:
            out.append(ev)
            if n > 0 and len(out) >= n:
                return

    try:
        await asyncio.wait_for(_go(), timeout=timeout)
    except TimeoutError:
        if n > 0:
            raise
    return out


@pytest.mark.asyncio
async def test_single_subscriber_receives_events() -> None:
    fake = _FakeClient()
    relay = SessionRelay(fake, sid="ses_1")  # type: ignore[arg-type]
    await relay.start()
    try:
        # Subscribe first so the queue is registered before events arrive.
        stream = relay.subscribe()
        for i in range(3):
            fake.feed(_sse("message.part.delta", {"sessionID": "ses_1"}, f"evt_{i}"))
        events = await _collect(stream, 3)
        assert [e["id"] for e in events] == ["evt_0", "evt_1", "evt_2"]
        assert all(e["event"] == "message.part.delta" for e in events)
    finally:
        await relay.stop()


@pytest.mark.asyncio
async def test_multi_subscriber_fanout() -> None:
    fake = _FakeClient()
    relay = SessionRelay(fake, sid="ses_1")  # type: ignore[arg-type]
    await relay.start()
    try:
        s1 = relay.subscribe()
        s2 = relay.subscribe()
        # Give the subscribers a tick to register their queues.
        await asyncio.sleep(0)
        for i in range(3):
            fake.feed(_sse("message.part.delta", {"sessionID": "ses_1"}, f"evt_{i}"))
        out1 = await _collect(s1, 3)
        out2 = await _collect(s2, 3)
        assert [e["id"] for e in out1] == ["evt_0", "evt_1", "evt_2"]
        assert [e["id"] for e in out2] == ["evt_0", "evt_1", "evt_2"]
    finally:
        await relay.stop()


# ---------------------------------------------------------------------------
# Ring buffer replay
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ring_buffer_replay_on_subscribe_with_last_event_id() -> None:
    fake = _FakeClient()
    relay = SessionRelay(fake, sid="ses_1")  # type: ignore[arg-type]
    await relay.start()
    try:
        # Subscribe once to drain the queue into the ring buffer.
        first_sub = relay.subscribe()
        for i in range(1, 11):
            fake.feed(_sse("message.part.delta", {"sessionID": "ses_1"}, f"evt_{i}"))
        await _collect(first_sub, 10)
        # New subscriber asks to resume after "evt_5".
        resumed = relay.subscribe(last_event_id="evt_5")
        replayed = await _collect(resumed, 5)
        assert [e["id"] for e in replayed] == ["evt_6", "evt_7", "evt_8", "evt_9", "evt_10"]
    finally:
        await relay.stop()


@pytest.mark.asyncio
async def test_ring_buffer_wrap_drops_oldest() -> None:
    fake = _FakeClient()
    relay = SessionRelay(fake, sid="ses_1", buffer_size=256)  # type: ignore[arg-type]
    await relay.start()
    try:
        # Drain via a live subscriber so events flow through the pump.
        sink = relay.subscribe()
        for i in range(1, 301):  # 300 events
            fake.feed(_sse("message.part.delta", {"sessionID": "ses_1"}, f"evt_{i:03d}"))
        await _collect(sink, 300)
        # Buffer holds only the last 256: evt_045 → evt_300.
        # Ask a new subscriber to replay everything (no last_event_id).
        replayed = await _collect(relay.subscribe(last_event_id=None), 0, timeout=0.05)
        # last_event_id=None should NOT replay; only forward new events.
        assert replayed == []
        # last_event_id="evt_000" (older than any in buffer) should replay all
        # 256 buffered events PLUS prepend a one-time `gap` warning so the
        # browser can tell the user that some events were dropped.
        resumed = relay.subscribe(last_event_id="evt_000")
        all_replayed = await _collect(resumed, 257)
        assert len(all_replayed) == 257
        # First event is the gap warning.
        assert all_replayed[0]["event"] == "gap"
        assert all_replayed[0]["data"]["last_event_id"] == "evt_000"
        assert all_replayed[0]["data"]["buffer_size"] == 256
        # Then the 256 buffered events in order; oldest must be evt_045
        # (300 - 256 + 1 = 45).
        assert all_replayed[1]["id"] == "evt_045"
        assert all_replayed[-1]["id"] == "evt_300"
    finally:
        await relay.stop()


# ---------------------------------------------------------------------------
# Slow subscriber must not block the others.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slow_subscriber_does_not_stall_others() -> None:
    fake = _FakeClient()
    relay = SessionRelay(fake, sid="ses_1", subscriber_queue_size=2)  # type: ignore[arg-type]
    await relay.start()
    try:
        slow = relay.subscribe()  # we deliberately never read this stream
        fast = relay.subscribe()
        # Give subscribe() a tick to register.
        await asyncio.sleep(0)
        for i in range(5):
            fake.feed(_sse("message.part.delta", {"sessionID": "ses_1"}, f"evt_{i}"))
        # The slow subscriber's queue fills (cap=2) then events get dropped for it.
        # The fast subscriber must still see all 5 events.
        out_fast = await _collect(fast, 5, timeout=2.0)
        assert [e["id"] for e in out_fast] == ["evt_0", "evt_1", "evt_2", "evt_3", "evt_4"]
        # The slow subscriber stream is still alive — close it explicitly.
        _ = slow
    finally:
        await relay.stop()


# ---------------------------------------------------------------------------
# Subscriber cleanup on cancellation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscriber_cleanup_on_cancellation() -> None:
    fake = _FakeClient()
    relay = SessionRelay(fake, sid="ses_1")  # type: ignore[arg-type]
    await relay.start()
    try:
        stream = relay.subscribe()
        # Drive one iteration so the generator's first yield runs and the
        # subscriber registers itself.
        fake.feed(_sse("message.part.delta", {"sessionID": "ses_1"}, "evt_1"))

        async def _consume_one() -> None:
            async for _ in stream:
                return

        await asyncio.wait_for(_consume_one(), timeout=1.0)
        assert relay.subscriber_count() == 1
        # Closing the stream triggers cleanup.
        await stream.aclose()  # type: ignore[attr-defined]
        # Give the event loop a tick to run any GeneratorExit handlers.
        await asyncio.sleep(0)
        assert relay.subscriber_count() == 0
    finally:
        await relay.stop()


# ---------------------------------------------------------------------------
# RelayManager: per-sid relays + shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_relay_manager_creates_one_relay_per_sid() -> None:
    fake = _FakeClient()
    mgr = RelayManager(fake)  # type: ignore[arg-type]
    try:
        r1 = await mgr.get_or_create_relay("ses_a")
        r2 = await mgr.get_or_create_relay("ses_a")
        r3 = await mgr.get_or_create_relay("ses_b")
        assert r1 is r2
        assert r3 is not r1
    finally:
        await mgr.shutdown()


@pytest.mark.asyncio
async def test_relay_manager_drop_relay_stops_pump() -> None:
    fake = _FakeClient()
    mgr = RelayManager(fake)  # type: ignore[arg-type]
    relay = await mgr.get_or_create_relay("ses_a")
    await mgr.drop_relay("ses_a")
    # Pump task no longer running.
    assert not relay.is_running()


# ---------------------------------------------------------------------------
# H1 boundary row: provider_unauthenticated pass-through
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_error_event_passes_through_relay() -> None:
    """Boundary row H1: unknown error event types (e.g. provider_unauthenticated)
    must NOT be dropped by the relay — the relay is dumb on purpose.

    This test uses ``provider_unauthenticated`` as a representative unknown
    error event to verify end-to-end pass-through from upstream → relay →
    downstream subscriber.  The relay is expected to forward it with the
    event type and payload intact so the browser can surface the error inline.
    """
    fake = _FakeClient()
    relay = SessionRelay(fake, sid="ses_1")  # type: ignore[arg-type]
    await relay.start()
    try:
        stream = relay.subscribe()
        # Feed one known event followed by the unknown error type.
        fake.feed(_sse("session.idle", {"sessionID": "ses_1"}, "evt_before"))
        fake.feed(
            _sse(
                "provider_unauthenticated",
                {
                    "sessionID": "ses_1",
                    "provider": "anthropic",
                    "message": "API key not set",
                },
                "evt_unauthenticated",
            )
        )
        events = await _collect(stream, 2)
        ids = [e["id"] for e in events]
        assert "evt_before" in ids
        assert "evt_unauthenticated" in ids, (
            "provider_unauthenticated event must not be dropped by the relay"
        )
        unauthenticated_event = next(e for e in events if e["id"] == "evt_unauthenticated")
        assert unauthenticated_event["event"] == "provider_unauthenticated"
        assert unauthenticated_event["data"]["properties"]["provider"] == "anthropic"
        assert unauthenticated_event["data"]["properties"]["message"] == "API key not set"
    finally:
        await relay.stop()
