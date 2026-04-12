"""Unit tests for orch.daemon.browser_env — no DB, no subprocess calls.

All subprocess calls are patched. Tests verify:
- resolve_browser_env returns None when project has no browser config
- Deterministic port allocation
- render_prompt_substitutions placeholder handling
- run_env_up_hook opt-out and error handling
- run_env_down_hook never raises
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from orch.daemon.browser_env import (
    _compute_port_offset,
    is_browser_verification_step,
    render_prompt_substitutions,
    resolve_browser_env,
    run_env_down_hook,
    run_env_up_hook,
)
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import StepType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_project_config(bv_cfg: dict | None = None) -> ProjectConfig:
    config: dict = {}
    if bv_cfg is not None:
        config["browser_verification"] = bv_cfg
    return ProjectConfig(
        id="innoforge",
        display_name="InnoForge",
        repo_root="/repos/innoforge",
        enabled=True,
        cli_tool="claude",
        worktree_base=".worktrees",
        config=config,
    )


_FULL_BV_CFG = {
    "env_up_command": "make e2e-up",
    "env_down_command": "make e2e-down",
    "base_url_template": "http://localhost:${E2E_FRONTEND_PORT}",
    "port_pool": {
        "frontend_base": 3100,
        "api_base": 8090,
        "db_base": 5442,
        "redis_base": 6389,
        "pool_size": 100,
    },
    "e2e_user": "dev@example.local",
    "e2e_password": "Secret123",
    "compose_project_prefix": "innoforge-e2e",
}


# ---------------------------------------------------------------------------
# is_browser_verification_step
# ---------------------------------------------------------------------------


def test_is_browser_verification_step_enum() -> None:
    assert is_browser_verification_step(StepType.browser_verification) is True


def test_is_browser_verification_step_string() -> None:
    assert is_browser_verification_step("browser_verification") is True


def test_is_browser_verification_step_other_enum() -> None:
    assert is_browser_verification_step(StepType.implementation) is False


def test_is_browser_verification_step_other_string() -> None:
    assert is_browser_verification_step("implementation") is False


# ---------------------------------------------------------------------------
# resolve_browser_env — opt-out cases
# ---------------------------------------------------------------------------


def test_resolve_browser_env_no_config_returns_none() -> None:
    """Project with no browser_verification block → None."""
    pc = make_project_config(bv_cfg=None)
    result = resolve_browser_env(pc, "innoforge", "F-00001")
    assert result is None


def test_resolve_browser_env_empty_config_returns_none() -> None:
    """Project with empty browser_verification block → None."""
    pc = make_project_config(bv_cfg={})
    result = resolve_browser_env(pc, "innoforge", "F-00001")
    assert result is None


def test_resolve_browser_env_missing_env_up_command_returns_none() -> None:
    """browser_verification block without env_up_command → None (opt-out)."""
    pc = make_project_config(bv_cfg={"env_down_command": "make e2e-down"})
    result = resolve_browser_env(pc, "innoforge", "F-00001")
    assert result is None


# ---------------------------------------------------------------------------
# resolve_browser_env — port allocation
# ---------------------------------------------------------------------------


def test_resolve_browser_env_returns_expected_keys() -> None:
    pc = make_project_config(bv_cfg=_FULL_BV_CFG)
    env = resolve_browser_env(pc, "innoforge", "F-00001")
    assert env is not None
    assert "E2E_FRONTEND_PORT" in env
    assert "E2E_API_PORT" in env
    assert "E2E_DB_PORT" in env
    assert "E2E_REDIS_PORT" in env
    assert "COMPOSE_PROJECT_NAME" in env
    assert "IW_BROWSER_BASE_URL" in env
    assert "IW_BROWSER_E2E_USER" in env
    assert "IW_BROWSER_E2E_PASSWORD" in env
    assert "IW_ITEM_ID" in env


def test_resolve_browser_env_deterministic() -> None:
    """Same (project_id, item_id) always yields the same ports."""
    pc = make_project_config(bv_cfg=_FULL_BV_CFG)
    env1 = resolve_browser_env(pc, "innoforge", "F-00007")
    env2 = resolve_browser_env(pc, "innoforge", "F-00007")
    assert env1 == env2


def test_resolve_browser_env_different_items_different_ports() -> None:
    """Different item_ids (with different hashes) yield different offsets."""
    pc = make_project_config(bv_cfg=_FULL_BV_CFG)
    env1 = resolve_browser_env(pc, "innoforge", "F-00001")
    env2 = resolve_browser_env(pc, "innoforge", "F-00002")
    assert env1 is not None
    assert env2 is not None
    # Ports are derived from a hash — almost certainly different for distinct IDs
    assert env1["E2E_FRONTEND_PORT"] != env2["E2E_FRONTEND_PORT"]


def test_resolve_browser_env_ports_in_valid_range() -> None:
    """All four ports must fall within base + pool_size."""
    pc = make_project_config(bv_cfg=_FULL_BV_CFG)
    env = resolve_browser_env(pc, "innoforge", "F-00042")
    assert env is not None
    pool = _FULL_BV_CFG["port_pool"]
    assert (
        pool["frontend_base"]
        <= int(env["E2E_FRONTEND_PORT"])
        < pool["frontend_base"] + pool["pool_size"]
    )
    assert pool["api_base"] <= int(env["E2E_API_PORT"]) < pool["api_base"] + pool["pool_size"]
    assert pool["db_base"] <= int(env["E2E_DB_PORT"]) < pool["db_base"] + pool["pool_size"]
    assert pool["redis_base"] <= int(env["E2E_REDIS_PORT"]) < pool["redis_base"] + pool["pool_size"]


def test_resolve_browser_env_offset_uses_pool_size() -> None:
    """_compute_port_offset stays within [0, pool_size)."""
    for pool_size in (10, 50, 100, 200):
        offset = _compute_port_offset("proj", "F-00001", pool_size)
        assert 0 <= offset < pool_size


def test_resolve_browser_env_base_url_substituted() -> None:
    pc = make_project_config(bv_cfg=_FULL_BV_CFG)
    env = resolve_browser_env(pc, "innoforge", "F-00001")
    assert env is not None
    port = env["E2E_FRONTEND_PORT"]
    assert env["IW_BROWSER_BASE_URL"] == f"http://localhost:{port}"


def test_resolve_browser_env_default_port_pool() -> None:
    """If port_pool is absent, platform defaults are used."""
    pc = make_project_config(bv_cfg={"env_up_command": "make up"})
    env = resolve_browser_env(pc, "proj", "I-00001")
    assert env is not None
    # Default frontend_base=3100; port must be >= 3100
    assert int(env["E2E_FRONTEND_PORT"]) >= 3100


def test_resolve_browser_env_default_compose_prefix() -> None:
    """If compose_project_prefix is absent, defaults to '{project_id}-e2e-{item}'."""
    pc = make_project_config(bv_cfg={"env_up_command": "make up"})
    env = resolve_browser_env(pc, "myproj", "F-00001")
    assert env is not None
    assert env["COMPOSE_PROJECT_NAME"].startswith("myproj-e2e-")


def test_resolve_browser_env_no_e2e_user_skips_key() -> None:
    """If e2e_user is absent, IW_BROWSER_E2E_USER must not be in the dict."""
    pc = make_project_config(bv_cfg={"env_up_command": "make up"})
    env = resolve_browser_env(pc, "proj", "F-00001")
    assert env is not None
    assert "IW_BROWSER_E2E_USER" not in env
    assert "IW_BROWSER_E2E_PASSWORD" not in env


# ---------------------------------------------------------------------------
# render_prompt_substitutions
# ---------------------------------------------------------------------------


def test_render_known_placeholder_replaced() -> None:
    env = {"IW_BROWSER_BASE_URL": "http://localhost:3137"}
    result = render_prompt_substitutions("Open {{IW_BROWSER_BASE_URL}} in browser.", env)
    assert result == "Open http://localhost:3137 in browser."


def test_render_unknown_placeholder_left_untouched() -> None:
    env = {"IW_BROWSER_BASE_URL": "http://localhost:3137"}
    result = render_prompt_substitutions("Value: {{UNKNOWN_VAR}}", env)
    assert result == "Value: {{UNKNOWN_VAR}}"


def test_render_multiple_placeholders() -> None:
    env = {
        "IW_BROWSER_BASE_URL": "http://localhost:3137",
        "IW_BROWSER_E2E_USER": "admin@example.com",
        "IW_BROWSER_E2E_PASSWORD": "pass123",
    }
    prompt = (
        "URL={{IW_BROWSER_BASE_URL}} user={{IW_BROWSER_E2E_USER}} pw={{IW_BROWSER_E2E_PASSWORD}}"
    )
    result = render_prompt_substitutions(prompt, env)
    assert "http://localhost:3137" in result
    assert "admin@example.com" in result
    assert "pass123" in result


def test_render_no_placeholders_unchanged() -> None:
    text = "No placeholders here."
    result = render_prompt_substitutions(text, {})
    assert result == text


def test_render_known_placeholder_missing_from_env_left_untouched() -> None:
    """A known placeholder name that isn't in the env dict is left as-is."""
    env: dict[str, str] = {}
    result = render_prompt_substitutions("Visit {{IW_BROWSER_BASE_URL}}", env)
    assert result == "Visit {{IW_BROWSER_BASE_URL}}"


