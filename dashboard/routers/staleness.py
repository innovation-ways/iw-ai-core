"""Staleness router — Stale Process & Migration Detector (F-00063).

Endpoints:
  GET  /projects/{project_id}/staleness           — panel HTML fragment
  GET  /projects/{project_id}/staleness-dot       — small dot HTML fragment
  POST /projects/{project_id}/services/{svc}/restart
  POST /projects/{project_id}/services/{svc}/start
  POST /projects/{project_id}/services/{svc}/stop
  POST /projects/{project_id}/alembic/upgrade

Design notes:
  - No DB required: all staleness state is computed live from projects.toml,
    /proc, git log, and alembic subprocesses. ``get_db`` is never injected.
  - 5-second per-(project_id, service_name) soft-lock is held in a
    module-level dict. This is correct because the dashboard runs as a
    single uvicorn worker. Multi-worker deployments would need a shared
    store, but that is out of scope for this feature.
  - projects.toml is re-read on every action (Invariant 6: no caching).
  - ``projects.toml`` is a trusted operator-only config; restart/start/stop
    commands run with ``shell=True`` so operators can use shell features
    (pipes, ``&&``, variable expansion, etc.). Never log command contents
    that could contain secrets.
  - For the iw-ai-core dashboard restarting itself: the restart endpoint
    returns 202 immediately (not 204) so the HTTP response can flush before
    the helper script kills and respawns the dashboard process.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
import tomllib
from pathlib import Path
from subprocess import DEVNULL
from typing import Any, cast

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from orch.staleness.service import compute_project_staleness

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Module-level templates reference (patched in tests to avoid rendering
# real Jinja2 templates that S04 hasn't created yet).
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _HERE / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# ---------------------------------------------------------------------------
# 5-second per-service soft-lock.
# Maps (project_id, service_name) → monotonic timestamp of last successful action.
# Single-process assumption: the dashboard runs as one uvicorn worker.
# ---------------------------------------------------------------------------

_service_locks: dict[tuple[str, str], float] = {}
_LOCK_SECONDS = 5.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_projects_toml() -> dict[str, Any]:
    """Load and return the raw projects.toml dict.

    Re-reads from disk on every call per Invariant 6 (no caching).
    Raises tomllib.TOMLDecodeError on parse failure (caller handles it).
    """
    from orch.config import CORE_ROOT  # noqa: PLC0415

    toml_path = CORE_ROOT / "projects.toml"
    return tomllib.loads(toml_path.read_text())


def _is_known_project(project_id: str) -> bool:
    """Return True iff project_id is present in projects.toml.

    Loads projects.toml fresh.  Returns False on parse errors (safe default).
    """
    try:
        data = _load_projects_toml()
        return project_id in data.get("projects", {})
    except Exception:  # noqa: BLE001
        return False


def _get_service_config(
    project_id: str, service_name: str, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Return the raw service config dict for (project_id, service_name), or None."""
    project_entry = data.get("projects", {}).get(project_id)
    if project_entry is None:
        return None
    for svc in project_entry.get("services", []):
        if svc.get("name") == service_name:
            return cast("dict[str, Any]", svc)
    return None


