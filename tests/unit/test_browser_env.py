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
    _E2E_DASHBOARD_SERVICE,
    _apply_per_item_fixtures,
    _capture_crashed_container_logs,
    _compute_port_offset,
    _is_port_free,
    _load_persisted_offset,
    _pick_free_offset,
    _save_persisted_offset,
    _state_file_path,
    allocate_browser_env,
    fixture_apply_service,
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
    """Return make project config."""
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
    "e2e_user": "dev@example.com",
    "e2e_password": "Secret123",
    "compose_project_prefix": "innoforge-e2e",
}


# ---------------------------------------------------------------------------
# is_browser_verification_step
# ---------------------------------------------------------------------------


def test_is_browser_verification_step_enum() -> None:
    """Verifies that is browser verification step enum."""
    assert is_browser_verification_step(StepType.browser_verification) is True


def test_is_browser_verification_step_string() -> None:
    """Verifies that is browser verification step string."""
    assert is_browser_verification_step("browser_verification") is True


def test_is_browser_verification_step_other_enum() -> None:
    """Verifies that is browser verification step other enum."""
    assert is_browser_verification_step(StepType.implementation) is False


def test_is_browser_verification_step_other_string() -> None:
    """Verifies that is browser verification step other string."""
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
    """Verifies that resolve browser env returns expected keys."""
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
    """Verifies that resolve browser env base url substituted."""
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
    monkeypatch.setenv("IW_BROWSER_E2E_USER", "env-user@example.com")
    monkeypatch.setenv("IW_BROWSER_E2E_PASSWORD", "env-secret")
    pc = make_project_config(bv_cfg={"env_up_command": "make up"})
    env = resolve_browser_env(pc, "proj", "F-00001")
    assert env is not None
    assert env["IW_BROWSER_E2E_USER"] == "env-user@example.com"
    assert env["IW_BROWSER_E2E_PASSWORD"] == "env-secret"  # noqa: S105