# ---------------------------------------------------------------------------
# run_env_up_hook — opt-out
# ---------------------------------------------------------------------------


def test_run_env_up_hook_no_config_returns_true(tmp_path: Path) -> None:
    """No env_up_command → (True, empty path) — feature is opt-in."""
    pc = make_project_config(bv_cfg={})
    success, log_path = run_env_up_hook(pc, str(tmp_path), {}, "F-00001", "S01")
    assert success is True
    assert log_path == Path()


def test_run_env_up_hook_no_browser_cfg_returns_true(tmp_path: Path) -> None:
    """No browser_verification config at all → (True, empty path)."""
    pc = make_project_config(bv_cfg=None)
    success, log_path = run_env_up_hook(pc, str(tmp_path), {}, "F-00001", "S01")
    assert success is True


# ---------------------------------------------------------------------------
# run_env_up_hook — success
# ---------------------------------------------------------------------------


def test_run_env_up_hook_success(tmp_path: Path) -> None:
    pc = make_project_config(bv_cfg={"env_up_command": "/bin/true"})
    success, log_path = run_env_up_hook(pc, str(tmp_path), {}, "F-00001", "S01")
    assert success is True
    assert log_path.name == "F-00001_S01_browser_env_up.log"


# ---------------------------------------------------------------------------
# run_env_up_hook — failure cases
# ---------------------------------------------------------------------------


