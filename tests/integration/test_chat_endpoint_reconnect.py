"""End-to-end integration tests for tab-refresh reconnect (AC6).

Covers two ring-buffer scenarios:

* :func:`test_reconnect_replays_buffered_events_via_last_event_id` — buffer
  has events 1–10, browser reconnects with ``Last-Event-ID: evt_005``,
  receives ONLY events 6–10 (semantic-strict assertion on the exact ids).

* :func:`test_reconnect_past_ring_buffer_emits_gap_warning` — buffer caps
  at 256, the relay has seen 300 events (so ids 1–44 have aged out),
  browser reconnects with ``Last-Event-ID: evt_001`` (well below the
  buffer floor). The dashboard emits a one-time ``gap`` warning frame
  followed by the most-recent 256 buffered events.

The "gap" warning is part of the design's *Boundary Behavior* row:

  > If the requested id has already aged out of the buffer, replay
  > everything in the buffer and emit a one-time ``event: gap`` warning.

If this contract regresses (e.g., the relay reverts to silent replay),
the second test fails on a specific assertion — not just a soft "didn't
crash".

These tests interact with private relay state (``relay._buffer``) to make
the buffer-fill condition deterministic without the flakiness of "sleep
for N ms and hope". That probe is intentional: it's the test's anchor
to the relay's internal contract, and a regression in the buffer's
``maxlen`` would surface here.

Adapted from F-00083 (pre-tab surface) to F-00086 (tab-scoped surface):
- POST /api/chat/sessions → POST /api/chat/tabs
- /api/chat/sessions/{sid}/... → /api/chat/tabs/{tab_id}/...
- relay_manager.get_or_create_relay(sid) → get_or_create_relay(tab_id)
- relay_manager.drop_relay(sid) → drop_relay(tab_id)
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.chat.opencode.client import OpencodeClient
from orch.chat.opencode.relay_manager import RelayManager
from tests.integration._fake_opencode import FakeOpencodeServer, fake_opencode_server

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _healthy_runtime_mock() -> Any:
    rt = MagicMock()
    rt.health = AsyncMock(return_value=True)
    return rt


async def _build_chat_app(
    fake: FakeOpencodeServer,
    db_session: Session,
) -> tuple[Any, OpencodeClient, RelayManager]:
    os.environ["IW_CORE_TEST_CONTEXT"] = "true"
    os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    app = create_app()
    client = OpencodeClient(base_url=fake.base_url, password="test-password")  # noqa: S106
    relay_manager = RelayManager(client)
    app.state.opencode_runtime = _healthy_runtime_mock()
    app.state.opencode_client = client
    app.state.relay_manager = relay_manager
    app.dependency_overrides[get_db] = lambda: db_session
    return app, client, relay_manager


def _parse_sse(body: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in body.split("\n"):
        line = raw_line.rstrip("\r")
        if line == "":
            if current:
                events.append(current)
                current = {}
            continue
        if line.startswith(":"):
            continue
        if ":" in line:
            field, _, value = line.partition(":")
            value = value.lstrip(" ")
            if field in {"event", "data", "id"}:
                current[field] = current.get(field, "") + value
    if current:
        events.append(current)
    return events


async def _wait_until(predicate: Any, *, timeout: float = 10.0, interval: float = 0.02) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(interval)
    raise AssertionError("Timed out waiting for predicate")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconnect_replays_buffered_events_via_last_event_id(
    db_session: Session,
    test_project: Project,
) -> None:
    """AC6: reconnect with ``Last-Event-ID`` replays only the newer buffered events.

    Adapted: POST /api/chat/sessions → POST /api/chat/tabs. The relay is
    keyed by tab_id; get_or_create_relay and drop_relay use tab_id.
    """
    with fake_opencode_server() as fake:
        app, client, relay_manager = await _build_chat_app(fake, db_session)
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                resp = await http.post(
                    "/api/chat/tabs",
                    json={"project_id": test_project.id},
                )
                assert resp.status_code == 201, resp.text
                tab = resp.json()["tab"]
                tab_id = tab["id"]
                sid = tab["opencode_session_id"]

                # Start the relay's pump up-front so events flow into its
                # buffer without needing a first browser subscriber. This
                # mirrors what would happen in real life: the relay pump
                # is started by the first reader; subsequent reconnects
                # find the relay (and buffer) already alive.
                relay = await relay_manager.get_or_create_relay(tab_id)
                await fake.control.await_stream(0, timeout=5.0)

                # Push 10 events with deterministic ids.
                for i in range(1, 11):
                    fake.control.push_event_to(
                        0,
                        event_id=f"evt_{i:03d}",
                        event_type="message.part.delta",
                        properties={"sessionID": sid, "delta": f"chunk-{i}"},
                    )

                # Wait for the pump to have ingested all 10 into the buffer.
                await _wait_until(lambda: len(relay._buffer) >= 10, timeout=5.0)
                assert len(relay._buffer) == 10
                assert [e["id"] for e in relay._buffer] == [f"evt_{i:03d}" for i in range(1, 11)]

                # Now the "reconnect": open a stream with Last-Event-ID:
                # evt_005 — the relay should replay evt_006 .. evt_010.
                body_parts: list[str] = []

                async def _consume() -> None:
                    async with http.stream(
                        "GET",
                        f"/api/chat/tabs/{tab_id}/stream",
                        timeout=20.0,
                        headers={"Last-Event-ID": "evt_005"},
                    ) as resp:
                        async for chunk in resp.aiter_text():
                            body_parts.append(chunk)

                consumer = asyncio.create_task(_consume())
                # Let the replay drain through the SSE generator.
                await asyncio.sleep(0.3)
                await relay_manager.drop_relay(tab_id)
                await asyncio.wait_for(consumer, timeout=5.0)

                parsed = _parse_sse("".join(body_parts))
                replayed_ids = [e.get("id") for e in parsed if e.get("id")]

                # SEMANTIC-CORRECTNESS: ONLY events 6–10 are replayed.
                # Events 1–5 must NOT appear — they were before
                # Last-Event-ID.
                assert replayed_ids == [
                    "evt_006",
                    "evt_007",
                    "evt_008",
                    "evt_009",
                    "evt_010",
                ], (
                    f"Reconnect with Last-Event-ID=evt_005 should replay only "
                    f"evt_006..evt_010, got: {replayed_ids}"
                )

                # And the event types are preserved end-to-end.
                event_types = [e.get("event") for e in parsed]
                assert all(et == "message.part.delta" for et in event_types if et)
        finally:
            await relay_manager.shutdown()
            await client.aclose()
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_reconnect_past_ring_buffer_emits_gap_warning(
    db_session: Session,
    test_project: Project,
) -> None:
    """AC6 / Boundary Behavior: aged-out Last-Event-ID triggers a one-time gap warning.

    Adapted: POST /api/chat/sessions → POST /api/chat/tabs. Relay keyed by tab_id.
    """
    with fake_opencode_server() as fake:
        app, client, relay_manager = await _build_chat_app(fake, db_session)
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                resp = await http.post(
                    "/api/chat/tabs",
                    json={"project_id": test_project.id},
                )
                assert resp.status_code == 201, resp.text
                tab = resp.json()["tab"]
                tab_id = tab["id"]
                sid = tab["opencode_session_id"]

                relay = await relay_manager.get_or_create_relay(tab_id)
                await fake.control.await_stream(0, timeout=5.0)

                # Push 300 events. Buffer maxlen=256, so events 1–44 age
                # out; the buffer holds evt_045 .. evt_300.
                for i in range(1, 301):
                    fake.control.push_event_to(
                        0,
                        event_id=f"evt_{i:03d}",
                        event_type="message.part.delta",
                        properties={"sessionID": sid},
                    )

                await _wait_until(
                    lambda: len(relay._buffer) == 256 and relay._buffer[-1].get("id") == "evt_300",
                    timeout=15.0,
                    interval=0.05,
                )
                # Verify buffer floor: oldest surviving event is evt_045.
                assert relay._buffer[0].get("id") == "evt_045"
                assert relay._buffer[-1].get("id") == "evt_300"

                # Reconnect with Last-Event-ID: evt_001 (aged out).
                body_parts: list[str] = []

                async def _consume() -> None:
                    async with http.stream(
                        "GET",
                        f"/api/chat/tabs/{tab_id}/stream",
                        timeout=20.0,
                        headers={"Last-Event-ID": "evt_001"},
                    ) as resp:
                        async for chunk in resp.aiter_text():
                            body_parts.append(chunk)

                consumer = asyncio.create_task(_consume())
                # 256 events take some time to stream through SSE wire.
                await asyncio.sleep(0.6)
                await relay_manager.drop_relay(tab_id)
                await asyncio.wait_for(consumer, timeout=10.0)

                parsed = _parse_sse("".join(body_parts))

                # SEMANTIC-CORRECTNESS: first event in the replay is the
                # gap warning carrying the aged-out id.
                assert len(parsed) >= 1
                assert parsed[0].get("event") == "gap", (
                    f"First event must be 'gap' (aged-out reconnect), got: {parsed[0]!r}"
                )
                gap_data = parsed[0].get("data", "")
                assert "evt_001" in gap_data, (
                    f"Gap payload must reference the aged-out id 'evt_001', got: {gap_data!r}"
                )
                assert "last_event_id_aged_out" in gap_data, (
                    f"Gap payload must include the reason, got: {gap_data!r}"
                )

                # The next 256 events are the buffer contents in order:
                # evt_045 .. evt_300.
                replayed = [e for e in parsed[1:] if e.get("id")]
                replayed_ids = [e["id"] for e in replayed]
                assert len(replayed_ids) == 256, (
                    f"Expected 256 buffered events after gap, got "
                    f"{len(replayed_ids)}: first={replayed_ids[:3]!r} "
                    f"last={replayed_ids[-3:]!r}"
                )
                assert replayed_ids[0] == "evt_045"
                assert replayed_ids[-1] == "evt_300"

                # The gap event is emitted EXACTLY ONCE — the buffered
                # events must NOT contain a second gap frame.
                gap_count = sum(1 for e in parsed if e.get("event") == "gap")
                assert gap_count == 1, f"Expected exactly one 'gap' event, got {gap_count}"
        finally:
            await relay_manager.shutdown()
            await client.aclose()
            app.dependency_overrides.clear()
