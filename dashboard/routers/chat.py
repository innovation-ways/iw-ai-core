"""Dashboard AI Assistant chat API router (F-00086 tab-scoped rewrite).

Thirteen endpoints under /api/chat/ that implement the tab-scoped surface
introduced by F-00086.  The seven legacy /api/chat/sessions/* endpoints are
removed; the frontend (S07) and tests (S08) migrate in lockstep.

Tab-scoped endpoints (11):
    POST   /api/chat/tabs
    GET    /api/chat/tabs?project_id=X&include_closed=false
    GET    /api/chat/tabs/recent-closed?project_id=X&limit=10
    GET    /api/chat/tabs/{tab_id}
    PATCH  /api/chat/tabs/{tab_id}
    DELETE /api/chat/tabs/{tab_id}
    POST   /api/chat/tabs/{tab_id}/reopen
    GET    /api/chat/tabs/{tab_id}/stream
    POST   /api/chat/tabs/{tab_id}/prompt
    POST   /api/chat/tabs/{tab_id}/abort
    POST   /api/chat/tabs/{tab_id}/permissions/{rid}

Retained endpoints (2):
    GET    /api/chat/config?project_id=X&runtime=opencode
    GET    /api/chat/skills

All endpoints return JSON or SSE (no htmx fragments). The three singletons
(runtime, client, relay_manager) are created in ``dashboard.app._lifespan``
and stored on ``request.app.state``.

SSE shape mirrors ``dashboard/routers/sse.py`` exactly: StreamingResponse with
``Cache-Control: no-cache``, ``X-Accel-Buffering: no``, ``Connection:
keep-alive``, and 30 s keep-alive comments. Relay events are forwarded as::

    event: <name>\\ndata: <json>\\nid: <event-id>\\n\\n

Context-chip convention
-----------------------
When ``POST /api/chat/tabs/{tab_id}/prompt`` receives a ``context`` field
``{type, id, title}`` it prepends::

    [Context: viewing {title} ({type} {id})]

to the prompt's first text-part and passes the result as the ``system``
keyword argument to ``OpencodeClient.prompt()``.

Health-gate
-----------
Endpoints that TOUCH the runtime (create, prompt, abort, permissions, stream,
get-with-messages) 503 when the runtime is unhealthy. Pure DB endpoints
(list, PATCH, DELETE, reopen, recent-closed) serve regardless of runtime
health.

Bootstrap
---------
GET /api/chat/tabs calls ``bootstrap_default_tab`` UNCONDITIONALLY before
returning the list. The helper itself gates on "zero rows for project" and is
a no-op once any row (active OR closed) exists.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from dashboard.dependencies import get_db
from orch.chat import bootstrap_default_tab
from orch.chat import tab_service as _tab_service
from orch.db.models import Project

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

    from sqlalchemy.orm import Session

    from orch.chat.opencode import OpencodeClient, OpencodeRuntime, RelayManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat")

# ---------------------------------------------------------------------------
# In-memory caches with TTL
# ---------------------------------------------------------------------------

_CONFIG_TTL = 30.0  # seconds
_SKILLS_TTL = 30.0  # seconds

_config_cache: dict[str, dict[str, Any]] = {}
_skills_cache: dict[str, Any] = {}

# Repo root used to scan `.opencode/{skills,commands}` and
# `.claude/{skills,commands}`. From this file's location two parents up reaches
# the iw-ai-core repo root (which holds CLAUDE.md). Tests patch via
# ``patch.object(chat_mod, "_OPENCODE_ROOT", tmp_path)``.
_OPENCODE_ROOT: Path = Path(
    os.environ.get("IW_CORE_REPO_ROOT", Path(__file__).resolve().parents[2])
)

# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateTabRequest(BaseModel):
    project_id: str
    runtime: str = "opencode"
    model: str | None = None
    title: str = "New chat"
    agent: str | None = None


class UpdateTabRequest(BaseModel):
    title: str | None = None
    model: str | None = None


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
# Tab serialization helper
# ---------------------------------------------------------------------------


def _tab_to_dict(tab: Any) -> dict[str, Any]:
    """Serialize a ChatTab ORM instance to a JSON-safe dict."""
    return {
        "id": str(tab.id),
        "project_id": tab.project_id,
        "title": tab.title,
        "runtime": tab.runtime,
        "model": tab.model,
        "status": tab.status,
        "opencode_session_id": tab.opencode_session_id,
        "created_at": tab.created_at.isoformat() if tab.created_at else None,
        "updated_at": tab.updated_at.isoformat() if tab.updated_at else None,
        "last_active_at": tab.last_active_at.isoformat() if tab.last_active_at else None,
        "closed_at": tab.closed_at.isoformat() if tab.closed_at else None,
    }


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

            if isinstance(raw_data, dict):
                payload = dict(raw_data)
                tab_id = ev.get("tab_id")
                if tab_id is not None and "tab_id" not in payload:
                    payload["tab_id"] = tab_id
                data_str = json.dumps(payload)
            else:
                data_str = str(raw_data)

            yield f"event: {name}\ndata: {data_str}\nid: {ev_id}\n\n"

            ping_tick += 1
            if ping_tick >= 6:
                yield ": keepalive\n\n"
                ping_tick = 0

            await asyncio.sleep(0)  # cooperative yield
    except Exception as exc:
        logger.error("chat SSE relay error: %s", exc)
        error_payload = json.dumps({"error": str(exc)})
        yield f"event: relay.error\ndata: {error_payload}\nid: \n\n"


# ---------------------------------------------------------------------------
# Tab endpoints
# ---------------------------------------------------------------------------


@router.post("/tabs")
async def create_tab(
    body: CreateTabRequest,
    db: Session = Depends(get_db),
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """Create a new chat tab. Returns ``{tab}`` + optional X-Tab-Soft-Cap-Exceeded header.

    Health-gated: 503 when the runtime is unavailable (a tab without a live
    runtime session would be unresponsive).

    Model validation: if ``model`` is supplied it must appear in the runtime's
    available models list. If omitted, the default model from config is used.

    Runtime allowlist: currently ``{"opencode"}``; attempting ``"pi"`` or any
    other value returns 400.
    """
    # --- runtime allowlist: validate BEFORE any client/health calls ---
    # This runs even before the health gate so unknown runtimes always get 400
    # (not 503) regardless of runtime health (invariant #3, AC6).
    if body.runtime not in _tab_service.ALLOWED_RUNTIMES:
        return JSONResponse(
            status_code=400,
            content={
                "error": (
                    f"runtime '{body.runtime}' not in allowlist "
                    f"{set(_tab_service.ALLOWED_RUNTIMES)!r}"
                )
            },
        )

    if not healthy or client is None:
        return _503_unavailable()

    # --- resolve and validate model ---
    # Fetch config once; cache key is project_id + runtime (no need to re-fetch
    # per field within this request).
    project_key = body.project_id.strip()
    runtime_key = body.runtime.strip()
    cache_key = f"{project_key}:{runtime_key}"
    now = time.monotonic()
    cache_slot = _config_cache.get(cache_key, {})
    cached_config = cache_slot.get("data")
    cached_at = cache_slot.get("at", 0.0)

    if cached_config is None or (now - cached_at) >= _CONFIG_TTL:
        # Fetch fresh config for this runtime.
        raw = await client.get_config()
        providers_raw = await client.get_providers()
        available_models = _flatten_provider_models(providers_raw)

        project = db.get(Project, project_key)
        ai_assistant = project.config.get("ai_assistant") if project is not None else None
        project_directory = project.repo_root if project is not None else ""
        if not isinstance(project_directory, str):
            project_directory = ""

        if not isinstance(ai_assistant, dict):
            filtered_models = available_models
            default_model = _pick_default_model(raw, providers_raw, available_models)
        else:
            allowlist_raw = ai_assistant.get("models")
            allowlist = (
                [m for m in allowlist_raw if isinstance(m, str)]
                if isinstance(allowlist_raw, list)
                else []
            )
            allow_default = ai_assistant.get("default_model")
            available_set = set(available_models)
            filtered_models = [m for m in allowlist if m in available_set]
            if not filtered_models:
                filtered_models = available_models
            default_model = (
                allow_default
                if isinstance(allow_default, str) and allow_default in filtered_models
                else (filtered_models[0] if filtered_models else "")
            )

        cached_config = {
            "models": filtered_models,
            "default_model": default_model,
            "project_directory": project_directory,
        }
        _config_cache[cache_key] = {"data": cached_config, "at": now}

    resolved_model = body.model if body.model is not None else cached_config["default_model"]

    # Validate model against available list (if model was explicitly requested).
    if body.model is not None:
        available = cached_config["models"]
        if resolved_model not in available:
            return JSONResponse(
                status_code=400,
                content={
                    "error": f"model '{resolved_model}' not available for runtime '{body.runtime}'"
                },
            )

    # --- create session via OpenCode ---
    project_directory = cached_config.get("project_directory") or ""
    try:
        session_id = await client.create_session(
            model=resolved_model,
            agent=body.agent,
            directory=project_directory if project_directory else None,
        )
    except Exception as exc:
        logger.error("create_tab: failed to create OpenCode session: %s", exc)
        return _503_unavailable()

    # --- persist tab ---
    try:
        tab, soft_cap_exceeded = _tab_service.create_tab(
            db,
            project_id=body.project_id,
            runtime=body.runtime,
            model=resolved_model,
            title=body.title,
            agent=body.agent,
            opencode_session_id=session_id,
        )
        db.commit()
    except ValueError as exc:
        # Runtime allowlist or other validation error from tab_service.
        return JSONResponse(status_code=400, content={"error": str(exc)})

    headers: dict[str, str] = {}
    if soft_cap_exceeded:
        headers["X-Tab-Soft-Cap-Exceeded"] = "true"

    return JSONResponse(
        status_code=201,
        content={"tab": _tab_to_dict(tab)},
        headers=headers,
    )


@router.get("/tabs/recent-closed")
async def list_recent_closed_tabs(
    project_id: str,
    limit: int = 10,
    db: Session = Depends(get_db),
) -> Any:
    """Return the most recently closed tabs for a project (ordered by closed_at DESC).

    Pure DB endpoint — no runtime health gate.
    """
    tabs = _tab_service.recent_closed_tabs(db, project_id=project_id, limit=limit)
    return {"tabs": [_tab_to_dict(t) for t in tabs]}


@router.get("/tabs")
async def list_tabs(
    project_id: str,
    include_closed: bool = False,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    client: OpencodeClient | None = Depends(_get_client),
) -> Any:
    """Return active tabs ordered by last_active_at DESC.

    UNCONDITIONALLY calls ``bootstrap_default_tab`` before returning the list.
    The helper itself decides whether to fire (it bails when ANY chat_tabs row
    exists, active or closed). This fulfils AC5 without pre-gating on empty
    list or include_closed.
    """
    # Resolve bootstrap dependencies from app state.
    runtime = None
    if request is not None:
        runtime = getattr(request.app.state, "opencode_runtime", None)

    if runtime is not None:
        project = db.get(Project, project_id)
        project_repo_root = project.repo_root if project is not None else None
        if not isinstance(project_repo_root, str):
            project_repo_root = None

        # Resolve default_model: use cached config when fresh, otherwise fetch
        # from the runtime client. The bootstrap path is the first thing a new
        # project hits, so the cache is normally cold here — without the
        # fallback fetch the seeded Default tab gets model="" (regression
        # caught by test_bootstrap_seeds_default_when_chat_tabs_empty).
        default_model = await _resolve_default_model_for_project(
            db, project_id=project_id, client=client
        )

        try:
            await bootstrap_default_tab(
                db,
                project_id=project_id,
                runtime=runtime,
                project_repo_root=project_repo_root,
                default_model=default_model,
            )
            db.commit()
        except Exception as exc:
            logger.warning("bootstrap_default_tab failed (non-fatal): %s", exc)
            db.rollback()

    tabs = _tab_service.list_tabs(db, project_id=project_id, include_closed=include_closed)
    return {"tabs": [_tab_to_dict(t) for t in tabs]}


async def _resolve_default_model_for_project(
    db: Session,
    *,
    project_id: str,
    client: OpencodeClient | None,
    runtime_key: str = "opencode",
) -> str:
    """Return the project's default chat model.

    Reads ``_config_cache`` when fresh; otherwise fetches ``/config`` +
    ``/config/providers`` via ``client`` and applies the project's
    ai_assistant allowlist. Returns empty string when the client is
    unavailable so the bootstrap can still proceed (the user can pick a
    model later).
    """
    cache_key = f"{project_id}:{runtime_key}"
    now = time.monotonic()
    cache_slot = _config_cache.get(cache_key, {})
    cached_config = cache_slot.get("data")
    cached_at = cache_slot.get("at", 0.0)

    if cached_config is not None and (now - cached_at) < _CONFIG_TTL:
        return cached_config.get("default_model", "") or ""

    if client is None:
        return ""

    try:
        raw = await client.get_config()
        providers_raw = await client.get_providers()
    except Exception as exc:
        logger.warning("default-model resolve: client fetch failed: %s", exc)
        return ""

    available_models = _flatten_provider_models(providers_raw)

    project = db.get(Project, project_id)
    ai_assistant = project.config.get("ai_assistant") if project is not None else None
    project_directory = project.repo_root if project is not None else ""
    if not isinstance(project_directory, str):
        project_directory = ""

    if not isinstance(ai_assistant, dict):
        filtered_models = available_models
        default_model = _pick_default_model(raw, providers_raw, available_models)
    else:
        allowlist_raw = ai_assistant.get("models")
        allowlist = (
            [m for m in allowlist_raw if isinstance(m, str)]
            if isinstance(allowlist_raw, list)
            else []
        )
        allow_default = ai_assistant.get("default_model")
        available_set = set(available_models)
        filtered_models = [m for m in allowlist if m in available_set]
        if not filtered_models:
            filtered_models = available_models
        default_model = (
            allow_default
            if isinstance(allow_default, str) and allow_default in filtered_models
            else (filtered_models[0] if filtered_models else "")
        )

    _config_cache[cache_key] = {
        "data": {
            "models": filtered_models,
            "default_model": default_model,
            "project_directory": project_directory,
        },
        "at": now,
    }
    return default_model or ""


@router.get("/tabs/{tab_id}")
async def get_tab(
    tab_id: str,
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
    db: Session = Depends(get_db),
) -> Any:
    """Return ``{tab, session, messages}`` for the given tab.

    Health-gated for session/message retrieval: 503 when unhealthy.
    """
    tab = _tab_service.get_tab(db, tab_id)
    if tab is None:
        return JSONResponse(status_code=404, content={"error": "tab not found"})

    if not healthy or client is None:
        return _503_unavailable()

    sid = tab.opencode_session_id
    session: dict[str, Any] | None = None
    messages: list[Any] = []
    if sid:
        try:
            session = await client.get_session(sid)
            messages = await client.get_messages(sid)
        except Exception as exc:
            logger.warning("get_tab: failed to fetch session/messages for sid=%s: %s", sid, exc)

    return {"tab": _tab_to_dict(tab), "session": session, "messages": messages}


@router.patch("/tabs/{tab_id}")
async def update_tab(
    tab_id: str,
    body: UpdateTabRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Patch title and/or model on a tab.

    Empty body ``{}`` returns the tab unchanged without bumping ``updated_at``
    (invariant #8 delegated entirely to ``tab_service.update_tab``).
    Pure DB endpoint — no runtime health gate.
    """
    try:
        tab = _tab_service.update_tab(db, tab_id, title=body.title, model=body.model)
        db.commit()
    except LookupError:
        return JSONResponse(status_code=404, content={"error": "tab not found"})
    return {"tab": _tab_to_dict(tab)}


