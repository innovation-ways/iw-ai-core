"""Dashboard AI Assistant chat API router (F-00083).

Nine endpoints under /api/chat/ that proxy to a managed ``opencode serve``
subprocess via OpencodeClient and RelayManager (implemented in orch/chat/).

All endpoints return JSON or SSE (no htmx fragments).  The three singletons
(runtime, client, relay_manager) are created in ``dashboard.app._lifespan``
and stored on ``request.app.state``.  Each endpoint reads them via a
lightweight ``Depends`` helper that also enforces the runtime health gate.

SSE shape mirrors ``dashboard/routers/sse.py`` exactly: StreamingResponse with
``Cache-Control: no-cache``, ``X-Accel-Buffering: no``, ``Connection:
keep-alive``, and 30 s keep-alive comments.  Relay events are forwarded as::

    event: <name>\\ndata: <json>\\nid: <event-id>\\n\\n

Context-chip convention
-----------------------
When ``POST /api/chat/sessions/{sid}/prompt`` receives a ``context`` field
``{type, id, title}`` it prepends::

    [Context: viewing {title} ({type} {id})]

to the prompt's first text-part and passes the result as the ``system``
keyword argument to ``OpencodeClient.prompt()``.  This is the only place in
the router where context injection happens — the underlying client method
signature stays clean.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

    from orch.chat.opencode_client import OpencodeClient
    from orch.chat.opencode_runtime import OpencodeRuntime
    from orch.chat.relay_manager import RelayManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat")

# ---------------------------------------------------------------------------
# In-memory caches with TTL
# ---------------------------------------------------------------------------

_CONFIG_TTL = 30.0  # seconds
_SKILLS_TTL = 30.0  # seconds

_config_cache: dict[str, Any] = {}
_skills_cache: dict[str, Any] = {}

# Root used for scanning .opencode/skills/ and .opencode/commands/; patched in
# tests via ``patch.object(chat_mod, "_OPENCODE_ROOT", tmp_path)``.
_OPENCODE_ROOT: Path = Path(
    os.environ.get("IW_CORE_REPO_ROOT", Path(__file__).resolve().parents[3])
)

# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    model: str | None = None
    agent: str | None = None
    directory: str | None = None


class PromptRequest(BaseModel):
    text: str = Field(..., min_length=1)
    model: str | None = None
    context: dict[str, str] | None = None  # {type, id, title}


class PermissionRequest(BaseModel):
    response: str
    remember: bool = False


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _503_unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": "OpenCode runtime unavailable"},
    )


async def _get_runtime(request: Request) -> OpencodeRuntime | None:
    """Return the runtime from app state, or None if unavailable."""
    return getattr(request.app.state, "opencode_runtime", None)


async def _get_client(request: Request) -> OpencodeClient | None:
    """Return the client from app state, or None if unavailable."""
    return getattr(request.app.state, "opencode_client", None)


async def _get_relay_manager(request: Request) -> RelayManager | None:
    """Return the relay manager from app state, or None if unavailable."""
    return getattr(request.app.state, "relay_manager", None)


async def _check_runtime_healthy(
    runtime: OpencodeRuntime | None = Depends(_get_runtime),
) -> bool:
    """Return True when the runtime is present and healthy."""
    if runtime is None:
        return False
    try:
        return await runtime.health()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# SSE generator helper
# ---------------------------------------------------------------------------


async def _relay_sse_generator(
    relay_iter: AsyncIterator[dict[str, Any]],
    request: Request,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted strings from a relay event iterator.

    Mirrors sse.py: keep-alive comment every ~30 s, disconnect check via
    ``request.is_disconnected()``.
    """
    import asyncio

    ping_tick = 0
    try:
        async for ev in relay_iter:
            if await request.is_disconnected():
                break

            name = ev.get("event", "message")
            raw_data = ev.get("data", {})
            ev_id = ev.get("id", "")

            data_str = json.dumps(raw_data) if isinstance(raw_data, dict) else str(raw_data)

            yield f"event: {name}\ndata: {data_str}\nid: {ev_id}\n\n"

            ping_tick += 1
            if ping_tick >= 6:
                yield ": keepalive\n\n"
                ping_tick = 0

            await asyncio.sleep(0)  # cooperative yield
    except Exception as exc:
        logger.error("chat SSE relay error: %s", exc)
        payload = json.dumps({"error": str(exc)})
        yield f"event: relay.error\ndata: {payload}\nid: \n\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/sessions")
