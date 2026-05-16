"""Deterministic OpenCode API stub for worktree E2E stacks."""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import logging
import os
import secrets
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

logger = logging.getLogger(__name__)

MODEL_ID = "stub/echo"
EVENT_BUFFER_MAX = 256
PERMISSION_TIMEOUT_SECONDS = 10.0


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class SessionState:
    session: dict[str, Any]
    messages: list[dict[str, Any]] = field(default_factory=list)
    current_permission_id: str | None = None
    permission_future: asyncio.Future[str] | None = None
    active_task: asyncio.Task[None] | None = None


class StubState:
    def __init__(self, password: str) -> None:
        self.password = password
        self.sessions: dict[str, SessionState] = {}
        self.session_order: list[str] = []
        self.event_id = 0
        self.events: deque[dict[str, Any]] = deque(maxlen=EVENT_BUFFER_MAX)
        self.subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self.lock = asyncio.Lock()

    async def emit(self, event_name: str, data: dict[str, Any]) -> dict[str, Any]:
        async with self.lock:
            self.event_id += 1
            event = {"id": str(self.event_id), "event": event_name, "data": data}
            self.events.append(event)
            for q in list(self.subscribers):
                q.put_nowait(event)
            return event


def _decode_basic_token(header: str) -> tuple[str, str] | None:
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "basic" or not value:
        return None
    try:
        raw = base64.b64decode(value, validate=True).decode("utf-8")
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return None
    username, sep, password = raw.partition(":")
    if not sep:
        return None
    return username, password


