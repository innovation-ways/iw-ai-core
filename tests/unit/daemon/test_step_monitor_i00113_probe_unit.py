from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from orch.daemon import step_monitor as sm


class _Ctx:
    def __init__(self, text: str):
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._text


def test_has_agent_cmdline_none_pid_returns_false() -> None:
    assert sm._has_agent_cmdline(None) is False


def test_has_agent_cmdline_detects_agent_from_cwd(monkeypatch) -> None:
    monkeypatch.setattr(sm.os, "kill", lambda _pid, _sig: None)

    def fake_open(path: str, *args, **kwargs):  # noqa: ARG001
        if path.endswith("/cwd"):
            return _Ctx("/tmp/worktrees/x/orch")
        raise OSError

    monkeypatch.setattr("builtins.open", fake_open)
    assert sm._has_agent_cmdline(123) is True


def test_has_agent_cmdline_falls_back_to_comm(monkeypatch) -> None:
    monkeypatch.setattr(sm.os, "kill", lambda _pid, _sig: None)

    def fake_open(path: str, *args, **kwargs):  # noqa: ARG001
        if path.endswith("/cwd"):
            raise OSError
        if path.endswith("/cmdline"):
            raise OSError
        if path.endswith("/comm"):
            return _Ctx("opencode\n")
        raise OSError

    monkeypatch.setattr("builtins.open", fake_open)
    assert sm._has_agent_cmdline(123) is True


def test_has_agent_cmdline_returns_false_when_comm_unreadable(monkeypatch) -> None:
    monkeypatch.setattr(sm.os, "kill", lambda _pid, _sig: None)

    def _raise_os_error(*_args, **_kwargs):
        raise OSError

    monkeypatch.setattr("builtins.open", _raise_os_error)
    assert sm._has_agent_cmdline(123) is False


def test_probe_for_child_tier1_finds_agent(monkeypatch) -> None:
    monkeypatch.setattr(sm.os, "listdir", lambda p: ["111"] if p.endswith("/task") else [])

    def _open_ctx(*_args, **_kwargs):
        return _Ctx("777")

    monkeypatch.setattr("builtins.open", _open_ctx)
    monkeypatch.setattr(sm, "_has_agent_cmdline", lambda pid: pid == 777)

    assert sm._probe_for_child(555) is True


def test_probe_for_child_tier2_finds_agent_after_tier1_read_error(monkeypatch) -> None:
    def fake_listdir(path: str):
        if path.endswith("/task"):
            return ["111"]
        if path == "/proc":
            return ["999", "abc"]
        return []

    monkeypatch.setattr(sm.os, "listdir", fake_listdir)

    def fake_open(path: str, *args, **kwargs):  # noqa: ARG001
        if path.endswith("/children"):
            raise OSError
        if path.endswith("/999/stat"):
            return _Ctx("999 (x) S 555 0 0 0")
        raise OSError

    monkeypatch.setattr("builtins.open", fake_open)
    monkeypatch.setattr(sm, "_has_agent_cmdline", lambda pid: pid == 999)

    assert sm._probe_for_child(555) is True


def test_probe_for_child_handles_proc_scan_errors(monkeypatch) -> None:
    def fake_listdir(path: str):
        if path.endswith("/task"):
            return []
        if path == "/proc":
            raise OSError
        return []

    monkeypatch.setattr(sm.os, "listdir", fake_listdir)
    assert sm._probe_for_child(555) is False


def test_check_step_health_dead_wrapper_with_child_updates_tokens(monkeypatch) -> None:
    run = SimpleNamespace(
        pid=123,
        pid_alive=False,
        session_file="/tmp/session.jsonl",
        last_heartbeat=None,
        started_at=datetime.now(UTC),
        timeout_secs=60,
    )
    calls: list[str] = []

    monkeypatch.setattr(sm, "_is_pid_alive", lambda _pid: False)
    monkeypatch.setattr(sm, "_probe_for_child", lambda _pid: True)
    monkeypatch.setattr(sm, "_update_token_counts", lambda _run: calls.append("updated"))

    def _track_resolve(*_args, **_kwargs):
        calls.append("resolve")

    def _track_crash(*_args, **_kwargs):
        calls.append("crash")

    monkeypatch.setattr(sm, "_maybe_resolve_pi_session_file", _track_resolve)
    monkeypatch.setattr(sm, "_handle_crashed", _track_crash)

    sm._check_step_health(
        db=MagicMock(),
        run=run,
        project_id="p",
        config=SimpleNamespace(stall_threshold=30),
        project_config=None,
    )

    assert run.pid_alive is True
    assert "crash" not in calls
    assert "updated" in calls
