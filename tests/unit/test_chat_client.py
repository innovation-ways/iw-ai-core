"""Unit tests for `orch.chat.opencode.client.OpencodeClient`.

Tests are TDD-RED — written and run BEFORE `orch.chat.opencode.client` exists.
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

from orch.chat.opencode.client import OpencodeClient

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
    """Verifies that create session request shape."""
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
    """Verifies that create session omits none keys."""
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
    """Verifies that list sessions request shape."""
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
    """Verifies that get session request shape."""
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
    """Verifies that get messages request shape."""
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
    """Verifies that prompt request shape."""
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
        # Opencode expects the structured `{providerID, modelID}` form, not
        # the slash-separated string the dashboard surfaces in its selector.
        assert body["model"] == {
            "providerID": "anthropic",
            "modelID": "claude-3-5",
        }
        assert body["system"] == "be terse"


@pytest.mark.asyncio
async def test_prompt_splits_provider_model_into_object() -> None:
    """When ``model`` is a ``"providerId/modelId"`` string the client must
    send it to opencode as ``{"providerID": ..., "modelID": ...}``.

    Regression: opencode 1.15 `/session/{id}/prompt_async` rejects
    ``"model": "<str>"`` with HTTP 400 — the OpenAPI schema requires the
    structured form. See `.opencode/node_modules/@opencode-ai/sdk` for the
    canonical type.
    """
    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/session/sid/prompt_async").respond(204)
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            await client.prompt("sid", "hi", model="minimax/MiniMax-M2.7")
        finally:
            await client.aclose()
        body = json.loads(route.calls.last.request.content.decode())
        assert body["model"] == {
            "providerID": "minimax",
            "modelID": "MiniMax-M2.7",
        }, f"expected object model, got {body['model']!r}"
        # The text part still rides along untouched.
        assert body["parts"] == [{"type": "text", "text": "hi"}]


@pytest.mark.asyncio
async def test_prompt_handles_model_with_slash_in_model_id() -> None:
    """A model ID can contain '/' (rare but valid). Split only the FIRST '/'."""
    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/session/sid/prompt_async").respond(204)
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            await client.prompt("sid", "hi", model="openai/gpt-5.5/pro")
        finally:
            await client.aclose()
        body = json.loads(route.calls.last.request.content.decode())
        assert body["model"] == {
            "providerID": "openai",
            "modelID": "gpt-5.5/pro",
        }


@pytest.mark.asyncio
async def test_prompt_omits_model_when_none() -> None:
    """Calling prompt without a model must NOT include a model field."""
    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/session/sid/prompt_async").respond(204)
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            await client.prompt("sid", "hi", model=None)
        finally:
            await client.aclose()
        body = json.loads(route.calls.last.request.content.decode())
        assert "model" not in body, f"unexpected model field: {body!r}"


@pytest.mark.asyncio
async def test_prompt_minimal_body() -> None:
    """Verifies that prompt minimal body."""
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
    """Verifies that abort request shape."""
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
    """Verifies that reply permission request shape."""
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
    """Verifies that get config request shape."""
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


@pytest.mark.asyncio
async def test_get_providers_request_shape() -> None:
    """`get_providers` GETs /config/providers and returns the raw dict."""
    providers_payload = {
        "providers": [
            {
                "id": "minimax",
                "name": "MiniMax",
                "models": {
                    "MiniMax-M2.7": {"id": "MiniMax-M2.7"},
                    "MiniMax-M2.5": {"id": "MiniMax-M2.5"},
                },
            },
        ],
        "default": {"minimax": "MiniMax-M2.7"},
    }
    async with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/config/providers").respond(json=providers_payload)
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            out = await client.get_providers()
        finally:
            await client.aclose()
        assert out == providers_payload
        assert route.called
        assert route.calls.last.request.headers["Authorization"] == _expected_basic_auth_header()


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
    """Verifies that stream events yields server sent events."""
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
    """Verifies that stream events passes last event id header."""
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
    """Verifies that http error propagates."""
    async with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/session").respond(503, json={"error": "down"})
        client = OpencodeClient(base_url=BASE_URL, password=PASSWORD)
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await client.create_session()
        finally:
            await client.aclose()