def test_run_env_up_hook_nonzero_exit_returns_false(tmp_path: Path) -> None:
    pc = make_project_config(bv_cfg={"env_up_command": "/bin/false"})
    success, log_path = run_env_up_hook(pc, str(tmp_path), {}, "F-00001", "S01")
    assert success is False
    assert log_path.exists()


def test_run_env_up_hook_timeout_returns_false(tmp_path: Path) -> None:
    """SubprocessTimeoutExpired → (False, log_path)."""
    pc = make_project_config(bv_cfg={"env_up_command": "sleep 9999"})
    with patch(
        "orch.daemon.browser_env.subprocess.run",
        side_effect=subprocess.TimeoutExpired("sleep", 600),
    ):
        success, log_path = run_env_up_hook(pc, str(tmp_path), {}, "F-00001", "S01")
    assert success is False


def test_run_env_up_hook_exception_returns_false(tmp_path: Path) -> None:
    """Arbitrary exception → (False, log_path)."""
    pc = make_project_config(bv_cfg={"env_up_command": "make up"})
    with patch("orch.daemon.browser_env.subprocess.run", side_effect=OSError("command not found")):
        success, log_path = run_env_up_hook(pc, str(tmp_path), {}, "F-00001", "S01")
    assert success is False


# ---------------------------------------------------------------------------
# run_env_down_hook — never raises
# ---------------------------------------------------------------------------


def test_run_env_down_hook_no_config_is_noop(tmp_path: Path) -> None:
    """No env_down_command → silently does nothing."""
    pc = make_project_config(bv_cfg={})
    run_env_down_hook(pc, str(tmp_path), {}, "F-00001", "S01")  # must not raise


def test_run_env_down_hook_success(tmp_path: Path) -> None:
    pc = make_project_config(bv_cfg={"env_up_command": "make up", "env_down_command": "/bin/true"})
    run_env_down_hook(pc, str(tmp_path), {}, "F-00001", "S01")  # must not raise


def test_run_env_down_hook_nonzero_exit_does_not_raise(tmp_path: Path) -> None:
    """Non-zero exit from env_down command → WARNING logged, no exception."""
    pc = make_project_config(bv_cfg={"env_up_command": "make up", "env_down_command": "/bin/false"})
    run_env_down_hook(pc, str(tmp_path), {}, "F-00001", "S01")  # must not raise


def test_run_env_down_hook_timeout_does_not_raise(tmp_path: Path) -> None:
    pc = make_project_config(bv_cfg={"env_up_command": "make up", "env_down_command": "sleep 9999"})
    with patch(
        "orch.daemon.browser_env.subprocess.run",
        side_effect=subprocess.TimeoutExpired("sleep", 300),
    ):
        run_env_down_hook(pc, str(tmp_path), {}, "F-00001", "S01")  # must not raise


def test_run_env_down_hook_exception_does_not_raise(tmp_path: Path) -> None:
    pc = make_project_config(bv_cfg={"env_up_command": "make up", "env_down_command": "make down"})
    with patch("orch.daemon.browser_env.subprocess.run", side_effect=OSError("docker not found")):
        run_env_down_hook(pc, str(tmp_path), {}, "F-00001", "S01")  # must not raise
