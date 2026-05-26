from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from orch.config import DaemonConfig
from orch.daemon import step_monitor
from orch.daemon.project_registry import ProjectConfig
from orch.daemon.step_monitor import monitor_running_steps
from orch.db.models import (
    DaemonEvent,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


class _Clock:
    def __init__(self, now: datetime):
        self.now_value = now

    def now(self, _tz):
        return self.now_value

    def advance(self, *, seconds: int):
        self.now_value = self.now_value + timedelta(seconds=seconds)


def _config(tmp_path, stall_threshold: int) -> DaemonConfig:
    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("")
    return DaemonConfig(
        db_host="127.0.0.1",
        db_port=1,
        db_name="ignored",
        db_user="ignored",
        db_password="ignored",  # noqa: S106
        db_url="postgresql+psycopg://ignored:ignored@127.0.0.1:1/ignored",
        dashboard_host="0.0.0.0",  # noqa: S104
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=stall_threshold,
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=projects_toml,
    )


def _project_config() -> ProjectConfig:
    return ProjectConfig(
        id="test-proj",
        display_name="Test",
        repo_root="/nonexistent",
        enabled=True,
        cli_tool="opencode",
        model="minimax",
        worktree_base=".worktrees",
        config={},
    )


def _seed_running_step(db_session, now: datetime) -> tuple[WorkItem, WorkflowStep, StepRun]:
    item_id = "I-STALL-001"
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.Feature,
        title="Stall test",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.work,
        config={},
    )
    db_session.add(item)
    db_session.flush()
    step = WorkflowStep(
        project_id="test-proj",
        work_item_id=item_id,
        step_number=1,
        step_id="S04",
        agent_label="Backend",
        opencode_agent="backend-impl",
        step_type=StepType.implementation,
        command="echo run",
        status=StepStatus.in_progress,
        timeout_secs=600,
    )
    db_session.add(step)
    db_session.flush()
    run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.running,
        pid=43121,
        pid_alive=True,
        command="echo run",
        worktree_path="/tmp/wt",
        cli_tool="opencode",
        started_at=now,
        last_heartbeat=now,
        timeout_secs=600,
    )
    db_session.add(run)
    db_session.commit()
    return item, step, run


def _install_clock(monkeypatch, clock: _Clock) -> None:
    class _DateTimeShim:
        @staticmethod
        def now(_tz):
            return clock.now_value

    monkeypatch.setattr(step_monitor, "datetime", _DateTimeShim)


@pytest.mark.integration
def test_stalled_agent_is_detected(db_session, test_project, tmp_path, chaos_daemon, monkeypatch):
    base = BASE_TIME
    _, _, run = _seed_running_step(db_session, base)
    chaos_daemon.inject_agent_stall_after_seconds(2)
    clock = _Clock(base)
    _install_clock(monkeypatch, clock)
    monkeypatch.setattr(step_monitor, "_is_pid_alive", lambda _pid: True)

    clock.advance(seconds=3)
    monitor_running_steps(
        db_session, "test-proj", _config(tmp_path, stall_threshold=2), _project_config()
    )
    db_session.refresh(run)

    assert run.status == RunStatus.stalled
    assert chaos_daemon.hooks_armed["agent_stall_after_seconds"] == 2


@pytest.mark.integration
def test_stalled_agent_step_recorded(db_session, test_project, tmp_path, monkeypatch):
    base = BASE_TIME
    _, _, run = _seed_running_step(db_session, base)
    clock = _Clock(base)
    _install_clock(monkeypatch, clock)
    monkeypatch.setattr(step_monitor, "_is_pid_alive", lambda _pid: True)

    kill_calls: list[int] = []
    monkeypatch.setattr(
        step_monitor, "kill_process_group", lambda pid: kill_calls.append(pid) or True
    )

    clock.advance(seconds=5)
    monitor_running_steps(
        db_session, "test-proj", _config(tmp_path, stall_threshold=2), _project_config()
    )
    db_session.refresh(run)
    event = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == "test-proj", DaemonEvent.event_type == "step_stall_killed"
        )
        .order_by(DaemonEvent.id.desc())
        .first()
    )

    assert run.status == RunStatus.failed
    assert kill_calls == [run.pid]
    assert event is not None
    assert int(event.event_metadata["pid"]) == run.pid
    assert float(event.event_metadata["heartbeat_age_secs"]) >= 5.0


@pytest.mark.integration
def test_stall_policy_routing(db_session, test_project, tmp_path, monkeypatch):
    base = BASE_TIME
    item, step, run = _seed_running_step(db_session, base)
    clock = _Clock(base)
    _install_clock(monkeypatch, clock)
    monkeypatch.setattr(step_monitor, "_is_pid_alive", lambda _pid: True)
    monkeypatch.setattr(step_monitor, "kill_process_group", lambda _pid: True)

    clock.advance(seconds=5)
    monitor_running_steps(
        db_session, "test-proj", _config(tmp_path, stall_threshold=2), _project_config()
    )
    db_session.refresh(item)
    db_session.refresh(step)
    db_session.refresh(run)

    assert run.status == RunStatus.failed
    assert step.status == StepStatus.failed
    assert item.status == WorkItemStatus.in_progress


@pytest.mark.integration
def test_stall_threshold_zero_boundary(
    db_session, test_project, tmp_path, chaos_daemon, monkeypatch
):
    with pytest.raises(ValueError, match=r"seconds must be > 0"):
        chaos_daemon.inject_agent_stall_after_seconds(0)

    base = BASE_TIME
    _, _, run = _seed_running_step(db_session, base)
    clock = _Clock(base)
    _install_clock(monkeypatch, clock)
    monkeypatch.setattr(step_monitor, "_is_pid_alive", lambda _pid: True)
    kill_calls: list[int] = []
    monkeypatch.setattr(
        step_monitor, "kill_process_group", lambda pid: kill_calls.append(pid) or True
    )

    clock.advance(seconds=1)
    monitor_running_steps(
        db_session, "test-proj", _config(tmp_path, stall_threshold=0), _project_config()
    )
    db_session.refresh(run)

    event = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == "test-proj", DaemonEvent.event_type == "step_stall_killed"
        )
        .order_by(DaemonEvent.id.desc())
        .first()
    )
    assert run.status == RunStatus.failed
    assert kill_calls == [run.pid]
    assert event is not None
    assert int(event.event_metadata["pid"]) == run.pid
