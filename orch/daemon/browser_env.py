"""browser_env — helpers for browser_verification step type.

This module handles the lifecycle of the test environment (docker compose, etc.)
for browser_verification steps. Projects opt in by adding a
``browser_verification`` block to their ``.iw-orch.json``:

    {
        "browser_verification": {
            "env_up_command": "make e2e-up",
            "env_down_command": "make e2e-down",
            "base_url_template": "http://localhost:${E2E_FRONTEND_PORT}",
            "port_pool": {
                "frontend_base": 3100,
                "api_base": 8090,
                "db_base": 5442,
                "redis_base": 6389,
                "pool_size": 100
            },
            "e2e_user": "dev@example.local",
            "e2e_password": "DevPass2026!",
            "compose_project_prefix": "myproject-e2e"
        }
    }

If ``env_up_command`` is absent the project is considered opted-out and all
functions here are no-ops.

## Port allocation and collision risk

Ports are deterministic: for a given (project_id, item_id) pair the same four
ports are always returned.  With pool_size=100 the birthday-paradox collision
probability reaches ~12% at 5 concurrent items and ~50% at 12 concurrent
items.  Collisions are recoverable (compose up will fail cleanly; the env_up
hook returns False and the step is marked failed so the daemon retries later).
Increase pool_size if you run many concurrent browser_verification steps.

## Teardown ownership (per code path)

- **Timeout / crash path** → ``step_monitor._handle_crashed`` /
  ``step_monitor._handle_timeout`` call ``run_env_down_hook`` directly.
- **Success path (step-done)** → ``orch.cli.step_commands.step_done`` calls
  ``run_env_down_hook`` after flushing the step status.
- **Fail path (step-fail)** → ``orch.cli.step_commands.step_fail`` calls
  ``run_env_down_hook`` after flushing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import socket
import subprocess
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from orch.daemon.project_registry import ProjectConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Step-type check
# ---------------------------------------------------------------------------


def is_browser_verification_step(step_type: object) -> bool:
    """Return True if step_type is the browser_verification enum member or string."""
    from orch.db.models import StepType  # noqa: PLC0415

    if isinstance(step_type, StepType):
        return step_type == StepType.browser_verification
    return str(step_type) in ("browser_verification", "StepType.browser_verification")


# ---------------------------------------------------------------------------
# Port allocation (deterministic, hash-based)
# ---------------------------------------------------------------------------

_DEFAULT_PORT_POOL = {
    "frontend_base": 3100,
    "api_base": 8090,
    "db_base": 5442,
    "redis_base": 6389,
    "pool_size": 100,
}


def _compute_port_offset(project_id: str, item_id: str, pool_size: int) -> int:
    """Return a deterministic integer offset in [0, pool_size)."""
    h = int(hashlib.sha256(f"{project_id}/{item_id}".encode()).hexdigest(), 16)
    return h % pool_size


# ---------------------------------------------------------------------------
# resolve_browser_env — public
# ---------------------------------------------------------------------------


def _is_port_free(port: int) -> bool:
    """Return True if the given TCP port on 127.0.0.1 is currently unbound.

    Uses a non-reuseable bind: if another process holds the port (either
    bound or in TIME_WAIT from a recent compose-down), this returns False
    and the caller scans to the next offset.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def _ports_for_offset(pool_cfg: dict[str, Any], offset: int) -> list[int]:
    return [
        int(pool_cfg["frontend_base"]) + offset,
        int(pool_cfg["api_base"]) + offset,
        int(pool_cfg["db_base"]) + offset,
        int(pool_cfg["redis_base"]) + offset,
    ]


