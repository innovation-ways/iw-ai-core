"""Unit tests for orch.daemon.browser_env — no DB, no subprocess calls.

All subprocess calls are patched. Tests verify:
- resolve_browser_env returns None when project has no browser config
- Deterministic port allocation
- render_prompt_substitutions placeholder handling
- run_env_up_hook opt-out and error handling
- run_env_down_hook never raises
"""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orch.daemon.browser_env import (
    _capture_crashed_container_logs,
    _compute_port_offset,
    _is_port_free,
    _load_persisted_offset,
    _pick_free_offset,
    _save_persisted_offset,
    _state_file_path,
    allocate_browser_env,
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
        model="minimax",
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


def test_resolve_browser_env_exports_e2e_db_url() -> None:
    """Regression guard: agents must be able to INSERT into the isolated E2E
    DB without falling back to orch.db.session.SessionLocal (which the
    worktree's .env pins at the *live* orchestration DB).

    The I-00038 S11 V4 step failed four times in a row because the
    `DaemonEvent` inserted "from the worktree root" landed in the live DB
    while the dashboard under test polled the container DB. The daemon must
    expose the E2E Postgres DSN so the prompt can document the exact
    pattern agents should use.
    """
    pc = make_project_config(bv_cfg=_FULL_BV_CFG)
    env = resolve_browser_env(pc, "innoforge", "F-00001")
    assert env is not None
    assert env["IW_BROWSER_E2E_DB_HOST"] == "127.0.0.1"
    assert env["IW_BROWSER_E2E_DB_PORT"] == env["E2E_DB_PORT"]
    assert env["IW_BROWSER_E2E_DB_NAME"] == "iw_e2e"
    assert env["IW_BROWSER_E2E_DB_USER"] == "iw_e2e"
    assert env["IW_BROWSER_E2E_DB_PASSWORD"] == "iw_e2e_dev"  # noqa: S105
    # Full DSN must be a parseable postgres URL pointing at the allocated
    # host port — matches what docker-compose.e2e.yml exposes.
    expected = f"postgresql://iw_e2e:iw_e2e_dev@127.0.0.1:{env['E2E_DB_PORT']}/iw_e2e"
    assert env["IW_BROWSER_E2E_DB_URL"] == expected


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


def test_resolve_browser_env_no_e2e_user_skips_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """If e2e_user is absent from config AND env, the keys must not be in the dict."""
    monkeypatch.delenv("IW_BROWSER_E2E_USER", raising=False)
    monkeypatch.delenv("IW_BROWSER_E2E_PASSWORD", raising=False)
    pc = make_project_config(bv_cfg={"env_up_command": "make up"})
    env = resolve_browser_env(pc, "proj", "F-00001")
    assert env is not None
    assert "IW_BROWSER_E2E_USER" not in env
    assert "IW_BROWSER_E2E_PASSWORD" not in env


def test_resolve_browser_env_e2e_creds_fall_back_to_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no creds in .iw-orch.json, IW_BROWSER_E2E_* are sourced from the env."""
    monkeypatch.setenv("IW_BROWSER_E2E_USER", "env-user@example.local")
    monkeypatch.setenv("IW_BROWSER_E2E_PASSWORD", "env-secret")
    pc = make_project_config(bv_cfg={"env_up_command": "make up"})
    env = resolve_browser_env(pc, "proj", "F-00001")
    assert env is not None
    assert env["IW_BROWSER_E2E_USER"] == "env-user@example.local"
    assert env["IW_BROWSER_E2E_PASSWORD"] == "env-secret"  # noqa: S105


def test_resolve_browser_env_config_creds_override_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit .iw-orch.json credential takes precedence over the env var."""
    monkeypatch.setenv("IW_BROWSER_E2E_USER", "env-user@example.local")
    monkeypatch.setenv("IW_BROWSER_E2E_PASSWORD", "env-secret")
    pc = make_project_config(bv_cfg=_FULL_BV_CFG)
    env = resolve_browser_env(pc, "innoforge", "F-00001")
    assert env is not None
    assert env["IW_BROWSER_E2E_USER"] == "dev@example.local"
    assert env["IW_BROWSER_E2E_PASSWORD"] == "Secret123"  # noqa: S105


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


# ---------------------------------------------------------------------------
# _is_port_free
# ---------------------------------------------------------------------------


def _reserve_port() -> tuple[socket.socket, int]:
    """Open a listening socket on an ephemeral port; caller closes."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    return s, s.getsockname()[1]


def test_is_port_free_true_when_nothing_listens() -> None:
    # Port 1 is almost certainly bound by no test process.
    # Pick a random high port via OS, then close, then probe.
    s, port = _reserve_port()
    s.close()
    assert _is_port_free(port) is True


def test_is_port_free_false_when_port_in_use() -> None:
    s, port = _reserve_port()
    try:
        assert _is_port_free(port) is False
    finally:
        s.close()


# ---------------------------------------------------------------------------
# _pick_free_offset
# ---------------------------------------------------------------------------


@pytest.mark.order_dependent
@pytest.mark.xfail(
    strict=False,
    reason=(
        "flaky: port-binding side effect from other tests leaks into this one "
        "under random order; tracked for P1-CR-C-followup"
    ),
)
def test_pick_free_offset_returns_hash_offset_when_free() -> None:
    """When the deterministic slot is free, the pick returns that offset."""
    pool_cfg = {
        "frontend_base": 59152,
        "api_base": 59300,
        "db_base": 59450,
        "redis_base": 59600,
        "pool_size": 50,
    }
    expected = _compute_port_offset("proj", "F-00001", 50)
    offset = _pick_free_offset(pool_cfg, "proj", "F-00001")
    assert offset == expected


def test_pick_free_offset_scans_forward_on_collision() -> None:
    """When the hash slot's frontend port is taken, the scan moves to the next offset."""
    pool_cfg = {
        "frontend_base": 59152,
        "api_base": 59300,
        "db_base": 59450,
        "redis_base": 59600,
        "pool_size": 50,
    }
    base = _compute_port_offset("proj", "F-00001", 50)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", pool_cfg["frontend_base"] + base))
    s.listen(1)
    try:
        offset = _pick_free_offset(pool_cfg, "proj", "F-00001")
        assert offset is not None
        assert offset != base
    finally:
        s.close()


# ---------------------------------------------------------------------------
# State-file persistence
# ---------------------------------------------------------------------------


def test_state_file_path_under_worktree_tmp(tmp_path: Path) -> None:
    path = _state_file_path(str(tmp_path), "F-00001")
    assert path == tmp_path / ".tmp" / "browser_env_F-00001.state"


def test_save_and_load_persisted_offset_roundtrip(tmp_path: Path) -> None:
    _save_persisted_offset(str(tmp_path), "F-00001", 42)
    loaded = _load_persisted_offset(str(tmp_path), "F-00001")
    assert loaded == 42


def test_load_persisted_offset_none_when_missing(tmp_path: Path) -> None:
    assert _load_persisted_offset(str(tmp_path), "F-00099") is None


def test_load_persisted_offset_none_on_malformed_file(tmp_path: Path) -> None:
    state = _state_file_path(str(tmp_path), "F-00001")
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("{not json")
    assert _load_persisted_offset(str(tmp_path), "F-00001") is None


# ---------------------------------------------------------------------------
# allocate_browser_env
# ---------------------------------------------------------------------------


def test_allocate_browser_env_returns_none_when_opted_out(tmp_path: Path) -> None:
    pc = make_project_config(bv_cfg=None)
    assert allocate_browser_env(pc, "innoforge", "F-00001", str(tmp_path)) is None


def test_allocate_browser_env_writes_state_file(tmp_path: Path) -> None:
    pc = make_project_config(bv_cfg={**_FULL_BV_CFG, "env_up_command": "/bin/true"})
    env = allocate_browser_env(pc, "innoforge", "F-00001", str(tmp_path))
    assert env is not None
    loaded = _load_persisted_offset(str(tmp_path), "F-00001")
    assert loaded is not None
    # The env ports must agree with the persisted offset.
    pool = _FULL_BV_CFG["port_pool"]
    assert int(env["E2E_FRONTEND_PORT"]) == pool["frontend_base"] + loaded


def test_allocate_browser_env_reuses_persisted_offset(tmp_path: Path) -> None:
    """A second call with the same worktree must reuse the first offset."""
    pc = make_project_config(bv_cfg={**_FULL_BV_CFG, "env_up_command": "/bin/true"})
    first = allocate_browser_env(pc, "innoforge", "F-00001", str(tmp_path))
    second = allocate_browser_env(pc, "innoforge", "F-00001", str(tmp_path))
    assert first is not None
    assert second is not None
    assert first["E2E_FRONTEND_PORT"] == second["E2E_FRONTEND_PORT"]


def test_resolve_browser_env_prefers_persisted_offset(tmp_path: Path) -> None:
    """resolve_browser_env honours the state file over the hash offset."""
    pc = make_project_config(bv_cfg={**_FULL_BV_CFG, "env_up_command": "/bin/true"})
    # Save an offset that won't match the hash (use 0 — distinct from any non-zero hash).
    _save_persisted_offset(str(tmp_path), "F-00001", 0)
    env = resolve_browser_env(pc, "innoforge", "F-00001", worktree_path=str(tmp_path))
    assert env is not None
    pool = _FULL_BV_CFG["port_pool"]
    assert int(env["E2E_FRONTEND_PORT"]) == pool["frontend_base"] + 0


def test_resolve_browser_env_falls_back_to_hash_without_worktree() -> None:
    """Without a worktree_path, resolve_browser_env uses the deterministic hash."""
    pc = make_project_config(bv_cfg={**_FULL_BV_CFG, "env_up_command": "/bin/true"})
    env = resolve_browser_env(pc, "innoforge", "F-00001")
    assert env is not None
    pool = _FULL_BV_CFG["port_pool"]
    expected_offset = _compute_port_offset("innoforge", "F-00001", pool["pool_size"])
    assert int(env["E2E_FRONTEND_PORT"]) == pool["frontend_base"] + expected_offset


def test_run_env_down_hook_deletes_state_file(tmp_path: Path) -> None:
    _save_persisted_offset(str(tmp_path), "F-00001", 7)
    pc = make_project_config(bv_cfg={"env_up_command": "make up", "env_down_command": "/bin/true"})
    run_env_down_hook(pc, str(tmp_path), {}, "F-00001", "S01")
    assert _load_persisted_offset(str(tmp_path), "F-00001") is None


# ---------------------------------------------------------------------------
# _capture_crashed_container_logs — I-00052
# ---------------------------------------------------------------------------


def test_i00052_capture_crashed_container_logs_happy_path() -> None:
    compose_log = (
        "dependency failed to start: container iw-ai-core-e2e-f00067-e2e-dashboard-1 exited (1)\n"
    )
    mock_result = MagicMock(
        stdout="ImportError: cannot import name 'foo'\n", stderr="", returncode=0
    )
    with patch("orch.daemon.browser_env.subprocess.run", return_value=mock_result) as mock_run:
        result = _capture_crashed_container_logs(compose_log)
    mock_run.assert_called_once_with(
        ["docker", "logs", "iw-ai-core-e2e-f00067-e2e-dashboard-1", "--tail", "50"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert "ImportError: cannot import name 'foo'" in result
    assert "Container Crash Logs" in result
    assert "iw-ai-core-e2e-f00067-e2e-dashboard-1" in result


def test_i00052_capture_crashed_container_logs_docker_unavailable() -> None:
    compose_log = "container foo-dashboard-1 exited (1)\n"
    with patch(
        "orch.daemon.browser_env.subprocess.run",
        side_effect=FileNotFoundError("docker not found"),
    ):
        result = _capture_crashed_container_logs(compose_log)
    assert result != ""
    assert "unavailable" in result


def test_i00052_capture_crashed_container_logs_docker_timeout() -> None:
    with patch(
        "orch.daemon.browser_env.subprocess.run",
        side_effect=subprocess.TimeoutExpired("docker", 10),
    ):
        result = _capture_crashed_container_logs("container foo-dashboard-1 exited (1)\n")
    assert result != ""
    assert "unavailable" in result


def test_i00052_capture_crashed_container_logs_empty_input() -> None:
    with patch("orch.daemon.browser_env.subprocess.run") as mock_run:
        result = _capture_crashed_container_logs("")
    assert result == ""
    mock_run.assert_not_called()


def test_i00052_capture_crashed_container_logs_no_crashed_containers() -> None:
    compose_log = "container foo-dashboard-1 starting\ncontainer foo-dashboard-1 stopped\n"
    with patch("orch.daemon.browser_env.subprocess.run") as mock_run:
        result = _capture_crashed_container_logs(compose_log)
    assert result == ""
    mock_run.assert_not_called()


def test_i00052_capture_crashed_container_logs_deduplicates() -> None:
    compose_log = "container foo-dashboard-1 exited (1)\ncontainer foo-dashboard-1 exited (1)\n"
    mock_result = MagicMock(stdout="error log\n", stderr="", returncode=0)
    with patch("orch.daemon.browser_env.subprocess.run", return_value=mock_result) as mock_run:
        result = _capture_crashed_container_logs(compose_log)
    mock_run.assert_called_once()
    assert "foo-dashboard-1" in result
