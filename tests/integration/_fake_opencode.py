"""In-process fake `opencode serve` for the F-00083 integration tests.

A Starlette app served by a background-thread `uvicorn.Server` on a random
loopback port. Mimics OpenCode's wire protocol just well enough to drive
the dashboard's ``OpencodeClient`` + ``RelayManager`` end-to-end:

* ``POST /session`` → returns ``{"id": "ses_<n>"}``.
* ``GET  /session`` / ``GET /session/{sid}`` / ``GET /session/{sid}/messages``
  → trivial JSON / empty list.
* ``POST /session/{sid}/prompt_async`` → records the POST body.
* ``POST /session/{sid}/abort``         → records the POST.
* ``POST /session/{sid}/permissions/{rid}`` → records the POST.
* ``GET  /config``                       → returns a fixed model list.
* ``GET  /event`` → an SSE stream. Each incoming connection gets its OWN
  per-connection ``queue.Queue``; the test pushes events into a specific
  connection via :meth:`FakeOpencodeControl.push_event_to`.

Why the per-connection queue? Each ``SessionRelay`` opens its OWN upstream
``/event`` connection (see ``relay_manager.SessionRelay._pump``). The
integration tests need to push *distinct* events to each session's relay
so that "concurrent sessions don't interleave" is genuinely observable,
not just an artifact of broadcasting one shared stream.

Thread safety: state mutated from the test thread (main asyncio loop)
and read from the uvicorn thread (server asyncio loop). All shared
collections are guarded by ``threading.Lock``; per-connection queues are
``queue.Queue`` instances which are thread-safe by design. We poll the
queue with short ``asyncio.sleep`` waits rather than block-on-get so the
server loop stays cooperative.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import queue
import socket
import threading
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route


def _pick_free_port() -> int:
    """Return a port number bound momentarily on 127.0.0.1 then released."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass
class ReceivedPost:
    """One inbound POST captured by the fake server."""

    path: str
    body: Any
    sid: str | None = None
    rid: str | None = None