def _pick_free_offset(pool_cfg: dict[str, Any], project_id: str, item_id: str) -> int | None:
    """Scan forward from the hash offset until all four ports are free.

    Returns None if every slot in the pool is taken — caller treats that
    as a transient env-up failure (daemon will retry later).
    """
    pool_size = int(pool_cfg["pool_size"])
    base = _compute_port_offset(project_id, item_id, pool_size)
    for i in range(pool_size):
        offset = (base + i) % pool_size
        if all(_is_port_free(p) for p in _ports_for_offset(pool_cfg, offset)):
            return offset
    return None


# ---------------------------------------------------------------------------
# State file — persists the chosen offset so teardown uses the same ports
# ---------------------------------------------------------------------------


def _state_file_path(worktree_path: str, item_id: str) -> Path:
    return Path(worktree_path) / ".tmp" / f"browser_env_{item_id}.state"


def _load_persisted_offset(worktree_path: str, item_id: str) -> int | None:
    state_path = _state_file_path(worktree_path, item_id)
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text())
        offset = data.get("offset")
        return int(offset) if offset is not None else None
    except (json.JSONDecodeError, ValueError, OSError):
        return None


def _save_persisted_offset(worktree_path: str, item_id: str, offset: int) -> None:
    state_path = _state_file_path(worktree_path, item_id)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"offset": offset}))


def _delete_persisted_offset(worktree_path: str, item_id: str) -> None:
    state_path = _state_file_path(worktree_path, item_id)
    try:
        state_path.unlink(missing_ok=True)
    except OSError:
        logger.debug("Could not delete state file %s (non-fatal)", state_path)


# ---------------------------------------------------------------------------
# Env dict builder (shared by resolve_browser_env / allocate_browser_env)
# ---------------------------------------------------------------------------


def _build_env(
    bv_cfg: dict[str, Any],
    project_id: str,
    item_id: str,
    offset: int,
) -> dict[str, str]:
    pool_cfg = {**_DEFAULT_PORT_POOL, **bv_cfg.get("port_pool", {})}

    compose_prefix = bv_cfg.get("compose_project_prefix") or f"{project_id}-e2e"
    compose_project_name = f"{compose_prefix}-{item_id.lower().replace('-', '')}"

    ports = _ports_for_offset(pool_cfg, offset)
    env: dict[str, str] = {
        "E2E_FRONTEND_PORT": str(ports[0]),
        "E2E_API_PORT": str(ports[1]),
        "E2E_DB_PORT": str(ports[2]),
        "E2E_REDIS_PORT": str(ports[3]),
        "COMPOSE_PROJECT_NAME": compose_project_name,
        "IW_ITEM_ID": item_id,
    }

    base_url_template = bv_cfg.get("base_url_template", "http://localhost:${E2E_FRONTEND_PORT}")
    env["IW_BROWSER_BASE_URL"] = Template(base_url_template).safe_substitute(env)

    if bv_cfg.get("e2e_user"):
        env["IW_BROWSER_E2E_USER"] = bv_cfg["e2e_user"]
    if bv_cfg.get("e2e_password"):
        env["IW_BROWSER_E2E_PASSWORD"] = bv_cfg["e2e_password"]

    # Direct DSN for the isolated E2E Postgres container, so browser-verification
    # agents can INSERT rows that the dashboard under test will actually observe.
    # The worktree's `.env` points IW_CORE_DB_* at the live orchestration DB;
    # using orch.db.session.SessionLocal from an agent writes to the wrong DB
    # and V4-style "inject a row and observe it in the UI" probes silently
    # fail (the dashboard polls a different DB). Credentials match
    # docker-compose.e2e.yml's e2e-db service (non-secret, fixed).
    e2e_db_creds = bv_cfg.get("e2e_db", {})
    e2e_db_user = e2e_db_creds.get("user", "iw_e2e")
    e2e_db_password = e2e_db_creds.get("password", "iw_e2e_dev")
    e2e_db_name = e2e_db_creds.get("name", "iw_e2e")
    env["IW_BROWSER_E2E_DB_HOST"] = "127.0.0.1"
    env["IW_BROWSER_E2E_DB_PORT"] = str(ports[2])
    env["IW_BROWSER_E2E_DB_NAME"] = e2e_db_name
    env["IW_BROWSER_E2E_DB_USER"] = e2e_db_user
    env["IW_BROWSER_E2E_DB_PASSWORD"] = e2e_db_password
    env["IW_BROWSER_E2E_DB_URL"] = (
        f"postgresql://{e2e_db_user}:{e2e_db_password}@127.0.0.1:{ports[2]}/{e2e_db_name}"
    )

    # Before overriding IW_CORE_DB_*, snapshot the daemon's orch DB credentials
    # as IW_CORE_ORCH_DB_*. The iw CLI step commands (step-done/fail/start)
    # prefer IW_CORE_ORCH_DB_* so they always reach the real orch DB, while
    # alembic, SessionLocal, and the E2E dashboard keep using the isolated DB.
    for _src, _dst in (
        ("IW_CORE_DB_HOST", "IW_CORE_ORCH_DB_HOST"),
        ("IW_CORE_DB_PORT", "IW_CORE_ORCH_DB_PORT"),
        ("IW_CORE_DB_NAME", "IW_CORE_ORCH_DB_NAME"),
        ("IW_CORE_DB_USER", "IW_CORE_ORCH_DB_USER"),
        ("IW_CORE_DB_PASSWORD", "IW_CORE_ORCH_DB_PASSWORD"),
    ):
        _val = os.environ.get(_src)
        if _val:
            env[_dst] = _val

    # IW_CORE_DB_* must also be set so that "uv run alembic" and any other
    # Python code that reads orch.config.get_db_url() inside the agent
    # subprocess uses the per-worktree DB (127.0.0.1:N) instead of the live
    # orch DB (5433) that the daemon's shell IW_CORE_DB_* points at.
    # load_dotenv() does NOT override existing env vars, so without these
    # explicit entries the agent would connect to the wrong DB and V2 would
    # corrupt the live orch DB's alembic_version.
    env["IW_CORE_DB_HOST"] = "127.0.0.1"
    env["IW_CORE_DB_PORT"] = str(ports[2])
    env["IW_CORE_DB_NAME"] = e2e_db_name
    env["IW_CORE_DB_USER"] = e2e_db_user
    env["IW_CORE_DB_PASSWORD"] = e2e_db_password

    return env


