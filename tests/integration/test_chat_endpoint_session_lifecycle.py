"""End-to-end integration tests for the Dashboard AI Assistant — happy path.

Exercises the full pipeline:

    POST /api/chat/sessions            → real OpencodeClient → fake `opencode serve`
    POST /api/chat/sessions/{sid}/prompt
    GET  /api/chat/sessions/{sid}/stream   ← SSE bytes flow back through the
                                             real RelayManager + SessionRelay
    POST /api/chat/sessions/{sid}/abort

The fake server (see ``_fake_opencode.py``) is a real ASGI app served by
``uvicorn`` on a background thread on a random loopback port. The dashboard
relay opens a real TCP/SSE connection to it, so the test exercises the
production wire path — only the upstream binary is replaced.

Per ``tests/CLAUDE.md`` we use the testcontainer ``db_session`` fixture for
DB pinning; the chat endpoints themselves do not touch the DB.
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
from orch.chat.opencode_client import OpencodeClient
from orch.chat.relay_manager import RelayManager
from tests.integration._fake_opencode import FakeOpencodeServer, fake_opencode_server

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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
    """Construct a dashboard app wired to the fake OpenCode + DB session."""
    os.environ["IW_CORE_TEST_CONTEXT"] = "true"
    original_eii = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    if original_eii is not None:
        # tests/conftest.py doesn't clear this; restore on teardown via finalizer
        # (the fixture-level cleanup handles env restoration if needed).
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
    """Parse SSE wire bytes into a list of ``{event, data, id}`` dicts.

    Tolerates the keep-alive comment lines (``": keepalive"``) that the
    dashboard interleaves.
    """
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
            continue  # keep-alive comment
        if ":" in line:
            field, _, value = line.partition(":")
            value = value.lstrip(" ")
            if field in {"event", "data", "id"}:
                current[field] = current.get(field, "") + value
    if current:
        events.append(current)
    return events


async def _read_until_relay_drops(
    http: AsyncClient,
    sid: str,
    relay_manager: RelayManager,
    fake: FakeOpencodeServer,
    *,
    push_then_drop: Any,
) -> list[dict[str, str]]:
    """Open SSE stream, run a coroutine that pushes events + drops relay, return parsed events."""
    body_parts: list[str] = []

    async def _consume() -> None:
        async with http.stream("GET", f"/api/chat/sessions/{sid}/stream", timeout=20.0) as resp:
            assert resp.status_code == 200
            async for chunk in resp.aiter_text():
                body_parts.append(chunk)

    consumer = asyncio.create_task(_consume())
    # Allow the relay's upstream pump to connect to the fake server.
    # Use the ASYNC waiter so the test loop yields while polling — otherwise
    # the consumer task never gets a chance to issue the SSE request.
    await fake.control.await_stream(0, timeout=5.0)
    try:
        await push_then_drop()
    finally:
        # Ensure the consumer exits even if push_then_drop didn't trigger close.
        if not consumer.done():
            await relay_manager.drop_relay(sid)
        await asyncio.wait_for(consumer, timeout=5.0)
    return _parse_sse("".join(body_parts))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_lifecycle_create_prompt_stream_abort(
    db_session: Session,
) -> None:
    """AC2 happy path: create → prompt → stream 3+ events → abort cleanly."""
    with fake_opencode_server() as fake:
        app, client, relay_manager = await _build_chat_app(fake, db_session)
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                # ---- create session ----
                resp = await http.post("/api/chat/sessions", json={})
                assert resp.status_code == 200, resp.text
                sid = resp.json()["session_id"]
                assert sid.startswith("ses_")
                # The fake server logs this as an inbound POST.
                create_posts = fake.control.posts_matching_path("/session")
                assert len(create_posts) == 1

                # ---- send prompt ----
                resp = await http.post(
                    f"/api/chat/sessions/{sid}/prompt",
                    json={"text": "list files in dashboard/routers"},
                )
                assert resp.status_code == 204
                # Fake server received the prompt forward.
                prompt_posts = fake.control.posts_matching_path(f"/session/{sid}/prompt_async")
                assert len(prompt_posts) == 1
                assert prompt_posts[0].body is not None
                # OpencodeClient wraps the text in a `parts` array.
                assert prompt_posts[0].body["parts"][0]["text"] == (
                    "list files in dashboard/routers"
                )

                # ---- open stream, push 3 events, drop relay ----
                async def push_then_drop() -> None:
                    fake.control.push_event_to(
                        0,
                        event_id="evt_001",
                        event_type="message.part.delta",
                        properties={"sessionID": sid, "delta": "Sure, "},
                    )
                    fake.control.push_event_to(
                        0,
                        event_id="evt_002",
                        event_type="message.part.delta",
                        properties={"sessionID": sid, "delta": "here you go."},
                    )
                    fake.control.push_event_to(
                        0,
                        event_id="evt_003",
                        event_type="session.idle",
                        properties={"sessionID": sid},
                    )
                    # Let the events flow through the pump → relay → SSE.
                    await asyncio.sleep(0.3)
                    await relay_manager.drop_relay(sid)

                events = await _read_until_relay_drops(
                    http, sid, relay_manager, fake, push_then_drop=push_then_drop
                )

                # Assert: at least the three pushed events appear, in order,
                # with the correct ids and types.
                event_ids = [e.get("id") for e in events if e.get("id")]
                assert "evt_001" in event_ids
                assert "evt_002" in event_ids
                assert "evt_003" in event_ids
                # Strict ordering (evt_001 before evt_002 before evt_003).
                assert event_ids.index("evt_001") < event_ids.index("evt_002")
                assert event_ids.index("evt_002") < event_ids.index("evt_003")

                # Event-type lines exist for each.
                event_types = [e.get("event") for e in events]
                assert "message.part.delta" in event_types
                assert "session.idle" in event_types

                # Payload survives JSON round-trip — the `delta` text is in
                # the rendered data line for evt_001.
                evt1 = next(e for e in events if e.get("id") == "evt_001")
                assert "Sure," in evt1["data"]

                # ---- abort ----
                resp = await http.post(f"/api/chat/sessions/{sid}/abort")
                assert resp.status_code == 204
                abort_posts = fake.control.posts_matching_path(f"/session/{sid}/abort")
                assert len(abort_posts) == 1
        finally:
            await relay_manager.shutdown()
            await client.aclose()
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_concurrent_sessions_independent_streams(db_session: Session) -> None:
    """AC3: two sessions, two streams, events don't bleed across sessions.

    Each ``SessionRelay`` opens its own upstream ``/event`` connection (see
    ``relay_manager._pump``). The fake server tags each connection with its
    own event queue, so pushing to queue #0 only reaches the relay for
    session A, and queue #1 only reaches the relay for session B.
    """
    with fake_opencode_server() as fake:
        app, client, relay_manager = await _build_chat_app(fake, db_session)
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                resp_a = await http.post("/api/chat/sessions", json={})
                resp_b = await http.post("/api/chat/sessions", json={})
                sid_a = resp_a.json()["session_id"]
                sid_b = resp_b.json()["session_id"]
                assert sid_a != sid_b

                body_a: list[str] = []
                body_b: list[str] = []

                async def consume_a() -> None:
                    async with http.stream(
                        "GET", f"/api/chat/sessions/{sid_a}/stream", timeout=20.0
                    ) as resp:
                        async for chunk in resp.aiter_text():
                            body_a.append(chunk)

                async def consume_b() -> None:
                    async with http.stream(
                        "GET", f"/api/chat/sessions/{sid_b}/stream", timeout=20.0
                    ) as resp:
                        async for chunk in resp.aiter_text():
                            body_b.append(chunk)

                task_a = asyncio.create_task(consume_a())
                # Pin the upstream-connection ordering: open A's stream
                # first, wait for its pump to register, THEN open B's.
                await fake.control.await_stream(0, timeout=5.0)
                task_b = asyncio.create_task(consume_b())
                await fake.control.await_stream(1, timeout=5.0)

                # Push 3 events to A's queue and 3 to B's queue, distinct ids.
                fake.control.push_event_to(
                    0,
                    event_id="A_evt_1",
                    event_type="message.part.delta",
                    properties={"sessionID": sid_a, "delta": "alpha"},
                )
                fake.control.push_event_to(
                    1,
                    event_id="B_evt_1",
                    event_type="message.part.delta",
                    properties={"sessionID": sid_b, "delta": "beta"},
                )
                fake.control.push_event_to(
                    0,
                    event_id="A_evt_2",
                    event_type="session.idle",
                    properties={"sessionID": sid_a},
                )
                fake.control.push_event_to(
                    1,
                    event_id="B_evt_2",
                    event_type="session.idle",
                    properties={"sessionID": sid_b},
                )

                await asyncio.sleep(0.4)
                await relay_manager.drop_relay(sid_a)
                await relay_manager.drop_relay(sid_b)

                await asyncio.wait_for(task_a, timeout=5.0)
                await asyncio.wait_for(task_b, timeout=5.0)

                events_a = _parse_sse("".join(body_a))
                events_b = _parse_sse("".join(body_b))

                ids_a = [e.get("id") for e in events_a if e.get("id")]
                ids_b = [e.get("id") for e in events_b if e.get("id")]

                # Session A sees ONLY its own events; B sees ONLY its own.
                assert "A_evt_1" in ids_a
                assert "A_evt_2" in ids_a
                assert "B_evt_1" not in ids_a, f"B's events leaked into A's stream: {ids_a}"
                assert "B_evt_2" not in ids_a

                assert "B_evt_1" in ids_b
                assert "B_evt_2" in ids_b
                assert "A_evt_1" not in ids_b, f"A's events leaked into B's stream: {ids_b}"
                assert "A_evt_2" not in ids_b
        finally:
            await relay_manager.shutdown()
            await client.aclose()
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_session_error_event_surfaces_to_sse_stream(db_session: Session) -> None:
    """Boundary row H1: ``session.error`` (and unknown error types like
    ``provider_unauthenticated``) must flow from the fake upstream through the
    relay and appear in the dashboard SSE stream intact.

    This test covers the scenario: "User selects a model the provider doesn't
    authenticate" — OpenCode would emit a ``session.error`` (and potentially a
    provider-specific event) that the dashboard must surface to the browser.

    The relay's pass-through of unknown event types is covered at the unit
    level by ``test_unknown_error_event_passes_through_relay``; this test
    adds integration-level coverage that the router + SSE generator also
    forwards error events end-to-end without transforming or dropping them.
    """
    with fake_opencode_server() as fake:
        app, client, relay_manager = await _build_chat_app(fake, db_session)
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                resp = await http.post("/api/chat/sessions", json={})
                assert resp.status_code == 200, resp.text
                sid = resp.json()["session_id"]

                async def push_error_events_then_drop() -> None:
                    # Emit a session.error event (what OpenCode likely emits
                    # when the provider is unauthenticated).
                    fake.control.push_event_to(
                        0,
                        event_id="err_001",
                        event_type="session.error",
                        properties={
                            "sessionID": sid,
                            "error": "provider not authenticated",
                            "provider": "anthropic",
                        },
                    )
                    # Also emit a hypothetical provider-specific event to
                    # verify unknown types also pass through at the wire level.
                    fake.control.push_event_to(
                        0,
                        event_id="err_002",
                        event_type="provider_unauthenticated",
                        properties={
                            "sessionID": sid,
                            "provider": "anthropic",
                            "message": "API key not configured",
                        },
                    )
                    await asyncio.sleep(0.3)
                    await relay_manager.drop_relay(sid)

                events = await _read_until_relay_drops(
                    http,
                    sid,
                    relay_manager,
                    fake,
                    push_then_drop=push_error_events_then_drop,
                )

                # Both error events must appear in the SSE stream.
                event_map = {e.get("id"): e for e in events if e.get("id")}
                assert "err_001" in event_map, (
                    f"session.error event missing from stream; got ids: {list(event_map)}"
                )
                assert "err_002" in event_map, (
                    f"provider_unauthenticated event missing from stream (relay must not drop "
                    f"unknown error event types); got ids: {list(event_map)}"
                )
                # Verify the event type labels survive end-to-end.
                assert event_map["err_001"].get("event") == "session.error"
                assert event_map["err_002"].get("event") == "provider_unauthenticated"
                # Verify payload contents survive JSON round-trip.
                assert "anthropic" in event_map["err_001"]["data"]
                assert "anthropic" in event_map["err_002"]["data"]
        finally:
            await relay_manager.shutdown()
            await client.aclose()
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_session_forwards_directory_to_opencode(
    db_session: Session,
) -> None:
    """CR-00057: when the frontend sends ``directory`` on session creation,
    the dashboard must forward it verbatim to opencode's ``POST /session``.

    The directory scopes the OpenCode session to the project's repo root so
    the assistant operates against the correct working tree.
    """
    project_dir = "/srv/projects/iw-ai-core"
    with fake_opencode_server() as fake:
        app, client, relay_manager = await _build_chat_app(fake, db_session)
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                resp = await http.post(
                    "/api/chat/sessions",
                    json={"directory": project_dir},
                )
                assert resp.status_code == 200, resp.text

                create_posts = fake.control.posts_matching_path("/session")
                assert len(create_posts) == 1
                body = create_posts[0].body
                assert isinstance(body, dict), f"expected JSON body, got {body!r}"
                assert body.get("directory") == project_dir, (
                    f"directory not forwarded to opencode; got body={body!r}"
                )

                # Sanity: when the frontend OMITS directory (e.g. on /system/*
                # pages), it must NOT be sent — opencode treats absent vs empty
                # very differently and we want strict fail-open semantics.
                resp_no_dir = await http.post("/api/chat/sessions", json={})
                assert resp_no_dir.status_code == 200, resp_no_dir.text
                create_posts = fake.control.posts_matching_path("/session")
                assert len(create_posts) == 2
                body_no_dir = create_posts[1].body
                assert isinstance(body_no_dir, dict)
                assert "directory" not in body_no_dir, (
                    f"directory key leaked when client sent none; body={body_no_dir!r}"
                )
        finally:
            await relay_manager.shutdown()
            await client.aclose()
            app.dependency_overrides.clear()
