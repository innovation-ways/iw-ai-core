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

# Per-chunk streaming delay. Real opencode emits one delta per LLM token at
# ~50-100ms per token, so a fast model still leaves several seconds of
# observable streaming for any non-trivial reply. The S16 browser
# verifications (V2 "streaming tokens appear within 10s", V5 "Abort button
# visible while streaming" + multi-tab switch flow) require a non-zero gap
# between chunks; without it the entire reply lands in <50ms and the Abort
# control flickers past too quickly to click.
STREAM_CHUNK_DELAY_S = 0.5

# Long-prompt threshold (chars). Prompts above this length trigger a longer
# reply with more chunks, giving V5 a comfortable abort window — matches
# the "Write a haiku and then explain each line in detail" V5 fixture.
LONG_PROMPT_THRESHOLD = 40

# Reply chunks for short prompts ("hi", "hello"). Total: ~1.6s streaming.
SHORT_REPLY_CHUNKS = ["ok", " — ", "running", " ls"]

# Reply chunks for long prompts. ~60 chunks × 0.5s ≈ 30s of streaming —
# long enough for V5 to switch to Tab B, send a Tab B prompt, wait for
# Tab B's reply to finish, switch back to Tab A, find the still-visible
# Abort button on Tab A, click it, and observe `Run aborted.` Real
# opencode replies to "Write a haiku and explain each line" are easily
# 200+ tokens, so this remains representative of production timing.
LONG_REPLY_CHUNKS = [
    "Sure",
    ", ",
    "let",
    " me",
    " think",
    " about",
    " that",
    " carefully",
    ".",
    " First",
    ",",
    " I'll",
    " sketch",
    " the",
    " three-line",
    " haiku",
    ",",
    " then",
    " walk",
    " through",
    " each",
    " line",
    " with",
    " short",
    " notes",
    " on",
    " imagery",
    ",",
    " rhythm",
    ",",
    " and",
    " meaning",
    ".",
    " The",
    " imagery",
    " grounds",
    " the",
    " abstraction",
    " of",
    " software",
    " engineering",
    " in",
    " a",
    " concrete",
    " seasonal",
    " moment",
    ";",
    " the",
    " rhythm",
    " of",
    " five",
    "-seven",
    "-five",
    " syllables",
    " gives",
    " it",
    " the",
    " traditional",
    " haiku",
    " cadence",
    ".",
]

# CR-00057: the stub advertises a realistic provider catalog so the chat
# allowlist round-trip (projects.toml -> Project.config["ai_assistant"] ->
# /api/chat/config intersection) has something non-trivial to filter
# against. The curated 5 below match `[projects.iw-ai-core.ai_assistant]`
# in projects.toml verbatim — the V1/V2 browser checks expect exactly
# those entries (in that order) after the intersection. The extras (and
# the legacy `stub/echo`) widen the fail-open list so V3 ("many more than
# 5 entries on /system/status") can pass without project_id.
ADVERTISED_PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "anthropic",
        "name": "Anthropic",
        "models": {
            "claude-opus-4-7": {"id": "claude-opus-4-7", "name": "Claude Opus 4.7"},
            "claude-sonnet-4-6": {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6"},
            "claude-haiku-4-5": {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5"},
        },
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "models": {
            "MiniMax-M2.7": {"id": "MiniMax-M2.7", "name": "MiniMax M2.7"},
            "MiniMax-M2.5": {"id": "MiniMax-M2.5", "name": "MiniMax M2.5"},
            "MiniMax-M2": {"id": "MiniMax-M2", "name": "MiniMax M2"},
        },
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "models": {
            "gpt-5.3-codex": {"id": "gpt-5.3-codex", "name": "GPT-5.3 Codex"},
            "gpt-5.2": {"id": "gpt-5.2", "name": "GPT-5.2"},
            "gpt-4o": {"id": "gpt-4o", "name": "GPT-4o"},
        },
    },
    {
        "id": "ollama",
        "name": "Ollama",
        "models": {
            "gemma4:26b": {"id": "gemma4:26b", "name": "Gemma4 26B"},
            "llama4:70b": {"id": "llama4:70b", "name": "Llama4 70B"},
            "qwen3:32b": {"id": "qwen3:32b", "name": "Qwen3 32B"},
        },
    },
    {
        "id": "stub",
        "name": "Stub",
        "models": {"echo": {"id": "echo", "name": "Stub Echo"}},
    },
]
ADVERTISED_DEFAULT = {"anthropic": "claude-opus-4-7"}