def resolve_browser_env(
    project_config: ProjectConfig,
    project_id: str,
    item_id: str,
    worktree_path: str | None = None,
) -> dict[str, str] | None:
    """Build the env-var dict for a browser_verification step.

    Returns None if the project has no browser_verification config or if
    ``env_up_command`` is missing (opt-out).

    If ``worktree_path`` is provided and a persisted offset exists from a
    prior ``allocate_browser_env`` call, that offset is used. Otherwise
    falls back to the deterministic hash offset.  This is the *read*
    entry point — teardown callers use it because they need to recover
    the exact ports that were brought up.
    """
    bv_cfg: dict[str, Any] = project_config.config.get("browser_verification", {})
    if not bv_cfg or not bv_cfg.get("env_up_command"):
        return None

    pool_cfg = {**_DEFAULT_PORT_POOL, **bv_cfg.get("port_pool", {})}
    pool_size = int(pool_cfg["pool_size"])

    offset: int | None = None
    if worktree_path:
        offset = _load_persisted_offset(worktree_path, item_id)
    if offset is None:
        offset = _compute_port_offset(project_id, item_id, pool_size)

    return _build_env(bv_cfg, project_id, item_id, offset)


def allocate_browser_env(
    project_config: ProjectConfig,
    project_id: str,
    item_id: str,
    worktree_path: str,
) -> dict[str, str] | None:
    """Allocate a free port slot for a browser_verification step.

    Reuses the persisted offset if one exists (handles retries / replays).
    Otherwise scans forward from the hash offset until all four ports are
    free, then persists the chosen offset to ``.tmp/browser_env_<item>.state``
    so teardown can recover it.

    Returns None when the project is opted out, or when every slot in the
    pool is occupied (treated as transient — daemon retries).
    """
    bv_cfg: dict[str, Any] = project_config.config.get("browser_verification", {})
    if not bv_cfg or not bv_cfg.get("env_up_command"):
        return None

    persisted = _load_persisted_offset(worktree_path, item_id)
    if persisted is not None:
        return _build_env(bv_cfg, project_id, item_id, persisted)

    pool_cfg = {**_DEFAULT_PORT_POOL, **bv_cfg.get("port_pool", {})}
    offset = _pick_free_offset(pool_cfg, project_id, item_id)
    if offset is None:
        logger.warning(
            "browser_env: no free port slot in pool (size=%d) for %s/%s",
            int(pool_cfg["pool_size"]),
            project_id,
            item_id,
        )
        return None

    _save_persisted_offset(worktree_path, item_id, offset)
    return _build_env(bv_cfg, project_id, item_id, offset)


