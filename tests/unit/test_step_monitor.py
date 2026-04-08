"""Unit tests for step_monitor — health checks for running step_runs.

All DB interaction is mocked. All time-sensitive tests use freezegun.
os.kill is patched at orch.daemon.step_monitor.os.kill throughout.
"""

from __future__ import annotations

import signal
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import pytest
from freezegun import freeze_time

from orch.config import DaemonConfig
from orch.daemon.project_registry import ProjectConfig
from orch.daemon.step_monitor import (
    _FALLBACK_TIMEOUT,
    PLATFORM_TIMEOUT_DEFAULTS,
    get_timeout,
    kill_process,
    monitor_running_steps,
)
from orch.db.models import RunStatus, StepStatus

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

_FROZEN_TIME = "2024-06-01 12:00:00"
_FROZEN_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)


def make_config(tmp_path: Path) -> DaemonConfig:
    """Minimal DaemonConfig for tests (stall_threshold=600s)."""
    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("")
    return DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5433/test",
        dashboard_host="0.0.0.0",  # noqa: S104
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=600,
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=projects_toml,
    )


def make_project_config(timeout_overrides: dict | None = None) -> ProjectConfig:
    """Minimal ProjectConfig with optional timeout_overrides."""
    config: dict = {}
    if timeout_overrides:
        config["timeout_overrides"] = timeout_overrides
    return ProjectConfig(
        id="test_proj",
        display_name="Test",
        repo_root="/nonexistent/test-project",
        enabled=True,
        cli_tool="opencode",
        worktree_base=".worktrees",
        config=config,
    )


def make_run(**kwargs) -> MagicMock:
    """Create a MagicMock StepRun with sensible defaults."""
    run = MagicMock()
    run.id = 42
    run.step_id = 1
    run.pid = 12345
    run.status = RunStatus.running
    run.pid_alive = None
    run.started_at = _FROZEN_NOW - timedelta(seconds=60)
    run.timeout_secs = 2700
    run.last_heartbeat = _FROZEN_NOW - timedelta(seconds=30)
    run.error_message = None
    run.completed_at = None
    run.duration_secs = None
    for k, v in kwargs.items():
        setattr(run, k, v)
    return run


def make_db(runs: list) -> MagicMock:
    """Create a mock Session that yields `runs` from the query chain."""
    db = MagicMock()
    db.query.return_value.join.return_value.filter.return_value.all.return_value = runs
    db.get.return_value = MagicMock()  # mock WorkflowStep
    return db


# ---------------------------------------------------------------------------
# monitor_running_steps — PID checks
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_TIME)
def test_pid_alive_within_timeout_no_action(tmp_path: Path) -> None:
    """PID alive, within timeout, not stalled → pid_alive/heartbeat updated, no state change."""
    run = make_run(
        started_at=_FROZEN_NOW - timedelta(seconds=60),
        timeout_secs=2700,
        last_heartbeat=_FROZEN_NOW - timedelta(seconds=30),
    )
    db = make_db([run])

    with patch("orch.daemon.step_monitor.os.kill") as mock_kill:
        mock_kill.return_value = None  # kill(pid, 0) succeeds — process alive
        monitor_running_steps(db, "proj", make_config(tmp_path))

    assert run.pid_alive is True
    assert run.last_heartbeat == _FROZEN_NOW
    assert run.status == RunStatus.running  # unchanged
    db.add.assert_not_called()
    db.commit.assert_called_once()


@freeze_time(_FROZEN_TIME)
def test_pid_dead_marks_failed(tmp_path: Path) -> None:
    """PID dead (ProcessLookupError) → status=failed, error_message set, parent step updated."""
    run = make_run(
        pid=12345,
        started_at=_FROZEN_NOW - timedelta(seconds=300),
    )
    db = make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", side_effect=ProcessLookupError):
        monitor_running_steps(db, "proj", make_config(tmp_path))

    assert run.pid_alive is False
    assert run.status == RunStatus.failed
    assert "PID dead" in run.error_message
    assert run.completed_at == _FROZEN_NOW
    assert run.duration_secs == pytest.approx(300.0)

    # Parent step must be marked failed
    mock_step = db.get.return_value
    assert mock_step.status == StepStatus.failed
    assert mock_step.completed_at == _FROZEN_NOW

    # Event emitted
    db.add.assert_called_once()
    event = db.add.call_args[0][0]
    assert event.event_type == "step_crashed"
    assert event.project_id == "proj"