class FakeOpencodeControl:
    """Test-facing handle: push events, inspect inbound POSTs, close streams.

    All mutating helpers are safe to call from the test thread while the
    fake server is running on its own background thread.
    """

    _STREAM_POLL_INTERVAL_S = 0.01

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connection_queues: list[queue.Queue[dict[str, Any] | None]] = []
        self._received_posts: list[ReceivedPost] = []
        self._sessions: dict[str, dict[str, Any]] = {}
        self._messages: dict[str, list[dict[str, Any]]] = {}
        self._next_sid = 1
        # When set, every active /event stream returns immediately.
        self._global_close = threading.Event()

    # ---- session id allocation -------------------------------------------------

    def allocate_session_id(self) -> str:
        with self._lock:
            sid = f"ses_{self._next_sid}"
            self._next_sid += 1
            self._sessions[sid] = {"id": sid}
            self._messages[sid] = []
        return sid

    def known_sessions(self) -> list[str]:
        with self._lock:
            return list(self._sessions.keys())

    def get_session(self, sid: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._sessions.get(sid, {"id": sid, "status": "idle"}))

    def get_messages(self, sid: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._messages.get(sid, []))

    # ---- inbound-POST recording -----------------------------------------------

    def _record_post(self, post: ReceivedPost) -> None:
        with self._lock:
            self._received_posts.append(post)

    def received_posts(self) -> list[ReceivedPost]:
        with self._lock:
            return list(self._received_posts)

    def posts_matching_path(self, path: str) -> list[ReceivedPost]:
        return [p for p in self.received_posts() if p.path == path]

    def posts_starting_with(self, prefix: str) -> list[ReceivedPost]:
        return [p for p in self.received_posts() if p.path.startswith(prefix)]

    # ---- connection-queue management ------------------------------------------

    def _register_stream(self) -> queue.Queue[dict[str, Any] | None]:
        q: queue.Queue[dict[str, Any] | None] = queue.Queue()
        with self._lock:
            self._connection_queues.append(q)
        return q

    def open_stream_count(self) -> int:
        with self._lock:
            return len(self._connection_queues)

    def wait_for_stream(self, index: int, timeout: float = 5.0) -> None:
        """Block until ``index + 1`` upstream /event subscribers exist.

        SYNCHRONOUS: uses ``time.sleep``. Callers in an asyncio context that
        share an event loop with the dashboard relay's pump MUST use
        :meth:`await_stream` instead — otherwise this blocks the loop and the
        relay's pump can never run, leading to a spurious timeout.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.open_stream_count() > index:
                return
            time.sleep(0.01)
        raise TimeoutError(
            f"Fake /event stream #{index} never opened; "
            f"have {self.open_stream_count()} after {timeout}s"
        )

    async def await_stream(self, index: int, timeout: float = 5.0) -> None:
        """Async variant of :meth:`wait_for_stream` — yields to the event loop."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.open_stream_count() > index:
                return
            await asyncio.sleep(0.01)
        raise TimeoutError(
            f"Fake /event stream #{index} never opened; "
            f"have {self.open_stream_count()} after {timeout}s"
        )

    def push_event_to(
        self,
        index: int,
        *,
        event_id: str,
        event_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Push one OpenCode-shape event onto the N-th /event subscriber's queue.

        Pre-condition: the subscriber must already be registered (call
        :meth:`await_stream` from async tests first, or :meth:`wait_for_stream`
        from sync tests).
        """
        if self.open_stream_count() <= index:
            raise RuntimeError(
                f"push_event_to({index}) called before stream {index} was "
                f"registered (have {self.open_stream_count()}). Call "
                f"`await control.await_stream({index})` first."
            )
        event = {
            "id": event_id,
            "type": event_type,
            "properties": properties or {},
        }
        with self._lock:
            q = self._connection_queues[index]
        q.put(event)

    def push_raw_to(self, index: int, payload: dict[str, Any]) -> None:
        """Push a verbatim payload dict (rare; for ill-formed event tests)."""
        if self.open_stream_count() <= index:
            raise RuntimeError(f"push_raw_to({index}) called before stream {index} was registered")
        with self._lock:
            q = self._connection_queues[index]
        q.put(payload)

    def close_stream(self, index: int) -> None:
        """Signal the N-th /event subscriber to terminate cleanly."""
        with self._lock:
            if index >= len(self._connection_queues):
                return
            q = self._connection_queues[index]
        q.put(None)

    def close_all_streams(self) -> None:
        with self._lock:
            qs = list(self._connection_queues)
        for q in qs:
            q.put(None)
        self._global_close.set()


# ---------------------------------------------------------------------------
# Starlette routes
# ---------------------------------------------------------------------------


def _build_app(control: FakeOpencodeControl) -> Starlette:
    async def post_session(request: Request) -> Response:
        body = await _safe_json(request)
        sid = control.allocate_session_id()
        control._record_post(ReceivedPost(path="/session", body=body, sid=sid))
        return JSONResponse({"id": sid, **(body if isinstance(body, dict) else {})})

    async def list_sessions(_request: Request) -> Response:
        return JSONResponse(
            [{"id": sid, "title": f"session {sid}"} for sid in control.known_sessions()]
        )

    async def get_session(request: Request) -> Response:
        sid = request.path_params["sid"]
        return JSONResponse(control.get_session(sid))

    async def get_messages(request: Request) -> Response:
        sid = request.path_params["sid"]
        return JSONResponse(control.get_messages(sid))

    async def post_prompt(request: Request) -> Response:
        sid = request.path_params["sid"]
        body = await _safe_json(request)
        control._record_post(
            ReceivedPost(
                path=f"/session/{sid}/prompt_async",
                body=body,
                sid=sid,
            )
        )
        return JSONResponse({"ok": True})

    async def post_abort(request: Request) -> Response:
        sid = request.path_params["sid"]
        body = await _safe_json(request)
        control._record_post(ReceivedPost(path=f"/session/{sid}/abort", body=body, sid=sid))
        return JSONResponse({"ok": True})

    async def post_permission(request: Request) -> Response:
        sid = request.path_params["sid"]
        rid = request.path_params["rid"]
        body = await _safe_json(request)
        control._record_post(
            ReceivedPost(
                path=f"/session/{sid}/permissions/{rid}",
                body=body,
                sid=sid,
                rid=rid,
            )
        )
        return JSONResponse({"ok": True})

    async def get_config(_request: Request) -> Response:
        return JSONResponse(
            {
                "models": ["fake/model-a", "fake/model-b"],
                "default_model": "fake/model-a",
                "default_agent": "default",
            }
        )

    async def get_event(request: Request) -> Response:
        q = control._register_stream()

        async def gen() -> AsyncIterator[bytes]:
            while True:
                if await request.is_disconnected():
                    return
                if control._global_close.is_set():
                    return
                try:
                    item = q.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(FakeOpencodeControl._STREAM_POLL_INTERVAL_S)
                    continue
                if item is None:
                    return
                # OpenCode's wire shape: data-only frames carrying a JSON
                # payload with `id` and `type` keys inside the body.
                line = "data: " + json.dumps(item) + "\n\n"
                yield line.encode("utf-8")

        return StreamingResponse(gen(), media_type="text/event-stream")

    async def get_global_health(_request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    return Starlette(
        routes=[
            Route("/session", post_session, methods=["POST"]),
            Route("/session", list_sessions, methods=["GET"]),
            Route("/session/{sid}", get_session, methods=["GET"]),
            Route("/session/{sid}/messages", get_messages, methods=["GET"]),
            Route("/session/{sid}/prompt_async", post_prompt, methods=["POST"]),
            Route("/session/{sid}/abort", post_abort, methods=["POST"]),
            Route(
                "/session/{sid}/permissions/{rid}",
                post_permission,
                methods=["POST"],
            ),
            Route("/config", get_config, methods=["GET"]),
            Route("/event", get_event, methods=["GET"]),
            Route("/global/health", get_global_health, methods=["GET"]),
        ]
    )


async def _safe_json(request: Request) -> Any:
    try:
        return await request.json()
    except (json.JSONDecodeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Server lifecycle (uvicorn in a background thread)
# ---------------------------------------------------------------------------


@dataclass
class FakeOpencodeServer:
    """Handle to a running fake OpenCode server."""

    base_url: str
    control: FakeOpencodeControl
    _server: uvicorn.Server
    _thread: threading.Thread
    _stopped: bool = field(default=False)

    def stop(self, timeout: float = 5.0) -> None:
        if self._stopped:
            return
        # Drain any active subscribers so their generators exit.
        self.control.close_all_streams()
        self._server.should_exit = True
        self._thread.join(timeout=timeout)
        self._stopped = True


def start_fake_opencode_server(*, startup_timeout: float = 5.0) -> FakeOpencodeServer:
    """Spawn the fake server on a random loopback port; block until ready."""
    control = FakeOpencodeControl()
    app = _build_app(control)
    port = _pick_free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
        # asyncio policy is irrelevant — uvicorn picks one per thread.
        loop="asyncio",
        lifespan="off",
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(
        target=server.run,
        name=f"fake-opencode-{port}",
        daemon=True,
    )
    thread.start()

    deadline = time.monotonic() + startup_timeout
    while time.monotonic() < deadline:
        if server.started:
            break
        if not thread.is_alive():
            raise RuntimeError("Fake opencode server thread died during startup")
        time.sleep(0.01)
    else:
        with contextlib.suppress(Exception):
            server.should_exit = True
            thread.join(timeout=1.0)
        raise TimeoutError(f"Fake opencode server did not become ready within {startup_timeout}s")

    return FakeOpencodeServer(
        base_url=f"http://127.0.0.1:{port}",
        control=control,
        _server=server,
        _thread=thread,
    )


@contextlib.contextmanager
def fake_opencode_server() -> Iterator[FakeOpencodeServer]:
    """Context manager wrapping ``start_fake_opencode_server`` + clean shutdown."""
    handle = start_fake_opencode_server()
    try:
        yield handle
    finally:
        handle.stop()
