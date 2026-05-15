"""Unit tests for `orch.chat.opencode_client.OpencodeClient`.

Tests are TDD-RED — written and run BEFORE `orch.chat.opencode_client` exists.
We use `respx` to assert exact request shapes (path, method, JSON body,
auth header) against an in-memory router.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
import pytest
import respx

from orch.chat.opencode_client import OpencodeClient

BASE_URL = "http://127.0.0.1:4099"
PASSWORD = "test-password-32-bytes-or-thereabouts"  # noqa: S105 — test fixture, not real


def _expected_basic_auth_header(user: str = "opencode", password: str = PASSWORD) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_session_request_shape() -> None:
    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/session").respond(
            json={"id": "ses_abc", "title": "New session", "version": "1.14.50"}
        )

        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            sid = await client.create_session(
                model="anthropic/claude-3-5-sonnet",
                agent="build",
                directory="/repo",
            )
        finally:
            await client.aclose()

        assert sid == "ses_abc"
        assert route.called
        assert route.call_count == 1
        req = route.calls.last.request
        assert req.method == "POST"
        body = json.loads(req.content.decode())
        assert body == {
            "model": "anthropic/claude-3-5-sonnet",
            "agent": "build",
            "directory": "/repo",
        }
        assert req.headers["Authorization"] == _expected_basic_auth_header()


@pytest.mark.asyncio
async def test_create_session_omits_none_keys() -> None:
    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/session").respond(json={"id": "ses_q"})
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            await client.create_session()
        finally:
            await client.aclose()
        body = json.loads(route.calls.last.request.content.decode())
        # No `model`/`agent`/`directory` keys when caller passed nothing.
        assert body == {}


# ---------------------------------------------------------------------------
# list / get / messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions_request_shape() -> None:
    async with respx.mock(base_url=BASE_URL) as mock:
        sessions = [{"id": "ses_1"}, {"id": "ses_2"}]
        route = mock.get("/session").respond(json=sessions)
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            out = await client.list_sessions()
        finally:
            await client.aclose()
        assert out == sessions
        assert route.called
        assert route.calls.last.request.headers["Authorization"] == _expected_basic_auth_header()


@pytest.mark.asyncio
async def test_get_session_request_shape() -> None:
    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/session/ses_1").respond(json={"id": "ses_1", "title": "Hi"})
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            out = await client.get_session("ses_1")
        finally:
            await client.aclose()
        assert out == {"id": "ses_1", "title": "Hi"}
        assert route.called


@pytest.mark.asyncio
async def test_get_messages_request_shape() -> None:
    async with respx.mock(base_url=BASE_URL) as mock:
        msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        route = mock.get("/session/ses_1/messages").respond(json=msgs)
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            out = await client.get_messages("ses_1")
        finally:
            await client.aclose()
        assert out == msgs
        assert route.called


# ---------------------------------------------------------------------------
# prompt / abort / reply_permission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_request_shape() -> None:
    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/session/ses_1/prompt_async").respond(json={"ok": True})
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            await client.prompt(
                "ses_1",
                "hello agent",
                model="anthropic/claude-3-5",
                system="be terse",
            )
        finally:
            await client.aclose()
        assert route.called
        body = json.loads(route.calls.last.request.content.decode())
        # The wire shape mirrors OpenCode's expected parts-array.
        assert body["parts"] == [{"type": "text", "text": "hello agent"}]
        assert body["model"] == "anthropic/claude-3-5"
        assert body["system"] == "be terse"


@pytest.mark.asyncio
async def test_prompt_minimal_body() -> None:
    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/session/ses_1/prompt_async").respond(json={"ok": True})
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            await client.prompt("ses_1", "hi")
        finally:
            await client.aclose()
        body = json.loads(route.calls.last.request.content.decode())
        assert body == {"parts": [{"type": "text", "text": "hi"}]}


@pytest.mark.asyncio
async def test_abort_request_shape() -> None:
    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/session/ses_1/abort").respond(json={"ok": True})
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            await client.abort("ses_1")
        finally:
            await client.aclose()
        assert route.called
        # Abort has no body.
        assert route.calls.last.request.content in (b"", b"{}")


@pytest.mark.asyncio
async def test_reply_permission_request_shape() -> None:
    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/session/ses_1/permissions/rid_77").respond(json={"ok": True})
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            await client.reply_permission("ses_1", "rid_77", response="once", remember=True)
        finally:
            await client.aclose()
        assert route.called
        body = json.loads(route.calls.last.request.content.decode())
        assert body == {"response": "once", "remember": True}


@pytest.mark.asyncio
async def test_get_config_request_shape() -> None:
    async with respx.mock(base_url=BASE_URL) as mock:
        cfg = {"models": [], "default_model": "x", "default_agent": "build"}
        route = mock.get("/config").respond(json=cfg)
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            out = await client.get_config()
        finally:
            await client.aclose()
        assert out == cfg
        assert route.called


# ---------------------------------------------------------------------------
# stream_events
# ---------------------------------------------------------------------------


def _sse_body(payloads: list[dict[str, Any]]) -> bytes:
    """Build raw SSE bytes matching opencode's data-only frames."""
    out = []
    for p in payloads:
        out.append(f"data: {json.dumps(p)}\n\n")
    return "".join(out).encode("utf-8")


@pytest.mark.asyncio
async def test_stream_events_yields_server_sent_events() -> None:
    payloads = [
        {"id": "evt_1", "type": "server.connected", "properties": {}},
        {
            "id": "evt_2",
            "type": "message.part.delta",
            "properties": {"sessionID": "s", "delta": "hi"},
        },
    ]
    async with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/event").mock(
            return_value=httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=_sse_body(payloads),
            )
        )
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            seen: list[str] = []
            async for sse in client.stream_events():
                seen.append(sse.data)
                if len(seen) == 2:
                    break
        finally:
            await client.aclose()

    assert len(seen) == 2
    assert json.loads(seen[0])["type"] == "server.connected"
    assert json.loads(seen[1])["type"] == "message.part.delta"


@pytest.mark.asyncio
async def test_stream_events_passes_last_event_id_header() -> None:
    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/event").mock(
            return_value=httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b"data: {}\n\n",
            )
        )
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            # consume nothing — we just need the GET to fire so we can inspect headers
            async for _ in client.stream_events(last_event_id="evt_42"):
                break
        finally:
            await client.aclose()
        assert route.called
        req = route.calls.last.request
        assert req.headers.get("Last-Event-ID") == "evt_42"
        # Without `last_event_id`, the header must be absent.

    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/event").mock(
            return_value=httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b"data: {}\n\n",
            )
        )
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            async for _ in client.stream_events():
                break
        finally:
            await client.aclose()
        assert "Last-Event-ID" not in route.calls.last.request.headers


# ---------------------------------------------------------------------------
# Errors propagate (no swallowing)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_error_propagates() -> None:
    async with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/session").respond(503, json={"error": "down"})
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await client.create_session()
        finally:
            await client.aclose()