# Flat list of "providerId/modelId" strings — used by the legacy /config
# response which exposes a denormalised model array.
ADVERTISED_FLAT: list[dict[str, str]] = [
    {"id": f"{p['id']}/{mid}", "name": entry["name"]}
    for p in ADVERTISED_PROVIDERS
    for mid, entry in p["models"].items()
]


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

    async def emit(self, event_name: str, properties: dict[str, Any]) -> dict[str, Any]:
        # Opencode 1.15 wire shape: the JSON in the SSE `data:` field has
        # `type`, `id`, and `properties` keys. The relay (orch/chat/filters.py
        # :normalise) reads `type` to set the event name and forwards
        # `properties` to the browser via chat.js's `data.properties` accessor.
        async with self.lock:
            self.event_id += 1
            eid = str(self.event_id)
            payload = {"type": event_name, "id": eid, "properties": properties}
            event = {"id": eid, "event": event_name, "data": payload}
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

    def _append_history(
        session: SessionState,
        *,
        message_id: str,
        sid: str,
        role: str,
        text: str,
    ) -> None:
        # Persist in the SDK SessionMessagesResponses shape so the dashboard's
        # GET /api/chat/sessions/{sid} (which proxies opencode's
        # /session/{sid}/messages) yields entries with info+parts that
        # chat.js's _loadHistory expects.
        session.messages.append(
            {
                "info": {
                    "id": message_id,
                    "sessionID": sid,
                    "role": role,
                    "time": {"created": datetime.now(UTC).timestamp()},
                },
                "parts": [{"type": "text", "text": text, "messageID": message_id}],
            }
        )

    async def emit_message_part_updated(
        *,
        message_id: str,
        delta: str,
        accumulated_text: str,
    ) -> None:
        # Opencode 1.15: message.part.updated carries a delta plus a full
        # Part snapshot. chat.js (_handleEvent) prefers `delta` and falls
        # back to `part.text` for the full-snapshot accumulator path.
        await state.emit(
            "message.part.updated",
            {
                "messageID": message_id,
                "delta": delta,
                "part": {
                    "type": "text",
                    "text": accumulated_text,
                    "messageID": message_id,
                },
            },
        )

    async def emit_message_finalised(
        *,
        sid: str,
        message_id: str,
        role: str = "assistant",
        error: Any = None,
    ) -> None:
        # message.updated with info.time.completed signals "stream done" to
        # chat.js — it flips _streaming off and finalises the last bubble.
        info: dict[str, Any] = {
            "id": message_id,
            "sessionID": sid,
            "role": role,
            "time": {
                "created": datetime.now(UTC).timestamp(),
                "completed": datetime.now(UTC).timestamp(),
            },
            "error": error,
        }
        await state.emit("message.updated", {"info": info})

    async def _finish_idle(sid: str, extra: dict[str, Any] | None = None) -> None:
        props: dict[str, Any] = {"sessionID": sid}
        if extra:
            props.update(extra)
        await state.emit("session.idle", props)

    async def _process_prompt(sid: str, prompt_text: str) -> None:
        session = state.sessions[sid]
        # Persist user turn in info+parts shape.
        user_mid = f"msg_{secrets.token_hex(4)}"
        _append_history(session, message_id=user_mid, sid=sid, role="user", text=prompt_text)

        # Stream the assistant reply as a series of delta events so chat.js
        # exercises its accumulation guard, then finalise with message.updated.
        # The stub paces chunks with a real wall-clock delay so the browser
        # verification step can observe streaming-in-progress (V2) and click
        # the per-tab Abort button while still streaming (V5). Without these
        # delays the entire response would land in <50ms and the Abort
        # control would flicker past faster than a UI test can react.
        assistant_mid = f"msg_{secrets.token_hex(4)}"
        reply_chunks = (
            LONG_REPLY_CHUNKS if len(prompt_text) > LONG_PROMPT_THRESHOLD else SHORT_REPLY_CHUNKS
        )
        accumulated = ""
        for i, chunk in enumerate(reply_chunks):
            accumulated += chunk
            await emit_message_part_updated(
                message_id=assistant_mid,
                delta=chunk,
                accumulated_text=accumulated,
            )
            # Skip the delay after the final chunk; the message.updated /
            # session.idle events follow immediately.
            if i < len(reply_chunks) - 1:
                try:
                    await asyncio.sleep(STREAM_CHUNK_DELAY_S)
                except asyncio.CancelledError:
                    # If aborted mid-stream, persist the partial reply and
                    # emit session.idle with aborted=true so chat.js can
                    # render the "Run aborted." indicator (V5 requirement).
                    _append_history(
                        session,
                        message_id=assistant_mid,
                        sid=sid,
                        role="assistant",
                        text=accumulated,
                    )
                    await emit_message_finalised(sid=sid, message_id=assistant_mid)
                    await _finish_idle(sid, extra={"aborted": True})
                    raise

        _append_history(
            session,
            message_id=assistant_mid,
            sid=sid,
            role="assistant",
            text=accumulated,
        )
        await emit_message_finalised(sid=sid, message_id=assistant_mid)
        await _finish_idle(sid)

    @app.get("/global/health")
    async def health() -> PlainTextResponse:
        return PlainTextResponse(content="", status_code=200)

    @app.get("/config")
    async def config(request: Request) -> JSONResponse:
        await require_auth(request)
        return JSONResponse(
            {
                "models": ADVERTISED_FLAT,
                "default_model": MODEL_ID,
                "default_agent": "build",
            }
        )

    @app.get("/config/providers")
    async def config_providers(request: Request) -> JSONResponse:
        # Mirrors the real opencode 1.15 shape consumed by
        # dashboard/routers/chat.py:_flatten_provider_models — providers is a
        # list of {id, models:{modelId:{...}}} (models is a DICT keyed by
        # model id, not a list), and default is a {providerId: modelId}
        # dict the dashboard merges into the model selector.
        await require_auth(request)
        return JSONResponse({"providers": ADVERTISED_PROVIDERS, "default": ADVERTISED_DEFAULT})

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
        # If a prompt stream is in flight, cancel it. _process_prompt's
        # CancelledError handler emits message.updated + a session.idle with
        # aborted=True against the partial reply (V5 browser-verification
        # contract). If no stream is active (e.g. the test path that calls
        # abort AFTER the prompt completes), we still emit one terminal
        # session.idle with aborted=True so callers always see a
        # state-transition event.
        cancelled_active = False
        if session.active_task is not None and not session.active_task.done():
            session.active_task.cancel()
            cancelled_active = True
        if not cancelled_active:
            await _finish_idle(sid, {"aborted": True})
        return JSONResponse({})

    @app.post("/session/{sid}/permissions/{rid}")
    async def permissions(sid: str, rid: str, request: Request) -> JSONResponse:
        # The default prompt flow no longer asks for permission, so this
        # endpoint just acknowledges the reply (and resolves any pending
        # permission future if a future variant of _process_prompt re-enables
        # the permission dance). Kept as a 200-returning route so the
        # dashboard's /api/chat/sessions/{sid}/permissions/{rid} pass-through
        # never sees a 404.
        await require_auth(request)
        session = state.sessions.get(sid)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        body = await request.json()
        response = body.get("response") if isinstance(body, dict) else None
        if response not in {"allow", "deny"}:
            raise HTTPException(status_code=400, detail="response must be allow|deny")
        if (
            rid == session.current_permission_id
            and session.permission_future is not None
            and not session.permission_future.done()
        ):
            session.permission_future.set_result(response)
        await state.emit("permission.replied", {"id": rid, "sessionID": sid, "response": response})
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