def create_app(password: str) -> FastAPI:
    app = FastAPI(title="e2e-opencode-stub", version="0.1")
    state = StubState(password=password)

    async def require_auth(request: Request) -> None:
        if request.url.path == "/global/health":
            return
        auth = request.headers.get("Authorization")
        creds = _decode_basic_token(auth or "")
        if creds != ("opencode", state.password):
            raise HTTPException(status_code=401, detail="Unauthorized")

    async def emit_message(
        session: SessionState,
        *,
        sid: str,
        status: str,
        text: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "session_id": sid,
            "role": "assistant",
            "status": status,
            "text": text,
        }
        if extra:
            payload.update(extra)
        if session.messages and session.messages[-1].get("role") == "assistant":
            session.messages[-1] = payload
        else:
            session.messages.append(payload)
        await state.emit("message.updated", payload)

    async def _finish_idle(sid: str, payload: dict[str, Any] | None = None) -> None:
        idle_payload = {"session_id": sid}
        if payload:
            idle_payload.update(payload)
        await state.emit("session.idle", idle_payload)

    async def _process_prompt(sid: str, prompt_text: str) -> None:
        session = state.sessions[sid]
        session.messages.append({"session_id": sid, "role": "user", "text": prompt_text})
        await emit_message(session, sid=sid, status="streaming", text="")
        await emit_message(session, sid=sid, status="streaming", text="ok — running ls")

        rid = f"req_{secrets.token_hex(4)}"
        fut: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        session.current_permission_id = rid
        session.permission_future = fut
        await state.emit(
            "permission.asked",
            {
                "session_id": sid,
                "request_id": rid,
                "tool": "bash",
                "command": "ls -la",
            },
        )

        try:
            decision = await asyncio.wait_for(fut, timeout=PERMISSION_TIMEOUT_SECONDS)
        except TimeoutError:
            await _finish_idle(sid, {"permission_timeout": True})
            return
        finally:
            session.current_permission_id = None
            session.permission_future = None

        if decision == "allow":
            await emit_message(
                session,
                sid=sid,
                status="complete",
                text="ok — running ls\nCONTENTS",
            )
            await _finish_idle(sid)
        elif decision == "deny":
            await _finish_idle(sid, {"permission_denied": True})
        elif decision == "abort":
            await _finish_idle(sid, {"aborted": True})

    @app.get("/global/health")
    async def health() -> PlainTextResponse:
        return PlainTextResponse(content="", status_code=200)

    @app.get("/config")
    async def config(request: Request) -> JSONResponse:
        await require_auth(request)
        return JSONResponse(
            {
                "models": [{"id": MODEL_ID, "name": "Stub Echo"}],
                "default_model": MODEL_ID,
                "default_agent": "build",
            }
        )

    @app.post("/session")
    async def create_session(request: Request) -> JSONResponse:
        await require_auth(request)
        body = (
            await request.json()
            if request.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        if not isinstance(body, dict):
            body = {}
        sid = f"ses_{secrets.token_hex(4)}"
        session_dict = {
            "id": sid,
            "created_at": _now_iso(),
            "title": None,
            "model": body.get("model") or MODEL_ID,
            "agent": body.get("agent") or "build",
            "directory": body.get("directory"),
        }
        state.sessions[sid] = SessionState(session=session_dict)
        state.session_order.append(sid)
        return JSONResponse(session_dict)

    @app.get("/session")
    async def list_sessions(request: Request) -> JSONResponse:
        await require_auth(request)
        rows = [state.sessions[sid].session for sid in state.session_order]
        return JSONResponse(rows)

    @app.get("/session/{sid}")
    async def get_session(sid: str, request: Request) -> JSONResponse:
        await require_auth(request)
        session = state.sessions.get(sid)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        return JSONResponse(session.session)

    @app.get("/session/{sid}/messages")
    async def get_messages(sid: str, request: Request) -> JSONResponse:
        await require_auth(request)
        session = state.sessions.get(sid)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        return JSONResponse(session.messages)

    @app.post("/session/{sid}/prompt_async")
    async def prompt_async(sid: str, request: Request) -> JSONResponse:
        await require_auth(request)
        session = state.sessions.get(sid)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        body = await request.json()
        parts = body.get("parts", []) if isinstance(body, dict) else []
        prompt_text = ""
        if isinstance(parts, list) and parts:
            first = parts[0]
            if isinstance(first, dict):
                prompt_text = str(first.get("text", ""))
        if session.active_task is not None and not session.active_task.done():
            session.active_task.cancel()
        session.active_task = asyncio.create_task(_process_prompt(sid, prompt_text))
        return JSONResponse({})

    @app.post("/session/{sid}/abort")
    async def abort(sid: str, request: Request) -> JSONResponse:
        await require_auth(request)
        session = state.sessions.get(sid)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        if session.permission_future is not None and not session.permission_future.done():
            session.permission_future.set_result("abort")
        await _finish_idle(sid, {"aborted": True})
        return JSONResponse({})

    @app.post("/session/{sid}/permissions/{rid}")
    async def permissions(sid: str, rid: str, request: Request) -> JSONResponse:
        await require_auth(request)
        session = state.sessions.get(sid)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        body = await request.json()
        response = body.get("response") if isinstance(body, dict) else None
        if response not in {"allow", "deny"}:
            raise HTTPException(status_code=400, detail="response must be allow|deny")
        if rid == session.current_permission_id:
            if response == "allow":
                await emit_message(
                    session,
                    sid=sid,
                    status="streaming",
                    text="ok — running ls",
                    extra={"tool_continued": True},
                )
            else:
                await emit_message(
                    session,
                    sid=sid,
                    status="streaming",
                    text="ok — running ls",
                    extra={"tool_blocked": True},
                )
            if session.permission_future is not None and not session.permission_future.done():
                session.permission_future.set_result(response)
        return JSONResponse({})

    @app.get("/event")
    async def event_stream(request: Request) -> StreamingResponse:
        await require_auth(request)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        state.subscribers.add(queue)
        last_seen = request.headers.get("Last-Event-ID")

        async def gen() -> Any:
            try:
                if last_seen:
                    try:
                        last_id = int(last_seen)
                    except ValueError:
                        last_id = 0
                    for ev in list(state.events):
                        if int(ev["id"]) > last_id:
                            yield _to_sse(ev)

                while True:
                    ev = await queue.get()
                    yield _to_sse(ev)
            finally:
                state.subscribers.discard(queue)

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


def _to_sse(event: dict[str, Any]) -> str:
    import json

    return f"event: {event['event']}\ndata: {json.dumps(event['data'])}\nid: {event['id']}\n\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opencode")
    parser.add_argument("--selftest", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    serve = subparsers.add_parser("serve")
    serve.add_argument("--hostname", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=4096)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.selftest:
        app = create_app(password=os.environ.get("OPENCODE_SERVER_PASSWORD", "selftest-password"))
        if not hasattr(app, "routes"):
            raise RuntimeError("selftest failed: app has no routes")
        return 0

    if args.command != "serve":
        parser.print_usage(sys.stderr)
        return 2

    password = os.environ.get("OPENCODE_SERVER_PASSWORD")
    if not password:
        raise RuntimeError("OPENCODE_SERVER_PASSWORD must be set")

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logger.info("starting e2e opencode stub on %s:%s", args.hostname, args.port)
    app = create_app(password=password)
    uvicorn.run(app, host=args.hostname, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
