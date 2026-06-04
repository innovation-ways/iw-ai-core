"""PiRuntime — ChatRuntime implementation for Pi RPC subprocess pool (F-00087).

``PiRuntime`` manages a pool of ``PiRpcClient`` instances (one per chat tab),
bounded by ``MAX_PI_TABS`` with LRU eviction and a 15-minute idle reaper.

Key design decisions:
* **Lazy spawn** — ``create_session()`` assigns a UUID but does NOT start a
  subprocess.  The subprocess is started on the first ``prompt()`` or
  ``subscribe()`` call via ``_get_or_spawn_client()``.
* **LRU eviction** — when ``_get_or_spawn_client`` would push the active
  subprocess count over ``MAX_PI_TABS``, the client with the oldest
  ``last_activity`` is closed.  The session metadata (``pi_session_path``)
  is retained so the evicted session can be resumed later.
* **Idle reaper** — a background task runs every 60 s and closes any client
  whose ``last_activity`` is older than ``IDLE_TIMEOUT_SECONDS``.
* **Pi binary not found** — ``health()`` uses ``shutil.which``; no subprocess
  is spawned until a session is created.

References: F-00087 §4, R-00072 §2.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import time
import uuid
from typing import TYPE_CHECKING, Any

from orch.chat.pi.event_normalizer import normalize_pi_event
from orch.chat.pi.pi_rpc_client import PiRpcClient
from orch.chat.runtime_base import ChatRuntime

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

logger = logging.getLogger(__name__)

# Configurable via environment variables.
MAX_PI_TABS: int = int(os.environ.get("IW_CORE_MAX_PI_TABS", "6"))
IDLE_TIMEOUT_SECONDS: int = int(os.environ.get("IW_CORE_PI_IDLE_TIMEOUT", "900"))

_REAPER_INTERVAL_SECONDS: float = 60.0


class PiRuntime(ChatRuntime):
    """ChatRuntime backed by a pool of ``pi --mode rpc`` subprocesses.

    One ``PiRpcClient`` per tab; at most ``MAX_PI_TABS`` active subprocesses
    (LRU eviction policy).
    """

    def __init__(
        self,
        *,
        base_session_dir: Path | None = None,
        env: dict[str, str] | None = None,
        binary: str = "pi",
    ) -> None:
        from pathlib import Path

        self._base_session_dir: Path = base_session_dir or (
            Path.home() / ".pi" / "agent" / "sessions"
        )
        self._env = env
        self._binary = binary

        # tab_id → PiRpcClient (only active/started clients live here)
        self._clients: dict[str, PiRpcClient] = {}

        # tab_id → {last_activity, pi_session_path}
        # Preserved even after eviction so we can respawn with --session.
        self._client_tab_meta: dict[str, dict[str, Any]] = {}

        # Start the idle reaper background task.
        self._reaper_task: asyncio.Task[None] | None = None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._reaper_task = asyncio.create_task(
                    self._idle_reaper_loop(), name="pi-idle-reaper"
                )
        except RuntimeError:
            # No running event loop at construction time (sync context / tests).
            pass

    # ------------------------------------------------------------------
    # ChatRuntime ABC implementation
    # ------------------------------------------------------------------

    async def health(self) -> bool:
        """True iff the ``pi`` binary is on PATH. No subprocess spawned."""
        return bool(shutil.which(self._binary))

    async def create_session(
        self,
        *,
        model: str | None = None,
        agent: str | None = None,
        directory: str | None = None,
    ) -> str:
        """Assign a fresh UUID session id. Subprocess is NOT spawned yet (lazy)."""
        session_id = str(uuid.uuid4())
        # Initialise metadata; subprocess path will be filled in on first spawn.
        self._client_tab_meta[session_id] = {
            "last_activity": time.monotonic(),
            "pi_session_path": None,
            "model": model,
            "agent": agent,
            "directory": directory,
        }
        logger.debug("PiRuntime.create_session -> %s (lazy)", session_id)
        return session_id

    async def get_session(self, session_id: str) -> dict[str, Any]:
        """Return stored metadata for a Pi session.

        Args:
            session_id: The session UUID assigned by create_session.

        Returns:
            Dict with ``id`` and ``pi_session_path`` (may be None if subprocess
            has not been spawned yet).
        """
        meta = self._client_tab_meta.get(session_id, {})
        return {
            "id": session_id,
            "pi_session_path": meta.get("pi_session_path"),
        }

    async def list_sessions(self) -> list[dict[str, Any]]:
        """Scan base_session_dir for .jsonl session files."""
        results: list[dict[str, Any]] = []
        if not self._base_session_dir.exists():
            return results
        try:
            for p in sorted(self._base_session_dir.rglob("*.jsonl")):
                results.append({"pi_session_path": str(p), "name": p.stem})
        except OSError as exc:
            logger.warning("PiRuntime.list_sessions: scan error: %s", exc)
        return results

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Request message history from the Pi subprocess."""
        client = self._clients.get(session_id)
        if client is None:
            return []
        try:
            resp = await client.request_response({"type": "get_messages"})
            messages = resp.get("messages", [])
            return list(messages) if isinstance(messages, list) else []
        except Exception as exc:  # noqa: BLE001
            logger.warning("PiRuntime.get_messages(%s): %s", session_id, exc)
            return []

    async def prompt(
        self,
        session_id: str,
        text: str,
        *,
        model: str | None = None,
        system: str | None = None,
    ) -> None:
        """Send a prompt to the Pi subprocess. Spawns lazily on first call."""
        if not await self.health():
            raise RuntimeError("pi binary not found on PATH")

        client = await self._get_or_spawn_client(session_id)

        # If a different model is requested, set it first.
        if model is not None:
            meta = self._client_tab_meta.get(session_id, {})
            if meta.get("model") != model:
                await client.send_command({"type": "set_model", "model": model})
                meta["model"] = model

        cmd: dict[str, Any] = {"type": "prompt", "message": text}
        if system:
            cmd["system"] = system
        await client.send_command(cmd)
        self._touch_activity(session_id)

    async def abort(self, session_id: str) -> None:
        """Send an abort command to the Pi subprocess for a session.

        Args:
            session_id: The session whose in-flight work should be cancelled.
        """
        client = self._clients.get(session_id)
        if client is not None:
            await client.send_command({"type": "abort"})
            self._touch_activity(session_id)

    async def reply_permission(
        self,
        session_id: str,
        request_id: str,
        response: str,
        *,
        remember: bool = False,  # noqa: ARG002 — reserved for future policy persistence
    ) -> None:
        """Translate "approve"/"deny" → bool and write extension_ui_response to stdin."""
        client = self._clients.get(session_id)
        if client is None:
            logger.warning(
                "reply_permission: no active client for session %s; ignoring", session_id
            )
            return
        value = response.lower() in ("approve", "yes", "true", "1", "allow")
        await client.reply_extension_ui(request_id, value)
        self._touch_activity(session_id)

    async def set_model(self, session_id: str, model: str) -> None:
        """Pin the active model for a session's Pi subprocess.

        Args:
            session_id: The session to update.
            model: Model identifier to pin (forwarded to the subprocess).
        """
        client = self._clients.get(session_id)
        if client is not None:
            await client.send_command({"type": "set_model", "model": model})
            meta = self._client_tab_meta.get(session_id)
            if meta is not None:
                meta["model"] = model
            self._touch_activity(session_id)

    def subscribe(
        self,
        session_id: str,
        *,
        last_event_id: str | None = None,  # noqa: ARG002 — Pi has no ring-buffer replay in v1
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield normalised event dicts from the Pi subprocess for ``session_id``.

        Declared as a regular ``def`` returning an async generator so the
        return type is ``AsyncGenerator`` (a subtype of ``AsyncIterator``),
        satisfying the ABC contract.  See ``ChatRuntime.subscribe`` for the
        LSP rationale.
        """
        return self._subscribe_impl(session_id)

    async def _subscribe_impl(self, session_id: str) -> AsyncIterator[dict[str, Any]]:
        """Internal async generator backing ``subscribe``."""
        if not await self.health():
            raise RuntimeError("pi binary not found on PATH")
        client = await self._get_or_spawn_client(session_id)
        async for raw_event in client.events():
            self._touch_activity(session_id)
            normalised = normalize_pi_event(raw_event)
            if normalised is not None:
                yield normalised

    async def get_config(self) -> dict[str, Any]:
        """Stub — Pi models are fetched from agent_runtime_options in the router."""
        return {}

    async def get_providers(self) -> dict[str, Any]:
        """Stub — Pi providers are fetched from agent_runtime_options in the router."""
        return {}

    async def close_session(self, session_id: str) -> None:
        """Close the subprocess for ``session_id`` (if active)."""
        client = self._clients.pop(session_id, None)
        if client is not None:
            with contextlib.suppress(Exception):
                await client.close()
        # Preserve metadata so the session can be resumed later.

    # ------------------------------------------------------------------
    # Pool helpers
    # ------------------------------------------------------------------

    async def _get_or_spawn_client(self, session_id: str) -> PiRpcClient:
        """Return existing client or spawn a new one (with LRU eviction if needed)."""
        client = self._clients.get(session_id)
        if client is not None:
            self._touch_activity(session_id)
            return client

        # Need to spawn a new client — evict LRU if at cap.
        await self._evict_lru_if_needed()

        meta = self._client_tab_meta.get(session_id, {})
        session_dir = self._base_session_dir / session_id

        pi_session_path = meta.get("pi_session_path")
        # NOTE: resume-by-path (--session <path>) is a v2 follow-up.
        # pi_session_path is retained in metadata for future use.
        _ = pi_session_path  # noqa: F841 — suppress until resume-by-path is implemented

        # Forward ``directory`` (the project repo root passed to
        # ``create_session``) as the subprocess cwd so the Pi extension
        # reads ``.opencode/opencode.json`` from the project, not the
        # dashboard's working directory.  See F-00087 AC3.
        directory = meta.get("directory")
        client = PiRpcClient(
            session_dir=session_dir,
            env=self._env,
            binary=self._binary,
            cwd=directory,
        )
        await client.start()

        self._clients[session_id] = client
        now = time.monotonic()
        if session_id not in self._client_tab_meta:
            self._client_tab_meta[session_id] = {}
        self._client_tab_meta[session_id]["last_activity"] = now

        logger.debug("PiRuntime: spawned client for session %s", session_id)
        return client

    async def _evict_lru_if_needed(self) -> None:
        """If active client count >= MAX_PI_TABS, close the least-recently-used one."""
        if len(self._clients) < MAX_PI_TABS:
            return

        # Find the session with the oldest last_activity.
        lru_sid = min(
            self._clients,
            key=lambda sid: self._client_tab_meta.get(sid, {}).get("last_activity", float("inf")),
        )
        logger.info(
            "PiRuntime: evicting LRU session %s (active=%d, cap=%d)",
            lru_sid,
            len(self._clients),
            MAX_PI_TABS,
        )
        lru_client = self._clients.pop(lru_sid)
        with contextlib.suppress(Exception):
            await lru_client.close()
        # Retain meta so the tab can be resumed later.

    def _touch_activity(self, session_id: str) -> None:
        """Update last_activity for ``session_id`` in both client and meta."""
        now = time.monotonic()
        client = self._clients.get(session_id)
        if client is not None:
            client._last_activity = now  # noqa: SLF001 — direct update for performance
        meta = self._client_tab_meta.get(session_id)
        if meta is not None:
            meta["last_activity"] = now

    # ------------------------------------------------------------------
    # Idle reaper
    # ------------------------------------------------------------------

    async def _idle_reaper_loop(self) -> None:
        """Periodically close clients that have been idle for too long."""
        while True:
            try:
                await asyncio.sleep(_REAPER_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                return

            now = time.monotonic()
            to_evict = [
                sid
                for sid, client in list(self._clients.items())
                if (now - client.last_activity) >= IDLE_TIMEOUT_SECONDS
            ]
            for sid in to_evict:
                logger.info(
                    "PiRuntime idle reaper: closing session %s (idle > %ds)",
                    sid,
                    IDLE_TIMEOUT_SECONDS,
                )
                client = self._clients.pop(sid, None)
                if client is not None:
                    with contextlib.suppress(Exception):
                        await client.close()

    # ------------------------------------------------------------------
    # Bulk shutdown
    # ------------------------------------------------------------------

    async def close_all_clients(self) -> None:
        """Close all active clients. Called by the dashboard lifespan on shutdown."""
        if self._reaper_task is not None and not self._reaper_task.done():
            self._reaper_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, BaseException):
                await self._reaper_task
            self._reaper_task = None

        for client in list(self._clients.values()):
            with contextlib.suppress(Exception):
                await client.close()
        self._clients.clear()
