"""Per-subprocess JSONL channel for Pi RPC protocol (F-00087).

``PiRpcClient`` owns one ``pi --mode rpc`` subprocess instance.  It
exposes:

* ``send_command(cmd)`` — JSON-encodes and writes to stdin.
* ``events()`` — async generator yielding parsed event dicts from stdout
  via the LF-only :func:`aiter_jsonl_lines` reader (R-00072 §2).
* ``request_response(cmd)`` — sends a command and waits for the
  matching ``{"type":"response"}`` reply (in order, since Pi RPC is
  strictly sequential).
* ``reply_extension_ui(request_id, value)`` — writes an
  ``extension_ui_response`` to stdin (approval flow).
* ``close()`` — graceful SIGTERM → SIGKILL shutdown (idempotent).

Process management: ``asyncio.create_subprocess_exec`` with
``start_new_session=True`` puts the Pi subprocess in its own process
group, but ``close()`` currently sends SIGTERM/SIGKILL to the leader
only (not the group).  Any orphaned grandchildren are left for the OS
to clean up — a process-group reaper is tracked as a follow-up
(F-00087 §Out of Scope: "Crash-recovery reaper for orphaned
subprocesses").

References: R-00072 §2, F-00087 §2.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any

from orch.chat.pi.pi_jsonl_reader import aiter_jsonl_lines

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

logger = logging.getLogger(__name__)

_GRACE_SECONDS = 5.0
_RESPONSE_TIMEOUT = 30.0


class PiRpcClient:
    """JSONL RPC channel to a single ``pi --mode rpc`` subprocess."""

    def __init__(
        self,
        *,
        session_dir: Path,
        env: dict[str, str] | None = None,
        binary: str = "pi",
        cwd: Path | str | None = None,
    ) -> None:
        self._session_dir = session_dir
        self._env = env
        self._binary = binary
        # When set, the Pi subprocess is spawned with this as its working
        # directory so the extension reads ``.opencode/opencode.json`` from
        # the project repo (not the dashboard's cwd).  See F-00087 AC3.
        self._cwd = cwd

        self._proc: asyncio.subprocess.Process | None = None
        self._pump_task: asyncio.Task[None] | None = None
        self._closed = False
        self._last_activity: float = time.monotonic()

        # Fan-out: all active ``events()`` iterators share one queue each.
        # We keep a list of queues; the pump puts into each.
        self._event_queues: list[asyncio.Queue[dict[str, Any] | None]] = []

        # Sequential request_response correlation: each call pushes a Future
        # onto this queue; the pump resolves them in order when it sees a
        # ``{"type":"response"}`` event.
        self._response_futures: asyncio.Queue[asyncio.Future[dict[str, Any]]] = asyncio.Queue()

        # stdin write lock — ensures commands are written atomically.
        self._write_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Spawn ``pi --mode rpc --session-dir <dir>`` subprocess."""
        env = dict(os.environ)
        if self._env:
            env.update(self._env)

        self._session_dir.mkdir(parents=True, exist_ok=True)

        logger.debug("Starting pi RPC subprocess session_dir=%s", self._session_dir)
        self._proc = await asyncio.create_subprocess_exec(
            self._binary,
            "--mode",
            "rpc",
            "--session-dir",
            str(self._session_dir),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(self._cwd) if self._cwd else None,
            start_new_session=True,
        )
        self._closed = False
        self._pump_task = asyncio.create_task(self._pump_events(), name="pi-rpc-pump")

    async def close(self) -> None:
        """Graceful shutdown: abort → close stdin → SIGTERM → SIGKILL (idempotent)."""
        if self._closed:
            return
        self._closed = True

        # Ask the agent to abort any in-flight work first.
        with contextlib.suppress(Exception):
            await self.send_command({"type": "abort"})

        # Close stdin so the subprocess knows we're done.
        proc = self._proc
        if proc is not None and proc.stdin is not None:
            with contextlib.suppress(Exception):
                proc.stdin.close()

        # Stop the pump task.
        if self._pump_task is not None and not self._pump_task.done():
            self._pump_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, BaseException):
                await self._pump_task
            self._pump_task = None

        if proc is not None and proc.returncode is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
            else:
                try:
                    await asyncio.wait_for(proc.wait(), timeout=_GRACE_SECONDS)
                except TimeoutError:
                    logger.warning(
                        "Pi subprocess did not exit within %.1fs of SIGTERM; SIGKILL",
                        _GRACE_SECONDS,
                    )
                    with contextlib.suppress(ProcessLookupError):
                        proc.kill()
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(proc.wait(), timeout=_GRACE_SECONDS)

        # Wake any waiting event consumers so they terminate.
        for q in self._event_queues:
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(None)

        # Resolve any pending request_response futures with an error.
        while not self._response_futures.empty():
            try:
                fut = self._response_futures.get_nowait()
                if not fut.done():
                    fut.set_exception(RuntimeError("Pi RPC client closed before response received"))
            except asyncio.QueueEmpty:
                break

    # ------------------------------------------------------------------
    # Command / event API
    # ------------------------------------------------------------------

    async def send_command(self, cmd: dict[str, Any]) -> None:
        """JSON-encode and write ``\\n``-terminated command to subprocess stdin."""
        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdin.is_closing():
            if self._closed:
                return  # Silently ignore post-close writes (boundary behavior).
            raise RuntimeError("Pi RPC client not started or stdin unavailable")
        line = json.dumps(cmd).encode() + b"\n"
        async with self._write_lock:
            proc.stdin.write(line)
            try:
                await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                if self._closed:
                    return
                raise
        self._last_activity = time.monotonic()

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """Async generator — yields normalised Pi RPC event dicts.

        Backed by the internal pump task; multiple concurrent callers each
        get their own queue so they all see every event independently.
        """
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=512)
        self._event_queues.append(queue)
        try:
            while True:
                item = await queue.get()
                if item is None:
                    return
                yield item
        finally:
            with contextlib.suppress(ValueError):
                self._event_queues.remove(queue)

    async def request_response(
        self,
        cmd: dict[str, Any],
        *,
        timeout: float = _RESPONSE_TIMEOUT,
    ) -> dict[str, Any]:
        """Send a command and wait for the matching ``{"type":"response"}`` reply.

        Pi RPC echoes ``{"type":"response","ok":bool}`` after each command
        in strict send order (R-00072 §2).  Correlation is positional (FIFO).
        """
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        await self._response_futures.put(fut)
        await self.send_command(cmd)
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except TimeoutError:
            raise TimeoutError(
                f"Pi RPC: no response for command {cmd.get('type')!r} within {timeout}s"
            ) from None

    async def reply_extension_ui(self, request_id: str, value: Any) -> None:
        """Write an ``extension_ui_response`` to subprocess stdin."""
        await self.send_command(
            {
                "type": "extension_ui_response",
                "id": request_id,
                "value": value,
            }
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def last_activity(self) -> float:
        """Monotonic timestamp of the last send or received event."""
        return self._last_activity

    # ------------------------------------------------------------------
    # Internal pump
    # ------------------------------------------------------------------

    async def _pump_events(self) -> None:
        """Read JSONL from stdout; dispatch to event queues + response futures."""
        proc = self._proc
        if proc is None or proc.stdout is None:
            return

        try:
            async for raw in aiter_jsonl_lines(proc.stdout):
                self._last_activity = time.monotonic()
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Pi RPC: invalid JSON from subprocess: %r", raw[:200])
                    continue

                event_type = event.get("type")

                # Resolve pending request_response future if this is a response.
                if event_type == "response" and not self._response_futures.empty():
                    try:
                        fut = self._response_futures.get_nowait()
                        if not fut.done():
                            fut.set_result(event)
                    except asyncio.QueueEmpty:
                        pass
                    # Responses are internal protocol messages — also fan-out to
                    # event consumers so they can observe them if needed.

                # Fan-out to all active event() consumers.
                for q in list(self._event_queues):
                    try:
                        q.put_nowait(event)
                    except asyncio.QueueFull:
                        logger.warning(
                            "Pi RPC event consumer queue full; dropping event type=%s",
                            event_type,
                        )

        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            if not self._closed:
                logger.error("Pi RPC pump error: %s", exc)
        finally:
            # Signal all event consumers that the stream has ended.
            for q in list(self._event_queues):
                with contextlib.suppress(asyncio.QueueFull):
                    q.put_nowait(None)
