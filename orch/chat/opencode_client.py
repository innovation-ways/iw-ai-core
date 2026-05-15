"""HTTP+SSE client for the managed `opencode serve` runtime.

Owns the wire protocol: request shapes, Basic auth, and the long-lived
`/event` SSE stream. The relay (see `relay_manager.py`) consumes
`stream_events()` and fans the events out to subscribers.

Errors propagate (the relay catches and retries). The client does NOT
log or swallow HTTP errors — `response.raise_for_status()` is called on
every JSON endpoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from httpx_sse import aconnect_sse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx_sse import ServerSentEvent

_DEFAULT_USERNAME = "opencode"


class OpencodeClient:
    """Thin async wrapper around `opencode serve`'s HTTP+SSE API.

    One client owns one `httpx.AsyncClient`; call `aclose()` when done.
    Auth is HTTP Basic with a per-runtime-startup password (S01-generated).
    """

    def __init__(
        self,
        base_url: str,
        password: str,
        *,
        username: str = _DEFAULT_USERNAME,
        timeout: httpx.Timeout | float | None = 30.0,
    ) -> None:
        self._base_url = base_url
        self._auth = httpx.BasicAuth(username, password)
        # The SSE stream is long-lived; per-request timeout=None for /event,
        # while JSON endpoints inherit this default.
        self._client = httpx.AsyncClient(
            base_url=base_url,
            auth=self._auth,
            timeout=timeout,
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def create_session(
        self,
        *,
        model: str | None = None,
        agent: str | None = None,
        directory: str | None = None,
    ) -> str:
        body: dict[str, Any] = {}
        if model is not None:
            body["model"] = model
        if agent is not None:
            body["agent"] = agent
        if directory is not None:
            body["directory"] = directory
        resp = await self._client.post("/session", json=body)
        resp.raise_for_status()
        data = resp.json()
        sid = data.get("id")
        if not isinstance(sid, str):
            raise RuntimeError(f"opencode /session did not return an id (got {data!r})")
        return sid

    async def list_sessions(self) -> list[dict[str, Any]]:
        resp = await self._client.get("/session")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise RuntimeError(
                f"opencode GET /session returned non-list (got {type(data).__name__})"
            )
        return data

    async def get_session(self, sid: str) -> dict[str, Any]:
        resp = await self._client.get(f"/session/{sid}")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    async def get_messages(self, sid: str) -> list[dict[str, Any]]:
        resp = await self._client.get(f"/session/{sid}/messages")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise RuntimeError(
                f"opencode GET /session/{sid}/messages returned non-list "
                f"(got {type(data).__name__})"
            )
        return data

    # ------------------------------------------------------------------
    # Prompting / control
    # ------------------------------------------------------------------

    async def prompt(
        self,
        sid: str,
        text: str,
        *,
        model: str | None = None,
        system: str | None = None,
    ) -> None:
        """Forward a user prompt to OpenCode (kicks off async streaming)."""
        body: dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        if model is not None:
            body["model"] = model
        if system is not None:
            body["system"] = system
        resp = await self._client.post(f"/session/{sid}/prompt_async", json=body)
        resp.raise_for_status()

    async def abort(self, sid: str) -> None:
        resp = await self._client.post(f"/session/{sid}/abort")
        resp.raise_for_status()

    async def reply_permission(
        self,
        sid: str,
        rid: str,
        response: str,
        *,
        remember: bool = False,
    ) -> None:
        body = {"response": response, "remember": remember}
        resp = await self._client.post(f"/session/{sid}/permissions/{rid}", json=body)
        resp.raise_for_status()

    async def get_config(self) -> dict[str, Any]:
        resp = await self._client.get("/config")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    # ------------------------------------------------------------------
    # SSE event stream
    # ------------------------------------------------------------------

    async def stream_events(
        self,
        *,
        last_event_id: str | None = None,
    ) -> AsyncIterator[ServerSentEvent]:
        """Yield raw SSE frames from `GET /event`.

        When `last_event_id` is provided, the `Last-Event-ID` header is
        attached so the relay (and ultimately the browser) can resume after
        a network blip.

        The relay normalises the frames via `filters.normalise`; this method
        is intentionally dumb.
        """
        headers: dict[str, str] = {}
        if last_event_id is not None:
            headers["Last-Event-ID"] = last_event_id

        # `aconnect_sse` opens the request with `stream=True` and parses
        # frames as they arrive. Timeout=None because the stream is
        # long-lived; the relay's watchdog handles staleness.
        async with aconnect_sse(
            self._client,
            "GET",
            "/event",
            headers=headers,
            timeout=None,
        ) as event_source:
            async for sse in event_source.aiter_sse():
                yield sse