@router.delete("/tabs/{tab_id}")
async def close_tab(
    tab_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """Soft-delete a tab (status='closed', closed_at=now()). Idempotent.

    Pure DB endpoint — no runtime health gate.
    """
    try:
        _tab_service.close_tab(db, tab_id)
        db.commit()
    except LookupError:
        return JSONResponse(status_code=404, content={"error": "tab not found"})
    return Response(status_code=204)


@router.post("/tabs/{tab_id}/reopen")
async def reopen_tab(
    tab_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Un-soft-delete a tab. Idempotent (no-op when already active).

    Pure DB endpoint — no runtime health gate.
    """
    try:
        tab = _tab_service.reopen_tab(db, tab_id)
        db.commit()
    except LookupError:
        return JSONResponse(status_code=404, content={"error": "tab not found"})
    return {"tab": _tab_to_dict(tab)}


@router.get("/tabs/{tab_id}/stream")
async def stream_tab(
    tab_id: str,
    request: Request,
    relay_manager: RelayManager | None = Depends(_get_relay_manager),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """SSE stream relaying events for the given tab.

    Respects the ``Last-Event-ID`` request header and ``last_event_id``
    query parameter for ring-buffer replay (invariant — existing behaviour
    preserved from the session-scoped stream_session handler).

    Events already carry ``tab_id`` (set by RelayManager in S03) — the
    router forwards the dict to JSON without stripping or renaming any field.
    """
    if not healthy or relay_manager is None:
        return _503_unavailable()

    last_event_id = request.headers.get("Last-Event-ID") or request.query_params.get(
        "last_event_id"
    )
    try:
        relay = await relay_manager.get_or_create_relay(tab_id)
    except ValueError as exc:
        # Tab has no opencode_session_id — cannot start relay.
        return JSONResponse(status_code=404, content={"error": str(exc)})
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


@router.post("/tabs/{tab_id}/prompt")
async def send_prompt(
    tab_id: str,
    body: PromptRequest,
    db: Session = Depends(get_db),
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """Forward a user prompt to the tab's OpenCode session.

    When ``body.context`` is supplied, prepends a context chip to the
    ``system`` argument::

        [Context: viewing {title} ({type} {id})]
    """
    if not healthy or client is None:
        return _503_unavailable()

    tab = _tab_service.get_tab(db, tab_id)
    if tab is None:
        return JSONResponse(status_code=404, content={"error": "tab not found"})

    sid = tab.opencode_session_id
    if not sid:
        return JSONResponse(
            status_code=409,
            content={"error": "tab has no opencode session; create the session first"},
        )

    system: str | None = None
    if body.context:
        ctx = body.context
        title = ctx.get("title", "")
        ctype = ctx.get("type", "")
        cid = ctx.get("id", "")
        system = f"[Context: viewing {title} ({ctype} {cid})]"

    await client.prompt(sid, body.text, model=body.model, system=system)

    # Bump last_active_at on prompt so the tab ordering stays fresh.
    _tab_service.touch_last_active(db, tab_id)
    db.commit()

    return Response(status_code=204)


@router.post("/tabs/{tab_id}/abort")
async def abort_tab(
    tab_id: str,
    db: Session = Depends(get_db),
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """Abort the current in-flight prompt for the given tab's session."""
    if not healthy or client is None:
        return _503_unavailable()

    tab = _tab_service.get_tab(db, tab_id)
    if tab is None:
        return JSONResponse(status_code=404, content={"error": "tab not found"})

    sid = tab.opencode_session_id
    if not sid:
        return Response(status_code=204)  # No session to abort; no-op.

    await client.abort(sid)
    return Response(status_code=204)


@router.post("/tabs/{tab_id}/permissions/{rid}")
async def reply_permission(
    tab_id: str,
    rid: str,
    body: PermissionRequest,
    db: Session = Depends(get_db),
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """Reply to a pending ``permission.asked`` event for the tab's session."""
    if not healthy or client is None:
        return _503_unavailable()

    tab = _tab_service.get_tab(db, tab_id)
    if tab is None:
        return JSONResponse(status_code=404, content={"error": "tab not found"})

    sid = tab.opencode_session_id
    if not sid:
        return JSONResponse(
            status_code=409,
            content={"error": "tab has no opencode session"},
        )

    await client.reply_permission(sid, rid, body.response, remember=body.remember)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Retained endpoints
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_config(
    project_id: str | None = None,
    runtime: str = "opencode",
    db: Session = Depends(get_db),
    client: OpencodeClient | None = Depends(_get_client),
    healthy: bool = Depends(_check_runtime_healthy),
) -> Any:
    """Return ``{models, default_model, default_agent, project_directory}`` with 30 s TTL cache.

    The opencode ``/config`` endpoint does not expose the available models —
    those live under ``/config/providers``. This handler calls both and
    flattens the providers into a sorted, de-duplicated list of
    ``"<providerId>/<modelId>"`` strings (the shape the front-end model
    selector consumes).

    The ``runtime`` query param (default ``"opencode"``) is accepted for
    forward-compatibility with F-B (Pi runtime); the response shape is
    unchanged.

    Unlike the other endpoints, if a cached value exists it is served even
    when the runtime is temporarily unhealthy.
    """
    now = time.monotonic()
    project_key = (project_id or "").strip()
    # Cache key includes runtime so Pi (F-B) can have independent caches.
    cache_key = f"{project_key}:{runtime}" if project_key else f"__none__:{runtime}"
    cache_slot = _config_cache.get(cache_key, {})
    cached = cache_slot.get("data")
    cached_at = cache_slot.get("at", 0.0)

    if cached is not None and (now - cached_at) < _CONFIG_TTL:
        return cached

    if not healthy or client is None:
        if cached is not None:
            # Serve stale cache rather than 503
            return cached
        return _503_unavailable()

    raw = await client.get_config()
    providers_raw = await client.get_providers()

    available_models = _flatten_provider_models(providers_raw)

    def _fail_open_result() -> dict[str, Any]:
        return {
            "models": available_models,
            "default_model": _pick_default_model(raw, providers_raw, available_models),
            "default_agent": raw.get("default_agent", ""),
            "project_directory": "",
        }

    if not project_key:
        logger.info("Chat config fallback: no project_id supplied — returning full provider list")
        result = _fail_open_result()
    else:
        project = db.get(Project, project_key)
        ai_assistant = project.config.get("ai_assistant") if project is not None else None
        project_directory = project.repo_root if project is not None else ""
        if not isinstance(project_directory, str):
            project_directory = ""
        if not isinstance(ai_assistant, dict):
            logger.info(
                "Chat config fallback: project=%s has no ai_assistant allowlist "
                "— returning full provider list",
                project_key,
            )
            result = _fail_open_result()
            result["project_directory"] = project_directory
        else:
            allowlist_raw = ai_assistant.get("models")
            allowlist = (
                [m for m in allowlist_raw if isinstance(m, str)]
                if isinstance(allowlist_raw, list)
                else []
            )
            allow_default = ai_assistant.get("default_model")

            available_set = set(available_models)
            filtered = [m for m in allowlist if m in available_set]
            dropped = [m for m in allowlist if m not in available_set]
            if dropped:
                logger.warning(
                    "Chat config allowlist dropped unreachable models for project=%s: %s",
                    project_key,
                    ",".join(dropped),
                )

            if not filtered:
                logger.info(
                    "Chat config allowlist empty after intersection for project=%s "
                    "— returning full provider list",
                    project_key,
                )
                result = _fail_open_result()
            else:
                default_model = (
                    allow_default
                    if isinstance(allow_default, str) and allow_default in filtered
                    else filtered[0]
                )
                result = {
                    "models": filtered,
                    "default_model": default_model,
                    "default_agent": raw.get("default_agent", ""),
                    "project_directory": project_directory,
                }

            if "project_directory" not in result:
                result["project_directory"] = project_directory

    _config_cache[cache_key] = {"data": result, "at": now}
    return result


def _flatten_provider_models(providers_raw: dict[str, Any]) -> list[str]:
    """Flatten ``/config/providers`` into sorted ``"providerId/modelId"`` strings."""
    out: set[str] = set()
    providers = providers_raw.get("providers", [])
    if not isinstance(providers, list):
        return []
    for p in providers:
        if not isinstance(p, dict):
            continue
        pid = p.get("id")
        models = p.get("models", {})
        if not isinstance(pid, str) or not pid:
            continue
        if not isinstance(models, dict):
            continue
        for model_id in models:
            if isinstance(model_id, str) and model_id:
                out.add(f"{pid}/{model_id}")
    return sorted(out)


def _pick_default_model(
    raw_config: dict[str, Any],
    providers_raw: dict[str, Any],
    models: list[str],
) -> str:
    """Choose a default model string.

    Preference order:
      1. ``raw_config["model"]`` if it appears in the flattened ``models`` list.
      2. First ``"<providerId>/<defaultModelId>"`` from ``providers_raw["default"]``
         that matches an entry in ``models``.
      3. First entry in ``models``.
      4. Empty string when no models are configured.
    """
    candidate = raw_config.get("model")
    if isinstance(candidate, str) and candidate in models:
        return candidate

    defaults = providers_raw.get("default", {})
    if isinstance(defaults, dict):
        for pid, mid in defaults.items():
            if not isinstance(pid, str) or not isinstance(mid, str):
                continue
            combo = f"{pid}/{mid}"
            if combo in models:
                return combo

    return models[0] if models else ""


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


_SKILL_ROOTS: Final[tuple[str, ...]] = (".opencode", ".claude")
_SKILL_KINDS: Final[tuple[tuple[str, str], ...]] = (("skill", "skills"), ("command", "commands"))


def _scan_opencode_mtime() -> float:
    """Return max mtime across every skill/command file under .opencode/ and .claude/."""
    root = _OPENCODE_ROOT
    max_mtime = 0.0
    for parent in _SKILL_ROOTS:
        for _, subdir in _SKILL_KINDS:
            d = root / parent / subdir
            if not d.is_dir():
                continue
            for p in d.rglob("*"):
                if p.is_file():
                    with contextlib.suppress(OSError):
                        mt = p.stat().st_mtime
                        if mt > max_mtime:
                            max_mtime = mt
    return max_mtime


def _load_skills() -> list[dict[str, str]]:
    """Walk skill/command roots and return entries.

    Two layouts are accepted under each ``<root>/<kind>/`` directory:

    1. **Subdirectory** — ``<name>/SKILL.md`` | ``<name>/<name>.md`` |
       ``<name>/README.md`` (Claude-style skills).
    2. **Flat file** — ``<name>.md`` (the actual layout of
       ``.opencode/commands/``).

    Both ``.opencode/`` and ``.claude/`` roots are scanned. When the same
    ``(kind, name)`` appears in multiple roots the first one wins (preference
    follows ``_SKILL_ROOTS`` order).
    """
    root = _OPENCODE_ROOT
    seen: dict[tuple[str, str], dict[str, str]] = {}

    for parent in _SKILL_ROOTS:
        for kind, subdir in _SKILL_KINDS:
            d = root / parent / subdir
            if not d.is_dir():
                continue
            for entry in sorted(d.iterdir()):
                meta = _read_skill_entry(entry, kind)
                if meta is None:
                    continue
                key = (meta["kind"], meta["name"])
                if key not in seen:
                    seen[key] = meta

    return list(seen.values())


def _read_skill_entry(entry: Path, kind: str) -> dict[str, str] | None:
    """Build a metadata dict for a skill/command entry, or None to skip.

    Handles both the subdirectory layout (``<name>/SKILL.md`` etc.) and the
    flat-file layout (``<name>.md``).
    """
    if entry.is_dir():
        name = entry.name
        description = ""
        for candidate in ("SKILL.md", f"{name}.md", "README.md"):
            md = entry / candidate
            if md.is_file():
                with contextlib.suppress(OSError):
                    description = _extract_description(md.read_text(encoding="utf-8"))
                break
        return {"kind": kind, "name": name, "description": description}

    if entry.is_file() and entry.suffix.lower() == ".md":
        name = entry.stem
        description = ""
        with contextlib.suppress(OSError):
            description = _extract_description(entry.read_text(encoding="utf-8"))
        return {"kind": kind, "name": name, "description": description}

    return None


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