def test_resolve_browser_env_config_creds_override_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit .iw-orch.json credential takes precedence over the env var."""
    monkeypatch.setenv("IW_BROWSER_E2E_USER", "env-user@example.com")
    monkeypatch.setenv("IW_BROWSER_E2E_PASSWORD", "env-secret")
    pc = make_project_config(bv_cfg=_FULL_BV_CFG)
    env = resolve_browser_env(pc, "innoforge", "F-00001")
    assert env is not None
    assert env["IW_BROWSER_E2E_USER"] == "dev@example.com"
    assert env["IW_BROWSER_E2E_PASSWORD"] == "Secret123"  # noqa: S105


# ---------------------------------------------------------------------------
# render_prompt_substitutions
# ---------------------------------------------------------------------------


def test_render_known_placeholder_replaced() -> None:
    """Verifies that render known placeholder replaced."""
    env = {"IW_BROWSER_BASE_URL": "http://localhost:3137"}
    result = render_prompt_substitutions("Open {{IW_BROWSER_BASE_URL}} in browser.", env)
    assert result == "Open http://localhost:3137 in browser."


def test_render_unknown_placeholder_left_untouched() -> None:
    """Verifies that render unknown placeholder left untouched."""
    env = {"IW_BROWSER_BASE_URL": "http://localhost:3137"}
    result = render_prompt_substitutions("Value: {{UNKNOWN_VAR}}", env)
    assert result == "Value: {{UNKNOWN_VAR}}"


def test_render_multiple_placeholders() -> None:
    """Verifies that render multiple placeholders."""
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
    """Verifies that render no placeholders unchanged."""
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
    """Verifies that run env up hook success."""
    pc = make_project_config(bv_cfg={"env_up_command": "/bin/true"})
    success, log_path = run_env_up_hook(pc, str(tmp_path), {}, "F-00001", "S01")
    assert success is True
    assert log_path.name == "F-00001_S01_browser_env_up.log"


# ---------------------------------------------------------------------------
# run_env_up_hook — failure cases
# ---------------------------------------------------------------------------


def test_run_env_up_hook_nonzero_exit_returns_false(tmp_path: Path) -> None:
    """Verifies that run env up hook nonzero exit returns false."""
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


def test_run_env_down_hook_no_config_is_noop(tmp_path: Path) -> None:  # noqa: E501  # assertion-scanner
    """No env_down_command → silently does nothing."""
    pc = make_project_config(bv_cfg={})
    run_env_down_hook(pc, str(tmp_path), {}, "F-00001", "S01")  # must not raise


def test_run_env_down_hook_success(tmp_path: Path) -> None:  # noqa: E501  # assertion-scanner
    """Verifies that run env down hook success."""
    pc = make_project_config(bv_cfg={"env_up_command": "make up", "env_down_command": "/bin/true"})
    run_env_down_hook(pc, str(tmp_path), {}, "F-00001", "S01")  # must not raise


def test_run_env_down_hook_nonzero_exit_does_not_raise(tmp_path: Path) -> None:  # noqa: E501  # assertion-scanner
    """Non-zero exit from env_down command → WARNING logged, no exception."""
    pc = make_project_config(bv_cfg={"env_up_command": "make up", "env_down_command": "/bin/false"})
    run_env_down_hook(pc, str(tmp_path), {}, "F-00001", "S01")  # must not raise


def test_run_env_down_hook_timeout_does_not_raise(tmp_path: Path) -> None:  # noqa: E501  # assertion-scanner
    """Verifies that run env down hook timeout does not raise."""
    pc = make_project_config(bv_cfg={"env_up_command": "make up", "env_down_command": "sleep 9999"})
    with patch(
        "orch.daemon.browser_env.subprocess.run",
        side_effect=subprocess.TimeoutExpired("sleep", 300),
    ):
        run_env_down_hook(pc, str(tmp_path), {}, "F-00001", "S01")  # must not raise


def test_run_env_down_hook_exception_does_not_raise(tmp_path: Path) -> None:  # noqa: E501  # assertion-scanner
    """Verifies that run env down hook exception does not raise."""
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
    """Verifies that is port free true when nothing listens."""
    # Port 1 is almost certainly bound by no test process.
    # Pick a random high port via OS, then close, then probe.
    s, port = _reserve_port()
    s.close()
    assert _is_port_free(port) is True


def test_is_port_free_false_when_port_in_use() -> None:
    """Verifies that is port free false when port in use."""
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


@pytest.mark.order_dependent
@pytest.mark.xfail(
    strict=False,
    reason=(
        "flaky: port-binding side effect from other tests leaks into this one "
        "under random order; tracked for P1-CR-C-followup"
    ),
)
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
    """Verifies that state file path under worktree tmp."""
    path = _state_file_path(str(tmp_path), "F-00001")
    assert path == tmp_path / ".tmp" / "browser_env_F-00001.state"


def test_save_and_load_persisted_offset_roundtrip(tmp_path: Path) -> None:
    """Verifies that save and load persisted offset roundtrip."""
    _save_persisted_offset(str(tmp_path), "F-00001", 42)
    loaded = _load_persisted_offset(str(tmp_path), "F-00001")
    assert loaded == 42


def test_load_persisted_offset_none_when_missing(tmp_path: Path) -> None:
    """Verifies that load persisted offset none when missing."""
    assert _load_persisted_offset(str(tmp_path), "F-00099") is None


def test_load_persisted_offset_none_on_malformed_file(tmp_path: Path) -> None:
    """Verifies that load persisted offset none on malformed file."""
    state = _state_file_path(str(tmp_path), "F-00001")
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("{not json")
    assert _load_persisted_offset(str(tmp_path), "F-00001") is None


# ---------------------------------------------------------------------------
# allocate_browser_env
# ---------------------------------------------------------------------------


def test_allocate_browser_env_returns_none_when_opted_out(tmp_path: Path) -> None:
    """Verifies that allocate browser env returns none when opted out."""
    pc = make_project_config(bv_cfg=None)
    assert allocate_browser_env(pc, "innoforge", "F-00001", str(tmp_path)) is None


def test_allocate_browser_env_writes_state_file(tmp_path: Path) -> None:
    """Verifies that allocate browser env writes state file."""
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
    """Verifies that run env down hook deletes state file."""
    _save_persisted_offset(str(tmp_path), "F-00001", 7)
    pc = make_project_config(bv_cfg={"env_up_command": "make up", "env_down_command": "/bin/true"})
    run_env_down_hook(pc, str(tmp_path), {}, "F-00001", "S01")
    assert _load_persisted_offset(str(tmp_path), "F-00001") is None


# ---------------------------------------------------------------------------
# _capture_crashed_container_logs — I-00052
# ---------------------------------------------------------------------------


def test_i00052_capture_crashed_container_logs_happy_path() -> None:
    """Verifies that i00052 capture crashed container logs happy path."""
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
    """Verifies that i00052 capture crashed container logs docker unavailable."""
    compose_log = "container foo-dashboard-1 exited (1)\n"
    with patch(
        "orch.daemon.browser_env.subprocess.run",
        side_effect=FileNotFoundError("docker not found"),
    ):
        result = _capture_crashed_container_logs(compose_log)
    assert result != ""
    assert "unavailable" in result


def test_i00052_capture_crashed_container_logs_docker_timeout() -> None:
    """Verifies that i00052 capture crashed container logs docker timeout."""
    with patch(
        "orch.daemon.browser_env.subprocess.run",
        side_effect=subprocess.TimeoutExpired("docker", 10),
    ):
        result = _capture_crashed_container_logs("container foo-dashboard-1 exited (1)\n")
    assert result != ""
    assert "unavailable" in result


def test_i00052_capture_crashed_container_logs_empty_input() -> None:
    """Verifies that i00052 capture crashed container logs empty input."""
    with patch("orch.daemon.browser_env.subprocess.run") as mock_run:
        result = _capture_crashed_container_logs("")
    assert result == ""
    mock_run.assert_not_called()


def test_i00052_capture_crashed_container_logs_no_crashed_containers() -> None:
    """Verifies that i00052 capture crashed container logs no crashed containers."""
    compose_log = "container foo-dashboard-1 starting\ncontainer foo-dashboard-1 stopped\n"
    with patch("orch.daemon.browser_env.subprocess.run") as mock_run:
        result = _capture_crashed_container_logs(compose_log)
    assert result == ""
    mock_run.assert_not_called()


def test_i00052_capture_crashed_container_logs_deduplicates() -> None:
    """Verifies that i00052 capture crashed container logs deduplicates."""
    compose_log = "container foo-dashboard-1 exited (1)\ncontainer foo-dashboard-1 exited (1)\n"
    mock_result = MagicMock(stdout="error log\n", stderr="", returncode=0)
    with patch("orch.daemon.browser_env.subprocess.run", return_value=mock_result) as mock_run:
        result = _capture_crashed_container_logs(compose_log)
    mock_run.assert_called_once()
    assert "foo-dashboard-1" in result


# ---------------------------------------------------------------------------
# CR-00100 — fixture_apply_service resolver
# ---------------------------------------------------------------------------


def test_fixture_apply_service_default_when_no_browser_verification_block() -> None:
    """Resolver returns the default when no browser_verification block is configured."""
    pc = make_project_config(bv_cfg=None)
    assert fixture_apply_service(pc) == _E2E_DASHBOARD_SERVICE
    assert fixture_apply_service(pc) == "e2e-dashboard"


def test_fixture_apply_service_default_when_key_missing() -> None:
    """Verifies the resolver falls back to the default when the key is absent from the block."""
    pc = make_project_config(bv_cfg={"env_up_command": "make e2e-up"})
    assert fixture_apply_service(pc) == "e2e-dashboard"


def test_fixture_apply_service_returns_configured_value() -> None:
    """Verifies the resolver returns the configured value when present."""
    bv_cfg = {"env_up_command": "make e2e-up", "fixture_apply_service": "api"}
    pc = make_project_config(bv_cfg=bv_cfg)
    assert fixture_apply_service(pc) == "api"


def test_fixture_apply_service_falls_back_when_empty_string() -> None:
    """An empty string is treated as unset and falls back to the default."""
    bv_cfg = {"env_up_command": "make e2e-up", "fixture_apply_service": ""}
    pc = make_project_config(bv_cfg=bv_cfg)
    assert fixture_apply_service(pc) == "e2e-dashboard"


def test_fixture_apply_service_falls_back_when_non_string() -> None:
    """Non-string values (e.g. int, list, bool) fall back to the default."""
    for bad in (42, True, ["api"], {"name": "api"}, None):
        bv_cfg = {"env_up_command": "make e2e-up", "fixture_apply_service": bad}
        pc = make_project_config(bv_cfg=bv_cfg)
        assert fixture_apply_service(pc) == "e2e-dashboard", f"unexpected for {bad!r}"


# ---------------------------------------------------------------------------
# CR-00100 — _apply_per_item_fixtures uses the configured service name
# ---------------------------------------------------------------------------


def _write_fixtures(worktree: Path, item_id: str) -> None:
    """Create a one-fixture e2e_fixtures dir so the apply path actually shells out."""
    fx_dir = worktree / "ai-dev" / "active" / item_id / "e2e_fixtures"
    fx_dir.mkdir(parents=True, exist_ok=True)
    (fx_dir / "01_seed.py").write_text("def seed(db):  # noqa: ARG001\n    pass\n")


def test_apply_per_item_fixtures_default_uses_e2e_dashboard_service(tmp_path: Path) -> None:
    """Default service_name is _E2E_DASHBOARD_SERVICE ('e2e-dashboard')."""
    item_id = "F-00099"
    _write_fixtures(tmp_path, item_id)
    mock_result = MagicMock(stdout="", stderr="", returncode=0)
    with patch("orch.daemon.browser_env.subprocess.run", return_value=mock_result) as mock_run:
        _apply_per_item_fixtures(item_id, "iw-ai-core-e2e-f00099", str(tmp_path))
    assert mock_run.call_count == 1
    argv = mock_run.call_args[0][0]
    # The service name appears between '-T' and 'uv'.
    t_idx = argv.index("-T")
    assert argv[t_idx + 1] == "e2e-dashboard"


def test_apply_per_item_fixtures_uses_overridden_service_name(tmp_path: Path) -> None:
    """A non-default service_name is what the docker compose exec targets."""
    item_id = "F-00099"
    _write_fixtures(tmp_path, item_id)
    mock_result = MagicMock(stdout="", stderr="", returncode=0)
    with patch("orch.daemon.browser_env.subprocess.run", return_value=mock_result) as mock_run:
        _apply_per_item_fixtures(
            item_id,
            "iw-rag-e2e-f00099",
            str(tmp_path),
            service_name="api",
        )
    assert mock_run.call_count == 1
    argv = mock_run.call_args[0][0]
    t_idx = argv.index("-T")
    assert argv[t_idx + 1] == "api"
    # And the rest of the argv (uv run python scripts/e2e_apply_item_fixtures.py <item>)
    # is unchanged.
    expected_tail = ["uv", "run", "python", "scripts/e2e_apply_item_fixtures.py", item_id]
    assert argv[t_idx + 2 :] == expected_tail


def test_apply_per_item_fixtures_unchanged_argv_for_default(tmp_path: Path) -> None:
    """With the default service_name the built argv is byte-for-byte what it was pre-CR."""
    item_id = "F-00099"
    _write_fixtures(tmp_path, item_id)
    mock_result = MagicMock(stdout="", stderr="", returncode=0)
    with patch("orch.daemon.browser_env.subprocess.run", return_value=mock_result) as mock_run:
        _apply_per_item_fixtures(item_id, "iw-ai-core-e2e-f00099", str(tmp_path))
    argv = mock_run.call_args[0][0]
    assert argv == [
        "docker",
        "compose",
        "-p",
        "iw-ai-core-e2e-f00099",
        "exec",
        "-T",
        "e2e-dashboard",
        "uv",
        "run",
        "python",
        "scripts/e2e_apply_item_fixtures.py",
        item_id,
    ]


def test_apply_per_item_fixtures_no_fixtures_dir_skips_exec(tmp_path: Path) -> None:
    """Fast path: no e2e_fixtures directory → no subprocess.run call, regardless of service_name."""
    mock_result = MagicMock(stdout="", stderr="", returncode=0)
    with patch("orch.daemon.browser_env.subprocess.run", return_value=mock_result) as mock_run:
        result = _apply_per_item_fixtures(
            "F-00099",
            "iw-ai-core-e2e-f00099",
            str(tmp_path),
            service_name="api",
        )
    # Fast path returns None silently and never shells out — verify both.
    assert result is None
    mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# CR-00100 — _apply_per_item_fixtures: extra argv-contract assertions
# ---------------------------------------------------------------------------
# The tests above pin the existence of the new behaviour. The tests below
# pin the *exact* argv shape so a regression that keeps the argv in the right
# overall structure but slips the wrong service token into the slot is still
# caught. The "BAD" assertion (`assert "e2e-dashboard" in cmd`) would survive
# that regression because the substring matches elsewhere in compose logging;
# these tests assert the token at its exact argv position.


def test_apply_per_item_fixtures_configured_argv_excludes_default(tmp_path: Path) -> None:
    """AC2 strengthened: configured service='api' lands in the argv AND 'e2e-dashboard' is absent.

    A future bug that injects 'e2e-dashboard' unconditionally — e.g. an
    internal helper hardcoding the default — must not survive this test.
    """
    item_id = "F-00099"
    _write_fixtures(tmp_path, item_id)
    mock_result = MagicMock(stdout="", stderr="", returncode=0)
    with patch("orch.daemon.browser_env.subprocess.run", return_value=mock_result) as mock_run:
        _apply_per_item_fixtures(
            item_id,
            "iw-rag-e2e-f00099",
            str(tmp_path),
            service_name="api",
        )
    assert mock_run.call_count == 1
    argv = mock_run.call_args[0][0]
    # 1) The exact token is 'api' at the post-'-T' position.
    assert argv[argv.index("-T") + 1] == "api"
    # 2) The default service name MUST NOT appear anywhere in the argv
    #    (not even as a substring of another token) — pins the AC2 invariant.
    assert "e2e-dashboard" not in argv


def test_apply_per_item_fixtures_default_service_token_at_exact_position(tmp_path: Path) -> None:
    """AC1 strengthened: default service token is exactly 'e2e-dashboard' at the '-T' position.

    Belt-and-braces for the default case: the index-based check is repeated
    here as a dedicated test so a future mutation that flips just the default
    path is caught independently of the configured-service test above.
    """
    item_id = "F-00099"
    _write_fixtures(tmp_path, item_id)
    mock_result = MagicMock(stdout="", stderr="", returncode=0)
    with patch("orch.daemon.browser_env.subprocess.run", return_value=mock_result) as mock_run:
        _apply_per_item_fixtures(item_id, "iw-ai-core-e2e-f00099", str(tmp_path))
    argv = mock_run.call_args[0][0]
    assert argv[argv.index("-T") + 1] == "e2e-dashboard"
    # And the default value matches the module-level constant — guards against
    # a future rename that forgets to update the test fixture.
    assert argv[argv.index("-T") + 1] == _E2E_DASHBOARD_SERVICE


def test_apply_per_item_fixtures_no_dir_skips_exec_with_default_service(tmp_path: Path) -> None:
    """AC3 (default service): no e2e_fixtures dir → subprocess seam never invoked.

    The default `service_name` parameter is `_E2E_DASHBOARD_SERVICE`; the
    fast-path check must trip *before* the service-name ever reaches the
    argv, regardless of which service was going to be used.
    """
    mock_result = MagicMock(stdout="", stderr="", returncode=0)
    with patch("orch.daemon.browser_env.subprocess.run", return_value=mock_result) as mock_run:
        result = _apply_per_item_fixtures(
            "F-00099",
            "iw-ai-core-e2e-f00099",
            str(tmp_path),
            # service_name omitted — falls through to the default
        )
    assert result is None
    mock_run.assert_not_called()


def test_apply_per_item_fixtures_empty_dir_skips_exec_with_default_service(tmp_path: Path) -> None:
    """AC3 (default service): empty e2e_fixtures dir → subprocess seam never invoked.

    The fast-path also short-circuits when the directory exists but contains
    no non-private ``*.py`` files. Verified for the default service.
    """
    fx_dir = tmp_path / "ai-dev" / "active" / "F-00099" / "e2e_fixtures"
    fx_dir.mkdir(parents=True, exist_ok=True)
    # The directory exists but has no fixture files (not even a private
    # underscore-prefixed one — those are filtered out too).
    mock_result = MagicMock(stdout="", stderr="", returncode=0)
    with patch("orch.daemon.browser_env.subprocess.run", return_value=mock_result) as mock_run:
        result = _apply_per_item_fixtures(
            "F-00099",
            "iw-ai-core-e2e-f00099",
            str(tmp_path),
        )
    assert result is None
    mock_run.assert_not_called()


def test_apply_per_item_fixtures_empty_dir_skips_exec_with_custom_service(tmp_path: Path) -> None:
    """AC3 (configured service): empty e2e_fixtures dir → subprocess seam never invoked.

    Symmetric with the no-dir case but for a non-default service name. The
    fast-path must short-circuit *before* the configured service name is
    considered; otherwise projects that override the service would still pay
    the docker-compose exec cost on items that ship no fixtures.
    """
    fx_dir = tmp_path / "ai-dev" / "active" / "F-00099" / "e2e_fixtures"
    fx_dir.mkdir(parents=True, exist_ok=True)
    mock_result = MagicMock(stdout="", stderr="", returncode=0)
    with patch("orch.daemon.browser_env.subprocess.run", return_value=mock_result) as mock_run:
        result = _apply_per_item_fixtures(
            "F-00099",
            "iw-ai-core-e2e-f00099",
            str(tmp_path),
            service_name="api",
        )
    assert result is None
    mock_run.assert_not_called()