async def create_session(
    body: CreateSessionRequest,
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """Create a new OpenCode session. Returns ``{session_id}``."""
    if not healthy or client is None:
        return _503_unavailable()
    sid = await client.create_session(
        model=body.model,
        agent=body.agent,
        directory=body.directory,
    )
    return {"session_id": sid}


@router.get("/sessions")
async def list_sessions(
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """List past sessions from OpenCode (passthrough)."""
    if not healthy or client is None:
        return _503_unavailable()
    return await client.list_sessions()


@router.get("/sessions/{sid}")
async def get_session(
    sid: str,
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """Get session metadata + full message history."""
    if not healthy or client is None:
        return _503_unavailable()
    session = await client.get_session(sid)
    messages = await client.get_messages(sid)
    return {"session": session, "messages": messages}


@router.get("/sessions/{sid}/stream")
async def stream_session(
    sid: str,
    request: Request,
    relay_manager: RelayManager | None = Depends(_get_relay_manager),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """SSE stream relaying events for the given session.

    Respects the ``Last-Event-ID`` request header for ring-buffer replay.
    """
    if not healthy or relay_manager is None:
        return _503_unavailable()

    last_event_id = request.headers.get("Last-Event-ID") or request.query_params.get(
        "last_event_id"
    )
    relay = await relay_manager.get_or_create_relay(sid)
    relay_iter = relay.subscribe(last_event_id=last_event_id)

    return StreamingResponse(
        _relay_sse_generator(relay_iter, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/sessions/{sid}/prompt")
async def send_prompt(
    sid: str,
    body: PromptRequest,
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """Forward a user prompt to OpenCode.

    When ``body.context`` is supplied, prepends a context chip to the
    ``system`` argument::

        [Context: viewing {title} ({type} {id})]
    """
    if not healthy or client is None:
        return _503_unavailable()

    system: str | None = None
    if body.context:
        ctx = body.context
        title = ctx.get("title", "")
        ctype = ctx.get("type", "")
        cid = ctx.get("id", "")
        system = f"[Context: viewing {title} ({ctype} {cid})]"

    await client.prompt(sid, body.text, model=body.model, system=system)
    return Response(status_code=204)


@router.post("/sessions/{sid}/abort")
async def abort_session(
    sid: str,
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """Abort the current in-flight prompt for the given session."""
    if not healthy or client is None:
        return _503_unavailable()
    await client.abort(sid)
    return Response(status_code=204)


@router.post("/sessions/{sid}/permissions/{rid}")
async def reply_permission(
    sid: str,
    rid: str,
    body: PermissionRequest,
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """Reply to a pending ``permission.asked`` event."""
    if not healthy or client is None:
        return _503_unavailable()
    await client.reply_permission(sid, rid, body.response, remember=body.remember)
    return Response(status_code=204)


@router.get("/config")
async def get_config(
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """Return ``{models, default_model, default_agent}`` with 30 s TTL cache.

    Unlike the other endpoints, if a cached value exists it is served even
    when the runtime is temporarily unhealthy.
    """
    now = time.monotonic()
    cached = _config_cache.get("data")
    cached_at = _config_cache.get("at", 0.0)

    if cached is not None and (now - cached_at) < _CONFIG_TTL:
        return cached

    if not healthy or client is None:
        if cached is not None:
            # Serve stale cache rather than 503
            return cached
        return _503_unavailable()

    raw = await client.get_config()
    result = {
        "models": raw.get("models", []),
        "default_model": raw.get("default_model", ""),
        "default_agent": raw.get("default_agent", ""),
    }
    _config_cache["data"] = result
    _config_cache["at"] = now
    return result


@router.get("/skills")
async def get_skills(
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """Return ``[{kind, name, description}]`` from ``.opencode/skills/`` and
    ``.opencode/commands/``. Cached for 30 s; invalidated when any file's
    mtime changes under those directories.
    """
    if not healthy:
        return _503_unavailable()

    now = time.monotonic()
    cached_at = _skills_cache.get("at", 0.0)
    cached_mtime = _skills_cache.get("mtime")

    # Compute the max mtime across all tracked files
    current_mtime = _scan_opencode_mtime()

    if (
        _skills_cache.get("data") is not None
        and (now - cached_at) < _SKILLS_TTL
        and current_mtime == cached_mtime
    ):
        return _skills_cache["data"]

    skills = _load_skills()
    _skills_cache["data"] = skills
    _skills_cache["at"] = now
    _skills_cache["mtime"] = current_mtime
    return skills


# ---------------------------------------------------------------------------
# Skills / commands helpers
# ---------------------------------------------------------------------------


def _scan_opencode_mtime() -> float:
    """Return max mtime across all files in .opencode/skills/ and .opencode/commands/."""
    root = _OPENCODE_ROOT
    max_mtime = 0.0
    for subdir in ("skills", "commands"):
        d = root / ".opencode" / subdir
        if d.is_dir():
            for p in d.rglob("*"):
                if p.is_file():
                    with contextlib.suppress(OSError):
                        mt = p.stat().st_mtime
                        if mt > max_mtime:
                            max_mtime = mt
    return max_mtime


def _load_skills() -> list[dict[str, str]]:
    """Walk .opencode/skills/ and .opencode/commands/ and return skill metadata."""
    root = _OPENCODE_ROOT
    results: list[dict[str, str]] = []

    for kind, subdir in (("skill", "skills"), ("command", "commands")):
        d = root / ".opencode" / subdir
        if not d.is_dir():
            continue
        for skill_dir in sorted(d.iterdir()):
            if not skill_dir.is_dir():
                continue
            name = skill_dir.name
            description = ""
            # Try SKILL.md or <name>.md for a description line
            for candidate in ("SKILL.md", f"{name}.md", "README.md"):
                md = skill_dir / candidate
                if md.is_file():
                    with contextlib.suppress(OSError):
                        description = _extract_description(md.read_text(encoding="utf-8"))
                    break
            results.append({"kind": kind, "name": name, "description": description})

    return results


def _extract_description(content: str) -> str:
    """Extract a brief description from a markdown file.

    Looks for a ``description:`` frontmatter key or the first non-heading
    paragraph.
    """
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("description:"):
            return stripped[len("description:") :].strip()
    # Fallback: first non-empty, non-heading line
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:120]
    return ""
