from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from orch.daemon import step_monitor as sm


def test_check_step_health_skips_crash_when_completed_at_set(monkeypatch) -> None:
    run = SimpleNamespace(
        pid=99999,
        pid_alive=True,
        completed_at=datetime.now(UTC),
        session_file=None,
    )
    crashed_calls: list[str] = []

    monkeypatch.setattr(sm, "_is_pid_alive", lambda _pid: False)
    monkeypatch.setattr(sm, "_probe_for_child", lambda _pid: False)
    monkeypatch.setattr(
        sm,
        "_handle_crashed",
        lambda *_args, **_kwargs: crashed_calls.append("called"),
    )

    sm._check_step_health(
        db=MagicMock(),
        run=run,
        project_id="p",
        config=SimpleNamespace(stall_threshold=30),
        project_config=None,
    )

    assert crashed_calls == []


def test_check_step_health_calls_crash_when_not_completed(monkeypatch) -> None:
    run = SimpleNamespace(
        pid=99999,
        pid_alive=True,
        completed_at=None,
        session_file=None,
    )
    crashed_calls: list[str] = []

    monkeypatch.setattr(sm, "_is_pid_alive", lambda _pid: False)
    monkeypatch.setattr(sm, "_probe_for_child", lambda _pid: False)
    monkeypatch.setattr(
        sm,
        "_handle_crashed",
        lambda *_args, **_kwargs: crashed_calls.append("called"),
    )

    sm._check_step_health(
        db=MagicMock(),
        run=run,
        project_id="p",
        config=SimpleNamespace(stall_threshold=30),
        project_config=None,
    )

    assert crashed_calls == ["called"]


def test_completed_at_none_still_calls_handle_crashed(monkeypatch) -> None:
    run = SimpleNamespace(
        pid=99999,
        pid_alive=True,
        completed_at=None,
        session_file=None,
    )
    crashed_calls: list[str] = []

    monkeypatch.setattr(sm, "_is_pid_alive", lambda _pid: False)
    monkeypatch.setattr(sm, "_probe_for_child", lambda _pid: False)
    monkeypatch.setattr(
        sm,
        "_handle_crashed",
        lambda *_args, **_kwargs: crashed_calls.append("called"),
    )

    sm._check_step_health(
        db=MagicMock(),
        run=run,
        project_id="p",
        config=SimpleNamespace(stall_threshold=30),
        project_config=None,
    )

    assert crashed_calls == ["called"]
    assert run.completed_at is None


def test_completed_at_set_and_child_alive_returns_early(monkeypatch) -> None:
    run = SimpleNamespace(
        id=1,
        pid=99999,
        pid_alive=False,
        completed_at=datetime.now(UTC),
        session_file=None,
        last_heartbeat=None,
        started_at=None,
        timeout_secs=None,
        cli_tool="opencode",
        worktree_path=None,
    )
    crashed_calls: list[str] = []

    monkeypatch.setattr(sm, "_is_pid_alive", lambda _pid: False)
    monkeypatch.setattr(sm, "_probe_for_child", lambda _pid: True)
    monkeypatch.setattr(
        sm,
        "_handle_crashed",
        lambda *_args, **_kwargs: crashed_calls.append("called"),
    )

    sm._check_step_health(
        db=MagicMock(),
        run=run,
        project_id="p",
        config=SimpleNamespace(stall_threshold=30),
        project_config=None,
    )

    assert crashed_calls == []
    assert run.pid_alive is False
