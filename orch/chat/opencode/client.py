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


def _split_provider_model(model: str) -> dict[str, str]:
    """Split a ``"providerId/modelId"`` string into opencode's structured form.

    Opencode's wire format uses ``{providerID, modelID}``. The dashboard
    surfaces a flat ``"providerId/modelId"`` string in its model selector so
    the front-end can treat it as a single value; this helper does the
    translation at the wire boundary.

    Only the first ``/`` is treated as the separator — model IDs that
    themselves contain ``/`` (e.g. ``openai/gpt-5.5/pro``) survive intact.
    Inputs without a ``/`` are sent with an empty ``providerID`` so opencode
    surfaces a clear 400 instead of silently picking a provider.
    """
    provider_id, sep, model_id = model.partition("/")
    if not sep:
        return {"providerID": "", "modelID": model}
    return {"providerID": provider_id, "modelID": model_id}


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
        """Close the underlying httpx.AsyncClient and release connections."""
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
        """Create a new OpenCode session and return its id.

        Args:
            model: Initial model in ``"<providerId>/<modelId>"`` form.
            agent: Agent configuration name to use for the session.
            directory: Working directory for the session.

        Returns:
            The session id string assigned by OpenCode.

        Raises:
            RuntimeError: If the response does not contain a valid id.
        """
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
        """Return all existing OpenCode sessions.

        Returns:
            List of session metadata dicts as returned by GET /session.

        Raises:
            RuntimeError: If the response is not a list.
        """
        resp = await self._client.get("/session")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise RuntimeError(
                f"opencode GET /session returned non-list (got {type(data).__name__})"
            )
        return data

    async def get_session(self, sid: str) -> dict[str, Any]:
        """Return the metadata blob for a single session.

        Args:
            sid: The OpenCode session id to fetch.

        Returns:
            Session metadata dict from GET /session/{sid}.
        """
        resp = await self._client.get(f"/session/{sid}")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    async def get_messages(self, sid: str) -> list[dict[str, Any]]:
        """Return the full message history for a session.

        Args:
            sid: The OpenCode session id.

        Returns:
            List of message dicts from GET /session/{sid}/messages.

        Raises:
            RuntimeError: If the response is not a list.
        """
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
        """Forward a user prompt to OpenCode (kicks off async streaming).

        The ``model`` argument is a ``"<providerId>/<modelId>"`` string (the
        shape exposed by ``/api/chat/config``). Opencode's
        ``/session/{id}/prompt_async`` requires the structured form
        ``{providerID, modelID}`` — the slash split happens here so callers can
        keep using a single string. Only the first ``/`` is treated as the
        separator, so model IDs that themselves contain a ``/`` (e.g.
        ``openai/gpt-5.5/pro``) survive intact.
        """
        body: dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        if model is not None:
            body["model"] = _split_provider_model(model)
        if system is not None:
            body["system"] = system
        resp = await self._client.post(f"/session/{sid}/prompt_async", json=body)
        resp.raise_for_status()

    async def abort(self, sid: str) -> None:
        """Cancel any in-flight completion for a session.

        Args:
            sid: The OpenCode session id to abort.
        """
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
        """Reply to a pending permission request on a session.

        Args:
            sid: The OpenCode session id.
            rid: The permission request id to reply to.
            response: The reply value (e.g. "approve" or "deny").
            remember: When True, OpenCode stores the decision for future similar requests.
        """
        body = {"response": response, "remember": remember}
        resp = await self._client.post(f"/session/{sid}/permissions/{rid}", json=body)
        resp.raise_for_status()

    async def get_config(self) -> dict[str, Any]:
        """Return the runtime's static configuration blob.

        Returns:
            Config dict from GET /config (models, defaults, and other settings).
        """
        resp = await self._client.get("/config")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    async def get_providers(self) -> dict[str, Any]:
        """Fetch ``/config/providers`` — returns ``{providers: [...], default: {...}}``.

        Unlike ``/config``, this endpoint enumerates every configured provider
        and the model catalogue each one exposes. The dashboard merges both
        endpoints to populate the model selector.
        """
        resp = await self._client.get("/config/providers")
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