@freeze_time(_FROZEN_TIME)
def test_pid_none_marks_failed(tmp_path: Path) -> None:
    """pid=None → status=failed with 'No PID recorded' message."""
    run = make_run(pid=None)
    db = make_db([run])

    with patch("orch.daemon.step_monitor.os.kill") as mock_kill:
        monitor_running_steps(db, "proj", make_config(tmp_path))

    # kill should never be called if pid is None
    mock_kill.assert_not_called()
    assert run.pid_alive is False
    assert run.status == RunStatus.failed
    assert run.error_message == "No PID recorded"

    event = db.add.call_args[0][0]
    assert event.event_type == "step_crashed"


@freeze_time(_FROZEN_TIME)
def test_pid_permission_error_treated_as_dead(tmp_path: Path) -> None:
    """PermissionError on kill -0 → treated as dead, status=failed."""
    run = make_run(pid=1)  # PID 1 (init) — PermissionError is realistic
    db = make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", side_effect=PermissionError):
        monitor_running_steps(db, "proj", make_config(tmp_path))

    assert run.pid_alive is False
    assert run.status == RunStatus.failed
    assert "PID dead" in run.error_message


# ---------------------------------------------------------------------------
# monitor_running_steps — timeout
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_TIME)
def test_pid_alive_timeout_exceeded(tmp_path: Path) -> None:
    """PID alive but elapsed > timeout_secs → SIGTERM, status=timeout, parent failed."""
    run = make_run(
        pid=12345,
        started_at=_FROZEN_NOW - timedelta(seconds=3700),  # 3700s > 2700s timeout
        timeout_secs=2700,
        last_heartbeat=_FROZEN_NOW - timedelta(seconds=30),
    )
    db = make_db([run])

    with patch("orch.daemon.step_monitor.os.kill") as mock_kill:
        mock_kill.return_value = None  # kill(pid, 0) succeeds
        monitor_running_steps(db, "proj", make_config(tmp_path))

    # kill(pid, 0) for aliveness check + kill(pid, SIGTERM) for termination
    assert mock_kill.call_count == 2
    assert call(12345, 0) in mock_kill.call_args_list
    assert call(12345, signal.SIGTERM) in mock_kill.call_args_list

    assert run.status == RunStatus.timeout
    assert "Timeout after" in run.error_message
    assert "2700s" in run.error_message
    assert run.completed_at == _FROZEN_NOW
    assert run.duration_secs == pytest.approx(3700.0)

    mock_step = db.get.return_value
    assert mock_step.status == StepStatus.failed

    event = db.add.call_args[0][0]
    assert event.event_type == "step_timeout"


@freeze_time(_FROZEN_TIME)
def test_timeout_skipped_when_started_at_is_none(tmp_path: Path) -> None:
    """If started_at is None, timeout check is skipped."""
    run = make_run(
        pid=12345,
        started_at=None,
        timeout_secs=1,  # tiny timeout — would trigger if started_at were set
        last_heartbeat=_FROZEN_NOW - timedelta(seconds=30),
    )
    db = make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db, "proj", make_config(tmp_path))

    assert run.status == RunStatus.running  # no timeout triggered


@freeze_time(_FROZEN_TIME)
def test_timeout_skipped_when_timeout_secs_is_none(tmp_path: Path) -> None:
    """If timeout_secs is None, timeout check is skipped."""
    run = make_run(
        pid=12345,
        started_at=_FROZEN_NOW - timedelta(seconds=9999),
        timeout_secs=None,
        last_heartbeat=_FROZEN_NOW - timedelta(seconds=30),
    )
    db = make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db, "proj", make_config(tmp_path))

    assert run.status == RunStatus.running  # no timeout triggered


# ---------------------------------------------------------------------------
# monitor_running_steps — stall
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_TIME)
def test_pid_alive_stalled(tmp_path: Path) -> None:
    """PID alive but heartbeat > stall_threshold → status=stalled (not terminal)."""
    run = make_run(
        pid=12345,
        started_at=_FROZEN_NOW - timedelta(seconds=120),
        timeout_secs=2700,
        last_heartbeat=_FROZEN_NOW - timedelta(seconds=700),  # 700s > 600s threshold
    )
    db = make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db, "proj", make_config(tmp_path))

    assert run.status == RunStatus.stalled
    assert "No progress for 600s" in run.error_message
    # Stall does NOT update parent workflow_step to failed
    mock_step = db.get.return_value
    assert mock_step.status != StepStatus.failed

    event = db.add.call_args[0][0]
    assert event.event_type == "step_stalled"


@freeze_time(_FROZEN_TIME)
def test_stall_skipped_when_heartbeat_is_none(tmp_path: Path) -> None:
    """If last_heartbeat is None, stall detection is skipped."""
    run = make_run(
        pid=12345,
        started_at=_FROZEN_NOW - timedelta(seconds=60),
        timeout_secs=2700,
        last_heartbeat=None,
    )
    db = make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db, "proj", make_config(tmp_path))

    assert run.status == RunStatus.running  # no stall triggered