# ---------------------------------------------------------------------------
# render_prompt_substitutions — public
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")
_KNOWN_PLACEHOLDERS = frozenset(
    {
        "IW_BROWSER_BASE_URL",
        "IW_BROWSER_E2E_USER",
        "IW_BROWSER_E2E_PASSWORD",
        "IW_BROWSER_E2E_DB_URL",
        "IW_BROWSER_E2E_DB_HOST",
        "IW_BROWSER_E2E_DB_PORT",
        "IW_BROWSER_E2E_DB_NAME",
        "IW_BROWSER_E2E_DB_USER",
        "IW_BROWSER_E2E_DB_PASSWORD",
        "IW_ITEM_ID",
        "IW_STEP_ID",
    }
)


def render_prompt_substitutions(prompt_text: str, env: dict[str, str]) -> str:
    """Replace {{VAR_NAME}} placeholders in prompt_text.

    Only substitutes known placeholder names; unknown ones are left verbatim
    so agents see them literally rather than getting empty strings.
    """

    def _replace(m: re.Match[str]) -> str:
        name = m.group(1)
        if name in _KNOWN_PLACEHOLDERS and name in env:
            return env[name]
        return m.group(0)  # leave unknown placeholders untouched

    return _PLACEHOLDER_RE.sub(_replace, prompt_text)


# ---------------------------------------------------------------------------
# Internal: log file path helper
# ---------------------------------------------------------------------------


def _log_path(worktree_path: str, item_id: str, step_id: str, suffix: str) -> Path:
    log_dir = Path(worktree_path) / "ai-dev" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{item_id}_{step_id}_{suffix}.log"


# ---------------------------------------------------------------------------
# run_env_up_hook — public
# ---------------------------------------------------------------------------


def run_env_up_hook(
    project_config: ProjectConfig,
    worktree_path: str,
    env: dict[str, str],
    item_id: str,
    step_id: str,
) -> tuple[bool, Path]:
    """Run the env_up_command in the worktree.

    Returns (success, log_path).
    If env_up_command is not configured, returns (True, Path('')) — feature
    is opt-in; missing command means no-op.
    """
    bv_cfg: dict[str, Any] = project_config.config.get("browser_verification", {})
    env_up_cmd = bv_cfg.get("env_up_command", "")
    if not env_up_cmd:
        return True, Path()

    log_path = _log_path(worktree_path, item_id, step_id, "browser_env_up")

    merged_env = {**os.environ, **env}

    logger.info(
        "[%s/%s] Running browser env_up: %s (log: %s)",
        item_id,
        step_id,
        env_up_cmd,
        log_path,
    )
    try:
        with log_path.open("w") as log_fh:
            result = subprocess.run(  # noqa: S602
                env_up_cmd,
                shell=True,
                cwd=worktree_path,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                timeout=600,
                env=merged_env,
            )
        if result.returncode != 0:
            logger.warning(
                "[%s/%s] browser env_up exited %d — see %s",
                item_id,
                step_id,
                result.returncode,
                log_path,
            )
            return False, log_path
        logger.info("[%s/%s] browser env_up succeeded", item_id, step_id)
        return True, log_path
    except subprocess.TimeoutExpired:
        logger.warning(
            "[%s/%s] browser env_up timed out after 600s — see %s",
            item_id,
            step_id,
            log_path,
        )
        return False, log_path
    except Exception as exc:
        logger.warning(
            "[%s/%s] browser env_up failed with exception: %s — see %s",
            item_id,
            step_id,
            exc,
            log_path,
        )
        return False, log_path


