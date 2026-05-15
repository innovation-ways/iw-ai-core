"""End-to-end integration tests for ``permission.asked`` → reply forwarding.

These tests cover the second half of AC2: when the agent (fake upstream)
emits a synthetic ``permission.asked`` event, the dashboard surfaces it on
the SSE stream; the browser POSTs an approval/deny via
``POST /api/chat/sessions/{sid}/permissions/{rid}``; the dashboard router
forwards that to the upstream via ``OpencodeClient.reply_permission``,
which we observe on the fake server's recorded-POST log.

Semantic-correctness commitment (I003 lesson): every assertion below
inspects the actual *payload* the fake server received — not just that
"some POST happened". The deny test additionally asserts the fake
server emits a downstream ``permission.replied`` event carrying the
``deny`` verdict, and that the dashboard stream forwards it untouched.

Test shape note
---------------
We push events → wait briefly → POST reply via dashboard → push the
follow-up ``permission.replied`` → ``drop_relay`` → then read the full
captured SSE body. Polling ``body_parts`` mid-flight is unreliable
because ``ASGITransport`` buffers chunks until either enough bytes are
emitted or the stream closes; the close-then-read pattern is reliable.
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


async def _wait_for_post(fake: FakeOpencodeServer, path: str, *, timeout: float = 5.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if fake.control.posts_matching_path(path):
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"Fake server never received POST to {path}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_permission_asked_event_renders_and_reply_forwards(
    db_session: Session,
) -> None:
    """A ``permission.asked`` event reaches the browser; the reply is forwarded upstream."""
    with fake_opencode_server() as fake:
        app, client, relay_manager = await _build_chat_app(fake, db_session)
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                resp = await http.post("/api/chat/sessions", json={})
                sid = resp.json()["session_id"]

                rid = "perm_req_abc"
                body_parts: list[str] = []

                async def _consume() -> None:
                    async with http.stream(
                        "GET", f"/api/chat/sessions/{sid}/stream", timeout=20.0
                    ) as resp:
                        async for chunk in resp.aiter_text():
                            body_parts.append(chunk)

                consumer = asyncio.create_task(_consume())
                await fake.control.await_stream(0, timeout=5.0)

                # Push permission.asked.
                fake.control.push_event_to(
                    0,
                    event_id="evt_perm_1",
                    event_type="permission.asked",
                    properties={
                        "sessionID": sid,
                        "requestID": rid,
                        "tool": "bash",
                        "args": {"cmd": "ls dashboard/routers"},
                    },
                )

                # Let the event flow upstream → relay → dashboard SSE.
                await asyncio.sleep(0.3)

                # POST the approval through the dashboard router.
                resp = await http.post(
                    f"/api/chat/sessions/{sid}/permissions/{rid}",
                    json={"response": "allow", "remember": False},
                )
                assert resp.status_code == 204, resp.text

                # Verify the dashboard forwarded the reply to the fake server.
                target_path = f"/session/{sid}/permissions/{rid}"
                await _wait_for_post(fake, target_path, timeout=5.0)
                reply_posts = fake.control.posts_matching_path(target_path)
                assert len(reply_posts) == 1, (
                    f"Expected exactly one POST to {target_path}, "
                    f"got {len(reply_posts)} (all paths: "
                    f"{[p.path for p in fake.control.received_posts()]})"
                )
                # SEMANTIC-CORRECTNESS: assert the actual reply payload.
                assert reply_posts[0].body == {"response": "allow", "remember": False}

                # Close the stream and read the captured body.
                await relay_manager.drop_relay(sid)
                await asyncio.wait_for(consumer, timeout=5.0)

                parsed = _parse_sse("".join(body_parts))
                permission_events = [e for e in parsed if e.get("event") == "permission.asked"]
                assert len(permission_events) == 1, (
                    f"Expected one permission.asked event in body, got: "
                    f"{[e.get('event') for e in parsed]}"
                )
                # The rid and tool name are part of the event payload —
                # this is what the approval modal renders.
                payload_data = permission_events[0]["data"]
                assert rid in payload_data, (
                    f"rid {rid!r} missing from permission.asked payload: {payload_data!r}"
                )
                assert "bash" in payload_data
                # The event id we pushed is preserved end-to-end.
                assert permission_events[0].get("id") == "evt_perm_1"
        finally:
            await relay_manager.shutdown()
            await client.aclose()
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_permission_deny_blocks_tool(db_session: Session) -> None:
    """A deny reply is forwarded upstream; a follow-up permission.replied flows back."""
    with fake_opencode_server() as fake:
        app, client, relay_manager = await _build_chat_app(fake, db_session)
        transport = ASGITransport(app=app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                resp = await http.post("/api/chat/sessions", json={})
                sid = resp.json()["session_id"]

                rid = "perm_req_deny"
                body_parts: list[str] = []

                async def _consume() -> None:
                    async with http.stream(
                        "GET", f"/api/chat/sessions/{sid}/stream", timeout=20.0
                    ) as resp:
                        async for chunk in resp.aiter_text():
                            body_parts.append(chunk)

                consumer = asyncio.create_task(_consume())
                await fake.control.await_stream(0, timeout=5.0)

                # Push the ask.
                fake.control.push_event_to(
                    0,
                    event_id="evt_p_ask",
                    event_type="permission.asked",
                    properties={
                        "sessionID": sid,
                        "requestID": rid,
                        "tool": "edit",
                    },
                )
                await asyncio.sleep(0.3)

                # Deny via the dashboard.
                resp = await http.post(
                    f"/api/chat/sessions/{sid}/permissions/{rid}",
                    json={"response": "deny"},
                )
                assert resp.status_code == 204

                target_path = f"/session/{sid}/permissions/{rid}"
                await _wait_for_post(fake, target_path, timeout=5.0)
                reply_posts = fake.control.posts_matching_path(target_path)
                assert len(reply_posts) == 1
                # SEMANTIC-CORRECTNESS: deny verdict is forwarded verbatim,
                # remember defaults to False.
                assert reply_posts[0].body == {"response": "deny", "remember": False}

                # Simulate the upstream emitting permission.replied AFTER
                # receiving the deny.
                fake.control.push_event_to(
                    0,
                    event_id="evt_p_replied",
                    event_type="permission.replied",
                    properties={
                        "sessionID": sid,
                        "requestID": rid,
                        "reply": "deny",
                    },
                )
                await asyncio.sleep(0.3)

                await relay_manager.drop_relay(sid)
                await asyncio.wait_for(consumer, timeout=5.0)

                parsed = _parse_sse("".join(body_parts))
                event_types = [e.get("event") for e in parsed]
                assert "permission.asked" in event_types, (
                    f"permission.asked missing from stream: {event_types}"
                )
                assert "permission.replied" in event_types, (
                    f"permission.replied missing from stream: {event_types}"
                )

                replied = next(e for e in parsed if e.get("event") == "permission.replied")
                # The deny verdict survives the round-trip into the
                # dashboard SSE wire.
                assert "deny" in replied["data"], (
                    f"deny verdict missing from replied payload: {replied!r}"
                )
                assert rid in replied["data"]
                assert replied.get("id") == "evt_p_replied"
        finally:
            await relay_manager.shutdown()
            await client.aclose()
            app.dependency_overrides.clear()
