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
import logging
import re
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


def resolve_browser_env(
    project_config: ProjectConfig,
    project_id: str,
    item_id: str,
) -> dict[str, str] | None:
    """Build the env-var dict for a browser_verification step.

    Returns None if the project has no browser_verification config or if
    ``env_up_command`` is missing (opt-out).

    The ports are derived deterministically from (project_id, item_id) so
    teardown does not need to persist state — it can recompute the same values.
    """
    bv_cfg: dict[str, Any] = project_config.config.get("browser_verification", {})
    if not bv_cfg or not bv_cfg.get("env_up_command"):
        return None

    pool_cfg = {**_DEFAULT_PORT_POOL, **bv_cfg.get("port_pool", {})}
    pool_size = int(pool_cfg["pool_size"])
    offset = _compute_port_offset(project_id, item_id, pool_size)

    frontend_port = int(pool_cfg["frontend_base"]) + offset
    api_port = int(pool_cfg["api_base"]) + offset
    db_port = int(pool_cfg["db_base"]) + offset
    redis_port = int(pool_cfg["redis_base"]) + offset

    compose_prefix = bv_cfg.get("compose_project_prefix") or f"{project_id}-e2e"
    compose_project_name = f"{compose_prefix}-{item_id.lower().replace('-', '')}"

    env: dict[str, str] = {
        "E2E_FRONTEND_PORT": str(frontend_port),
        "E2E_API_PORT": str(api_port),
        "E2E_DB_PORT": str(db_port),
        "E2E_REDIS_PORT": str(redis_port),
        "COMPOSE_PROJECT_NAME": compose_project_name,
        "IW_ITEM_ID": item_id,
    }

    # base_url_template: supports ${VAR} substitution
    base_url_template = bv_cfg.get("base_url_template", "http://localhost:${E2E_FRONTEND_PORT}")
    env["IW_BROWSER_BASE_URL"] = Template(base_url_template).safe_substitute(env)

    if bv_cfg.get("e2e_user"):
        env["IW_BROWSER_E2E_USER"] = bv_cfg["e2e_user"]
    if bv_cfg.get("e2e_password"):
        env["IW_BROWSER_E2E_PASSWORD"] = bv_cfg["e2e_password"]

    return env


# ---------------------------------------------------------------------------
# render_prompt_substitutions — public
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")
_KNOWN_PLACEHOLDERS = frozenset(
    {
        "IW_BROWSER_BASE_URL",
        "IW_BROWSER_E2E_USER",
        "IW_BROWSER_E2E_PASSWORD",
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

    import os  # noqa: PLC0415

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

    import os  # noqa: PLC0415

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