def _capture_crashed_container_logs(compose_log: str, tail: int = 50) -> str:
    """Parse compose output for exited containers and capture their docker logs.

    Returns a formatted string ready to append to StepRun.error_message.
    Never raises — all failures are silently ignored so a logging failure
    cannot block the step-failure recording path.
    """
    pattern = re.compile(r"container\s+([\w\-]+)\s+exited\s+\(\d+\)", re.IGNORECASE)
    container_names = list(dict.fromkeys(pattern.findall(compose_log)))
    if not container_names:
        return ""

    parts: list[str] = []
    for name in container_names:
        try:
            result = subprocess.run(  # noqa: S603, S607
                ["docker", "logs", name, "--tail", str(tail)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            combined = (result.stdout + result.stderr).strip()
            if combined:
                parts.append(f"### docker logs {name} (last {tail} lines)\n\n{combined}")
        except Exception:  # noqa: BLE001
            parts.append(f"### docker logs {name}\n\n(unavailable — docker logs failed)")
    if not parts:
        return ""
    return "\n\n## Container Crash Logs\n\n" + "\n\n".join(parts)


# ---------------------------------------------------------------------------
# run_env_down_hook — public
# ---------------------------------------------------------------------------


def run_env_down_hook(
    project_config: ProjectConfig,
    worktree_path: str,
    env: dict[str, str],
    item_id: str,
    step_id: str,
) -> None:
    """Run the env_down_command. Idempotent — never raises.

    If env_down_command is not configured, this is a no-op.
    """
    bv_cfg: dict[str, Any] = project_config.config.get("browser_verification", {})
    env_down_cmd = bv_cfg.get("env_down_command", "")
    if not env_down_cmd:
        logger.debug(
            "[%s/%s] No env_down_command configured — skipping teardown",
            item_id,
            step_id,
        )
        return

    merged_env = {**os.environ, **env}

    try:
        log_path = _log_path(worktree_path, item_id, step_id, "browser_env_down")
    except Exception:
        # If we can't even create the log path, still try to run the command
        log_path = Path(f"/tmp/{item_id}_{step_id}_browser_env_down.log")  # noqa: S108

    logger.info(
        "[%s/%s] Running browser env_down: %s (log: %s)",
        item_id,
        step_id,
        env_down_cmd,
        log_path,
    )
    try:
        with log_path.open("w") as log_fh:
            result = subprocess.run(  # noqa: S602
                env_down_cmd,
                shell=True,
                cwd=worktree_path,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                timeout=300,
                env=merged_env,
            )
        if result.returncode != 0:
            logger.warning(
                "[%s/%s] browser env_down exited %d (non-fatal) — see %s",
                item_id,
                step_id,
                result.returncode,
                log_path,
            )
    except subprocess.TimeoutExpired:
        logger.warning(
            "[%s/%s] browser env_down timed out (non-fatal) — see %s",
            item_id,
            step_id,
            log_path,
        )
    except Exception as exc:
        logger.warning(
            "[%s/%s] browser env_down failed with exception (non-fatal): %s",
            item_id,
            step_id,
            exc,
        )
    finally:
        _delete_persisted_offset(worktree_path, item_id)
