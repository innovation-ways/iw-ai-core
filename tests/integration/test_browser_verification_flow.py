"""Integration tests for browser_verification step launch and teardown.

Uses a real PostgreSQL testcontainer (no live DB).  Tests exercise:
- _launch_step for a browser_verification step with mock env_up
- env_up failure → step marked failed, no agent launched
- env_up success → agent launched with merged env
- Timeout/crash path → teardown hook called via step_monitor
- step-restart does NOT create a pending StepRun

These tests do NOT mock the database — the whole point is to verify real DB
state transitions.  subprocess.Popen and browser_env hook calls ARE mocked.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from orch.config import DaemonConfig
from orch.daemon.batch_manager import BatchManager
from orch.daemon.project_registry import ProjectConfig
from orch.daemon.step_monitor import monitor_running_steps
from orch.db.models import (
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

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def daemon_config(tmp_path: Path) -> DaemonConfig:
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


def make_project_config_with_bv(
    worktree_root: str,
    env_up_command: str = "/bin/true",
    env_down_command: str = "/bin/true",
) -> ProjectConfig:
    return ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root=worktree_root,
        enabled=True,
        cli_tool="opencode",
        model="minimax",
        worktree_base=".worktrees",
        config={
            "browser_verification": {
                "env_up_command": env_up_command,
                "env_down_command": env_down_command,
                "port_pool": {
                    "frontend_base": 3100,
                    "api_base": 8090,
                    "db_base": 5442,
                    "redis_base": 6389,
                    "pool_size": 100,
                },
                "compose_project_prefix": "test-e2e",
            }
        },
    )


def make_project_config_no_bv(worktree_root: str) -> ProjectConfig:
    return ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root=worktree_root,
        enabled=True,
        cli_tool="opencode",
        model="minimax",
        worktree_base=".worktrees",
        config={},
    )


@pytest.fixture
def manager_with_bv(db_session: Session, test_project, daemon_config, tmp_path) -> BatchManager:
    project_config = make_project_config_with_bv(str(tmp_path))

    @contextmanager
    def session_factory():
        yield db_session

    return BatchManager(
        project_id="test-proj",
        project_config=project_config,
        session_factory=session_factory,
        config=daemon_config,
    )


@pytest.fixture
def manager_no_bv(db_session: Session, test_project, daemon_config, tmp_path) -> BatchManager:
    project_config = make_project_config_no_bv(str(tmp_path))

    @contextmanager
    def session_factory():
        yield db_session

    return BatchManager(
        project_id="test-proj",
        project_config=project_config,
        session_factory=session_factory,
        config=daemon_config,
    )


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def make_work_item(db: Session, item_id: str = "F-00001") -> WorkItem:
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.Feature,
        title="Browser verification test item",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(item)
    db.flush()
    return item


def make_browser_step(
    db: Session,
    item_id: str = "F-00001",
    step_id: str = "S01",
    status: StepStatus = StepStatus.pending,
) -> WorkflowStep:
    step = WorkflowStep(
        project_id="test-proj",
        work_item_id=item_id,
        step_number=1,
        step_id=step_id,
        agent_label="quality-validation-impl",
        step_type=StepType.browser_verification,
        status=status,
    )
    db.add(step)
    db.flush()
    return step


def make_step_run(
    db: Session,
    step: WorkflowStep,
    run_number: int = 1,
    status: RunStatus = RunStatus.running,
    worktree_path: str = "/wt/F-00001",
    pid: int = 12345,
    started_at: datetime | None = None,
    timeout_secs: int = 1800,
) -> StepRun:
    now = started_at or datetime.now(UTC)
    step_run = StepRun(
        step_id=step.id,
        run_number=run_number,
        status=status,
        pid=pid,
        pid_alive=True,
        command="opencode run '/execute F-00001 S01'",
        worktree_path=worktree_path,
        cli_tool="opencode",
        started_at=now,
        last_heartbeat=now,
        timeout_secs=timeout_secs,
    )
    db.add(step_run)
    db.flush()
    return step_run


# ---------------------------------------------------------------------------
# Test: env_up failure → step marked failed, no Popen called
# ---------------------------------------------------------------------------


def test_launch_step_env_up_failure_marks_step_failed(
    db_session: Session, manager_with_bv: BatchManager, tmp_path: Path
) -> None:
    """When env_up_hook returns False, the step is marked failed and no agent is launched."""
    make_work_item(db_session)
    step = make_browser_step(db_session)
    worktree_path = tmp_path / ".worktrees" / "F-00001"
    worktree_path.mkdir(parents=True)
    worktree_info = {"path": str(worktree_path)}

    fake_env = {"E2E_FRONTEND_PORT": "3137", "IW_BROWSER_BASE_URL": "http://localhost:3137"}
    with (
        patch("orch.daemon.browser_env.allocate_browser_env", return_value=fake_env),
        patch("orch.daemon.browser_env.run_env_up_hook", return_value=(False, Path("/log.txt"))),
        # H11: env_up failure now triggers env_down teardown — mock it to a no-op
        patch("orch.daemon.browser_env.run_env_down_hook") as mock_env_down,
        patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen,
    ):
        manager_with_bv._launch_step(db_session, step, worktree_info)

    # Agent was NOT launched (the only Popen-equivalent path that should run is env_down,
    # which we mocked above to a no-op)
    mock_popen.assert_not_called()
    # H11: env_down should have been called to clean up partial bring-up state
    mock_env_down.assert_called_once()

    # Step should be failed
    db_session.refresh(step)
    assert step.status == StepStatus.failed

    # A failed StepRun should exist
    run = db_session.query(StepRun).filter(StepRun.step_id == step.id).first()
    assert run is not None
    assert run.status == RunStatus.failed
    assert "browser env setup failed" in run.error_message


# ---------------------------------------------------------------------------
# Test: env_up success → agent launched with merged env
# ---------------------------------------------------------------------------


def test_launch_step_env_up_success_launches_agent_with_env(
    db_session: Session, manager_with_bv: BatchManager, tmp_path: Path
) -> None:
    """When env_up_hook succeeds, the agent is launched with the browser env vars."""
    make_work_item(db_session)
    step = make_browser_step(db_session)
    worktree_path = tmp_path / ".worktrees" / "F-00001"
    worktree_path.mkdir(parents=True)
    worktree_info = {"path": str(worktree_path)}

    fake_bv_env = {"E2E_FRONTEND_PORT": "3137", "IW_BROWSER_BASE_URL": "http://localhost:3137"}

    mock_proc = MagicMock()
    mock_proc.pid = 99999

    with (
        patch(
            "orch.daemon.browser_env.allocate_browser_env",
            return_value=fake_bv_env,
        ),
        patch(
            "orch.daemon.browser_env.run_env_up_hook",
            return_value=(True, Path("/log.txt")),
        ),
        patch("orch.daemon.batch_manager.subprocess.Popen", return_value=mock_proc) as mock_popen,
        patch("pathlib.Path.open", MagicMock()),
    ):
        manager_with_bv._launch_step(db_session, step, worktree_info)

    # Agent was launched
    mock_popen.assert_called_once()
    popen_kwargs = mock_popen.call_args[1]

    # The env passed to Popen must include the browser env vars
    launched_env = popen_kwargs.get("env", {})
    assert launched_env.get("E2E_FRONTEND_PORT") == "3137"
    assert launched_env.get("IW_BROWSER_BASE_URL") == "http://localhost:3137"

    # Step should be in_progress
    db_session.refresh(step)
    assert step.status == StepStatus.in_progress

    # A running StepRun should exist
    run = db_session.query(StepRun).filter(StepRun.step_id == step.id).first()
    assert run is not None
    assert run.status == RunStatus.running
    assert run.pid == 99999


# ---------------------------------------------------------------------------
# Test: non-browser step → no browser env hooks called
# ---------------------------------------------------------------------------


def test_launch_step_non_browser_step_no_hooks_called(
    db_session: Session, manager_no_bv: BatchManager, tmp_path: Path
) -> None:
    """A non-browser step launches normally without any browser env calls."""
    make_work_item(db_session)
    # Create an implementation step (not browser_verification)
    step = WorkflowStep(
        project_id="test-proj",
        work_item_id="F-00001",
        step_number=1,
        step_id="S01",
        agent_label="backend-impl",
        step_type=StepType.implementation,
        status=StepStatus.pending,
    )
    db_session.add(step)
    db_session.flush()

    worktree_path = tmp_path / ".worktrees" / "F-00001"
    worktree_path.mkdir(parents=True)
    worktree_info = {"path": str(worktree_path)}

    mock_proc = MagicMock()
    mock_proc.pid = 11111

    with (
        patch("orch.daemon.browser_env.run_env_up_hook") as mock_up,
        patch("orch.daemon.batch_manager.subprocess.Popen", return_value=mock_proc),
        patch("pathlib.Path.open", MagicMock()),
    ):
        manager_no_bv._launch_step(db_session, step, worktree_info)

    # env_up_hook was never called
    mock_up.assert_not_called()

    db_session.refresh(step)
    assert step.status == StepStatus.in_progress


# ---------------------------------------------------------------------------
# Test: step_monitor crash path → teardown called
# ---------------------------------------------------------------------------


def test_step_monitor_crash_calls_teardown(
    db_session: Session, test_project, tmp_path: Path, daemon_config: DaemonConfig
) -> None:
    """When a step_run crashes, the browser env teardown hook is invoked."""
    make_work_item(db_session)
    step = make_browser_step(db_session)
    project_config = make_project_config_with_bv(str(tmp_path))
    make_step_run(db_session, step, worktree_path=str(tmp_path))

    with (
        patch("orch.daemon.step_monitor.os.kill", side_effect=ProcessLookupError),
        patch("orch.daemon.browser_env.run_env_down_hook") as mock_down,
        patch("orch.daemon.browser_env.resolve_browser_env") as mock_resolve,
    ):
        mock_resolve.return_value = {"E2E_FRONTEND_PORT": "3137"}
        monitor_running_steps(db_session, "test-proj", daemon_config, project_config)

    # Teardown was called once
    mock_down.assert_called_once()
    call_kwargs = mock_down.call_args
    # First positional arg is project_config
    assert call_kwargs[0][0] is project_config


# ---------------------------------------------------------------------------
# Test: step_monitor timeout path → teardown called
# ---------------------------------------------------------------------------


def test_step_monitor_timeout_calls_teardown(
    db_session: Session, test_project, tmp_path: Path, daemon_config: DaemonConfig
) -> None:
    """When a step_run times out, the browser env teardown hook is invoked."""
    make_work_item(db_session)
    step = make_browser_step(db_session)
    project_config = make_project_config_with_bv(str(tmp_path))
    # Create a step_run that is well past its timeout
    far_past = datetime.now(UTC) - timedelta(seconds=9999)
    make_step_run(
        db_session,
        step,
        worktree_path=str(tmp_path),
        started_at=far_past,
        timeout_secs=100,
    )

    with (
        patch("orch.daemon.step_monitor.os.kill", return_value=None),  # PID alive
        patch("orch.daemon.browser_env.run_env_down_hook") as mock_down,
        patch("orch.daemon.browser_env.resolve_browser_env") as mock_resolve,
    ):
        mock_resolve.return_value = {"E2E_FRONTEND_PORT": "3137"}
        monitor_running_steps(db_session, "test-proj", daemon_config, project_config)

    mock_down.assert_called_once()


# ---------------------------------------------------------------------------
# Test: step_monitor no project_config → no teardown, no crash
# ---------------------------------------------------------------------------


def test_step_monitor_no_project_config_skips_teardown(
    db_session: Session, test_project, tmp_path: Path, daemon_config: DaemonConfig
) -> None:
    """When project_config is None (legacy call), teardown is silently skipped."""
    make_work_item(db_session)
    # Step must be in_progress so _update_parent_step can transition it to failed
    step = make_browser_step(db_session, status=StepStatus.in_progress)
    make_step_run(db_session, step, worktree_path=str(tmp_path))

    with (
        patch("orch.daemon.step_monitor.os.kill", side_effect=ProcessLookupError),
        patch("orch.daemon.browser_env.run_env_down_hook") as mock_down,
    ):
        # project_config=None (default) — backward compatible call
        monitor_running_steps(db_session, "test-proj", daemon_config)

    mock_down.assert_not_called()

    # Step should still be marked failed (teardown skip doesn't affect this)
    db_session.refresh(step)
    assert step.status == StepStatus.failed


# ---------------------------------------------------------------------------
# Test: step-restart does NOT create a pending StepRun
# ---------------------------------------------------------------------------


def test_step_restart_does_not_create_pending_step_run(db_session: Session, test_project) -> None:
    """After step-restart, no pending StepRun row should exist for the step."""
    from click.testing import CliRunner

    from orch.cli.main import cli

    # Set up: a failed step with one completed run
    make_work_item(db_session)
    step = make_browser_step(db_session, status=StepStatus.failed)
    make_step_run(db_session, step, run_number=1, status=RunStatus.failed)

    initial_run_count = db_session.query(StepRun).filter(StepRun.step_id == step.id).count()
    assert initial_run_count == 1

    @contextmanager
    def get_session():
        yield db_session

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", "test-proj", "step-restart", "F-00001", "--step", "S01"],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output

    # Step must be pending
    db_session.refresh(step)
    assert step.status == StepStatus.pending

    # No new StepRun rows should have been added
    final_run_count = db_session.query(StepRun).filter(StepRun.step_id == step.id).count()
    assert final_run_count == initial_run_count, (
        f"Expected {initial_run_count} StepRun rows after restart, "
        f"but found {final_run_count} — orphan pending row was created"
    )

    # No pending StepRun should exist
    pending_run = (
        db_session.query(StepRun)
        .filter(StepRun.step_id == step.id, StepRun.status == RunStatus.pending)
        .first()
    )
    assert pending_run is None, "step-restart created an orphan pending StepRun"


# ---------------------------------------------------------------------------
# Test: step-restart JSON output uses next_run_number (not run_number)
# ---------------------------------------------------------------------------


def test_step_restart_json_output_uses_next_run_number(db_session: Session, test_project) -> None:
    """The JSON output field is 'next_run_number', not 'run_number'."""
    import json

    from click.testing import CliRunner

    from orch.cli.main import cli

    make_work_item(db_session)
    step = make_browser_step(db_session, status=StepStatus.failed)
    make_step_run(db_session, step, run_number=3, status=RunStatus.failed)

    @contextmanager
    def get_session():
        yield db_session

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "step-restart", "F-00001", "--step", "S01"],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "next_run_number" in data
    assert data["next_run_number"] == 4  # max_run=3, so next=4
    assert "run_number" not in data