@freeze_time(_FROZEN_TIME)
def test_stall_not_triggered_when_heartbeat_fresh(tmp_path: Path) -> None:
    """Heartbeat age < stall_threshold → no stall."""
    run = make_run(
        pid=12345,
        started_at=_FROZEN_NOW - timedelta(seconds=60),
        timeout_secs=2700,
        last_heartbeat=_FROZEN_NOW - timedelta(seconds=100),  # 100s < 600s
    )
    db = make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db, "proj", make_config(tmp_path))

    assert run.status == RunStatus.running


@freeze_time(_FROZEN_TIME)
def test_timeout_takes_priority_over_stall(tmp_path: Path) -> None:
    """When both timeout and stall conditions are met, timeout wins."""
    run = make_run(
        pid=12345,
        started_at=_FROZEN_NOW - timedelta(seconds=3700),
        timeout_secs=2700,
        last_heartbeat=_FROZEN_NOW - timedelta(seconds=700),  # also stalled
    )
    db = make_db([run])

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db, "proj", make_config(tmp_path))

    assert run.status == RunStatus.timeout  # timeout wins


# ---------------------------------------------------------------------------
# get_timeout — priority chain
# ---------------------------------------------------------------------------


def test_get_timeout_step_config_override() -> None:
    """Step-level override wins over project and platform."""
    project_config = make_project_config(timeout_overrides={"implementation": 9999})
    step_config = {"timeout_secs": 500}

    result = get_timeout(project_config, "implementation", step_config=step_config)

    assert result == 500  # step-level wins


def test_get_timeout_project_override() -> None:
    """Project-level override wins over platform default."""
    project_config = make_project_config(timeout_overrides={"implementation": 1234})

    result = get_timeout(project_config, "implementation")

    assert result == 1234  # project-level wins


def test_get_timeout_platform_default() -> None:
    """No overrides → platform default is used."""
    project_config = make_project_config()

    result = get_timeout(project_config, "implementation")

    assert result == PLATFORM_TIMEOUT_DEFAULTS["implementation"]  # 2700


def test_get_timeout_fallback_for_unknown_step_type() -> None:
    """Unknown step type → fallback value (1800)."""
    project_config = make_project_config()

    result = get_timeout(project_config, "unknown_step_type")

    assert result == _FALLBACK_TIMEOUT  # 1800


def test_get_timeout_step_config_empty_no_key() -> None:
    """step_config present but no 'timeout_secs' key → falls through to project/platform."""
    project_config = make_project_config(timeout_overrides={"code_review": 999})
    step_config: dict = {}  # no timeout_secs

    result = get_timeout(project_config, "code_review", step_config=step_config)

    assert result == 999  # project override used


def test_get_timeout_all_platform_defaults() -> None:
    """All known step types have correct platform defaults."""
    project_config = make_project_config()
    expected = {
        "implementation": 2700,
        "code_review": 1800,
        "code_review_fix": 2700,
        "code_review_final": 2400,
        "code_review_fix_final": 2700,
        "quality_validation": 600,
        "qv_fix": 1800,
        "browser_verification": 900,
    }
    for step_type, expected_secs in expected.items():
        assert get_timeout(project_config, step_type) == expected_secs


# ---------------------------------------------------------------------------
# kill_process
# ---------------------------------------------------------------------------


def test_kill_process_sends_sigterm_returns_true() -> None:
    """kill_process sends SIGTERM and returns True on success."""
    with patch("orch.daemon.step_monitor.os.kill") as mock_kill:
        mock_kill.return_value = None
        result = kill_process(12345)

    assert result is True
    mock_kill.assert_called_once_with(12345, signal.SIGTERM)


def test_kill_process_dead_pid_returns_false() -> None:
    """kill_process returns False (no exception) when process is already dead."""
    with patch("orch.daemon.step_monitor.os.kill", side_effect=ProcessLookupError):
        result = kill_process(99999)

    assert result is False


def test_kill_process_does_not_raise_on_dead_pid() -> None:
    """Calling kill_process on a dead PID never raises."""
    with patch("orch.daemon.step_monitor.os.kill", side_effect=ProcessLookupError):
        kill_process(99999)  # should not raise


# ---------------------------------------------------------------------------
# monitor_running_steps — empty run list
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_TIME)
def test_no_running_steps_commits_and_returns(tmp_path: Path) -> None:
    """No running steps → just commit, no os.kill calls."""
    db = make_db([])

    with patch("orch.daemon.step_monitor.os.kill") as mock_kill:
        monitor_running_steps(db, "proj", make_config(tmp_path))

    mock_kill.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_called_once()