def _get_alembic_config(project_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Return the raw alembic config dict for project_id, or None."""
    project_entry = data.get("projects", {}).get(project_id)
    if project_entry is None:
        return None
    alembic = project_entry.get("alembic")
    if alembic is None:
        return None
    return cast("dict[str, Any]", alembic)


def _get_repo_root(project_id: str, data: dict[str, Any]) -> str:
    """Return the repo_root string for a project (empty string if missing)."""
    return cast("str", data.get("projects", {}).get(project_id, {}).get("repo_root", ""))


def _toast_response(
    message: str,
    *,
    status_code: int = 204,
) -> Response:
    """Return a response with an HX-Trigger showToast header.

    Uses ``"type"`` (not ``"kind"``) to match the ``showToast`` JS helper in
    ``dashboard/templates/components/toast.html`` and the existing
    ``action_response`` / ``_action_response`` helpers in this package.
    """
    trigger = json.dumps({"showToast": {"message": message, "type": "success"}})
    return Response(
        status_code=status_code,
        headers={
            "HX-Trigger": trigger,
        },
    )


def _check_soft_lock(project_id: str, service_name: str) -> Response | None:
    """Check the per-service 5-second soft-lock.

    Returns a 429 Response if the lock is engaged, otherwise None (proceed).
    Records the current timestamp as the new lock value when not locked.
    """
    key = (project_id, service_name)
    now = time.monotonic()
    last = _service_locks.get(key)
    if last is not None:
        elapsed = now - last
        if elapsed < _LOCK_SECONDS:
            remaining = _LOCK_SECONDS - elapsed
            return Response(
                status_code=429,
                content=f"Rate limited — retry in {remaining:.1f}s",
                headers={"Retry-After": str(int(remaining) + 1)},
            )
    _service_locks[key] = now
    return None


def _spawn_command(command: str, repo_root: str) -> None:
    """Spawn a shell command detached (start_new_session=True).

    - shell=True: operator-supplied commands may use shell features.
    - start_new_session=True: spawned process survives the parent worker.
    - stdout/stderr are discarded (operator is responsible for service logs).
    """
    subprocess.Popen(  # noqa: S602 — shell=True intentional; command from trusted projects.toml
        command,
        shell=True,
        start_new_session=True,
        stdout=DEVNULL,
        stderr=DEVNULL,
        cwd=repo_root or None,
    )


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/staleness — panel fragment
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/staleness", response_class=HTMLResponse)
def staleness_panel(project_id: str, request: Request) -> Any:
    """Return the staleness panel HTML fragment for the project home page.

    Returns 404 if the project is not in projects.toml.
    Returns empty fragment (200, empty body) for opt-out projects.
    """
    if not _is_known_project(project_id):
        return Response(status_code=404, content=f"Project '{project_id}' not found")

    result = compute_project_staleness(project_id)

    # Opt-out: no services and no alembic — return empty fragment
    if not result.services and result.alembic is None:
        return Response(status_code=200, content="", media_type="text/html")

    # Build a minimal project-like object so templates can use project.id
    project = type("_Project", (), {"id": project_id})()
    return templates.TemplateResponse(
        request,
        "fragments/staleness_panel.html",
        {"staleness": result, "project": project},
    )


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/staleness-dot — dot fragment
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/staleness-dot", response_class=HTMLResponse)
def staleness_dot(project_id: str, request: Request) -> Any:
    """Return the small dot HTML fragment for the project list row.

    Returns 404 if the project is not in projects.toml.
    Returns a LITERAL empty body (no whitespace) for opt-out projects —
    htmx must receive exactly empty content to replace the placeholder with nothing.
    """
    if not _is_known_project(project_id):
        return Response(status_code=404, content=f"Project '{project_id}' not found")

    result = compute_project_staleness(project_id)

    # Opt-out: return a literal empty body so htmx replaces placeholder with nothing
    if not result.services and result.alembic is None:
        return Response(status_code=200, content="", media_type="text/html")

    # Build a minimal project-like object so templates can use project.id
    project = type("_Project", (), {"id": project_id})()
    return templates.TemplateResponse(
        request,
        "fragments/staleness_dot.html",
        {"staleness": result, "project": project},
    )


# ---------------------------------------------------------------------------
# Confirm dialog fragments (GET) — loaded by action buttons via hx-get
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/services/{service_name}/restart/confirm",
    response_class=HTMLResponse,
)
def service_restart_confirm(project_id: str, service_name: str, request: Request) -> Any:
    """Return the confirm dialog fragment for restarting a service."""
    try:
        data = _load_projects_toml()
    except Exception as exc:  # noqa: BLE001
        logger.error("[staleness] Failed to load projects.toml: %s", exc)
        return Response(status_code=500, content="Failed to load configuration")

    svc = _get_service_config(project_id, service_name, data)
    if svc is None or project_id not in data.get("projects", {}):
        return Response(status_code=404, content=f"Service '{service_name}' not found")

    return templates.TemplateResponse(
        request,
        "fragments/staleness_confirm.html",
        {
            "action": "restart",
            "service_name": service_name,
            "command_text": svc.get("restart_command", ""),
            "action_url": f"/projects/{project_id}/services/{service_name}/restart",
        },
    )


@router.get(
    "/projects/{project_id}/services/{service_name}/start/confirm",
    response_class=HTMLResponse,
)
def service_start_confirm(project_id: str, service_name: str, request: Request) -> Any:
    """Return the confirm dialog fragment for starting a service."""
    try:
        data = _load_projects_toml()
    except Exception as exc:  # noqa: BLE001
        logger.error("[staleness] Failed to load projects.toml: %s", exc)
        return Response(status_code=500, content="Failed to load configuration")

    svc = _get_service_config(project_id, service_name, data)
    if svc is None or project_id not in data.get("projects", {}):
        return Response(status_code=404, content=f"Service '{service_name}' not found")

    return templates.TemplateResponse(
        request,
        "fragments/staleness_confirm.html",
        {
            "action": "start",
            "service_name": service_name,
            "command_text": svc.get("start_command", ""),
            "action_url": f"/projects/{project_id}/services/{service_name}/start",
        },
    )


@router.get(
    "/projects/{project_id}/services/{service_name}/stop/confirm",
    response_class=HTMLResponse,
)
def service_stop_confirm(project_id: str, service_name: str, request: Request) -> Any:
    """Return the confirm dialog fragment for stopping a service."""
    try:
        data = _load_projects_toml()
    except Exception as exc:  # noqa: BLE001
        logger.error("[staleness] Failed to load projects.toml: %s", exc)
        return Response(status_code=500, content="Failed to load configuration")

    svc = _get_service_config(project_id, service_name, data)
    if svc is None or project_id not in data.get("projects", {}):
        return Response(status_code=404, content=f"Service '{service_name}' not found")

    return templates.TemplateResponse(
        request,
        "fragments/staleness_confirm.html",
        {
            "action": "stop",
            "service_name": service_name,
            "command_text": svc.get("stop_command", ""),
            "action_url": f"/projects/{project_id}/services/{service_name}/stop",
        },
    )


@router.get(
    "/projects/{project_id}/alembic/upgrade/confirm",
    response_class=HTMLResponse,
)
def alembic_upgrade_confirm(project_id: str, request: Request) -> Any:
    """Return the confirm dialog fragment for running alembic upgrade head."""
    try:
        data = _load_projects_toml()
    except Exception as exc:  # noqa: BLE001
        logger.error("[staleness] Failed to load projects.toml: %s", exc)
        return Response(status_code=500, content="Failed to load configuration")

    alembic_cfg = _get_alembic_config(project_id, data)
    if alembic_cfg is None or project_id not in data.get("projects", {}):
        return Response(status_code=404, content=f"No alembic config for project '{project_id}'")

    cfg_path = alembic_cfg.get("config", "alembic.ini")
    command_text = f"alembic -c {cfg_path} upgrade head"

    return templates.TemplateResponse(
        request,
        "fragments/staleness_confirm.html",
        {
            "action": "upgrade",
            "service_name": None,
            "command_text": command_text,
            "action_url": f"/projects/{project_id}/alembic/upgrade",
        },
    )


# ---------------------------------------------------------------------------
# Restart a service
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/services/{service_name}/restart")
def service_restart(project_id: str, service_name: str) -> Any:
    """Invoke the configured restart_command for a service.

    Returns:
        204 on success (with HX-Trigger showToast header).
        202 when the service is the dashboard itself (response must flush before
            the helper script kills the old process).
        404 if project or service is unknown.
        409 if no restart_command is configured.
        429 if the per-service 5-second soft-lock is engaged.
    """
    try:
        data = _load_projects_toml()
    except Exception as exc:  # noqa: BLE001
        logger.error("[staleness] Failed to load projects.toml: %s", exc)
        return Response(status_code=500, content="Failed to load configuration")

    svc = _get_service_config(project_id, service_name, data)
    if svc is None or project_id not in data.get("projects", {}):
        return Response(status_code=404, content=f"Service '{service_name}' not found")

    command = svc.get("restart_command") or None
    if command is None:
        return Response(
            status_code=409,
            content=f"Service '{service_name}' has no restart_command configured",
        )

    lock_response = _check_soft_lock(project_id, service_name)
    if lock_response is not None:
        return lock_response

    repo_root = _get_repo_root(project_id, data)
    _spawn_command(command, repo_root)

    # Dashboard self-restart: return 202 so the response flushes before the
    # helper script kills this process.
    status_code = 202 if "restart-dashboard" in command else 204
    return _toast_response(f"Restarting {service_name}…", status_code=status_code)


# ---------------------------------------------------------------------------
# Start a service
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/services/{service_name}/start")
def service_start(project_id: str, service_name: str) -> Any:
    """Invoke the configured start_command for a service.

    Returns:
        204 on success.
        404 if project or service is unknown.
        409 if no start_command is configured.
        429 if the per-service 5-second soft-lock is engaged.
    """
    try:
        data = _load_projects_toml()
    except Exception as exc:  # noqa: BLE001
        logger.error("[staleness] Failed to load projects.toml: %s", exc)
        return Response(status_code=500, content="Failed to load configuration")

    svc = _get_service_config(project_id, service_name, data)
    if svc is None or project_id not in data.get("projects", {}):
        return Response(status_code=404, content=f"Service '{service_name}' not found")

    command = svc.get("start_command") or None
    if command is None:
        return Response(
            status_code=409,
            content=f"Service '{service_name}' has no start_command configured",
        )

    lock_response = _check_soft_lock(project_id, service_name)
    if lock_response is not None:
        return lock_response

    repo_root = _get_repo_root(project_id, data)
    _spawn_command(command, repo_root)
    return _toast_response(f"Starting {service_name}…")


# ---------------------------------------------------------------------------
# Stop a service
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/services/{service_name}/stop")
def service_stop(project_id: str, service_name: str) -> Any:
    """Invoke the configured stop_command for a service.

    Returns:
        204 on success.
        404 if project or service is unknown.
        409 if no stop_command is configured.
        429 if the per-service 5-second soft-lock is engaged.
    """
    try:
        data = _load_projects_toml()
    except Exception as exc:  # noqa: BLE001
        logger.error("[staleness] Failed to load projects.toml: %s", exc)
        return Response(status_code=500, content="Failed to load configuration")

    svc = _get_service_config(project_id, service_name, data)
    if svc is None or project_id not in data.get("projects", {}):
        return Response(status_code=404, content=f"Service '{service_name}' not found")

    command = svc.get("stop_command") or None
    if command is None:
        return Response(
            status_code=409,
            content=f"Service '{service_name}' has no stop_command configured",
        )

    lock_response = _check_soft_lock(project_id, service_name)
    if lock_response is not None:
        return lock_response

    repo_root = _get_repo_root(project_id, data)
    _spawn_command(command, repo_root)
    return _toast_response(f"Stopping {service_name}…")


# ---------------------------------------------------------------------------
# Apply alembic migration
# ---------------------------------------------------------------------------


_ALEMBIC_TIMEOUT = 60  # seconds


@router.post("/projects/{project_id}/alembic/upgrade")
def alembic_upgrade(project_id: str) -> Any:
    """Run ``alembic upgrade head`` for the project's configured DB.

    Returns:
        200 with alembic stdout on success (rc=0).
        404 if project has no alembic block, or project is unknown.
        502 if alembic exits non-zero (DB unreachable, migration error).
        500 on projects.toml parse failure.

    Environment:
        When ``db_url_env`` is configured, its value is injected into the
        subprocess environment as the named var and also as IW_ALEMBIC_DB_URL.
        Its contents are never logged (it may be a connection string with
        credentials).
        When ``db_url_env`` is omitted, the subprocess inherits the parent
        environment unchanged — suitable for projects whose alembic env.py
        already resolves the URL from app config (e.g. iw-ai-core itself).
    """
    try:
        data = _load_projects_toml()
    except Exception as exc:  # noqa: BLE001
        logger.error("[staleness] Failed to load projects.toml: %s", exc)
        return Response(status_code=500, content="Failed to load configuration")

    projects = data.get("projects", {})
    if project_id not in projects:
        return Response(status_code=404, content=f"Project '{project_id}' not found")

    alembic_cfg = _get_alembic_config(project_id, data)
    if alembic_cfg is None:
        return Response(
            status_code=404,
            content=f"Project '{project_id}' has no alembic configuration",
        )

    repo_root = _get_repo_root(project_id, data)
    cfg_path = str(Path(repo_root) / alembic_cfg["config"])
    db_url_env = alembic_cfg.get("db_url_env") or None

    # Build subprocess environment
    env: dict[str, str] | None = None
    if db_url_env is not None:
        db_url = os.environ.get(db_url_env)
        if db_url is None:
            logger.warning(
                "[staleness] alembic upgrade: env var %r not set for project %r",
                db_url_env,
                project_id,
            )
            return Response(
                status_code=502,
                content=f"Environment variable '{db_url_env}' is not set",
            )
        env = dict(os.environ)
        env[db_url_env] = db_url
        env["IW_ALEMBIC_DB_URL"] = db_url
        # Never log db_url — it may contain credentials

    try:
        result = subprocess.run(  # noqa: S603,S607 — alembic CLI, args list, no shell injection
            ["alembic", "-c", cfg_path, "upgrade", "head"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=_ALEMBIC_TIMEOUT,
            check=False,
            env=env,
            cwd=repo_root or None,
        )
    except subprocess.TimeoutExpired:
        logger.warning("[staleness] alembic upgrade timed out for project %r", project_id)
        return Response(
            status_code=502,
            content=f"alembic upgrade timed out after {_ALEMBIC_TIMEOUT}s",
        )
    except OSError as exc:
        logger.warning("[staleness] alembic upgrade failed for project %r: %s", project_id, exc)
        return Response(status_code=502, content=str(exc))

    if result.returncode != 0:
        stderr = result.stderr.strip()
        logger.warning(
            "[staleness] alembic upgrade exited %d for project %r",
            result.returncode,
            project_id,
        )
        return JSONResponse(
            status_code=502,
            content={
                "error": "alembic upgrade failed",
                "returncode": result.returncode,
                "stderr": stderr,
            },
        )

    stdout = result.stdout.strip()
    logger.info("[staleness] alembic upgrade succeeded for project %r", project_id)
    trigger = json.dumps(
        {"showToast": {"message": "Migrations applied successfully", "type": "success"}}
    )
    return Response(
        status_code=200,
        content=stdout,
        media_type="text/plain",
        headers={"HX-Trigger": trigger},
    )
