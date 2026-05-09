"""CR-00024: end-to-end step-monitor lifecycle in a real testcontainer DB.

Inserts a real StepRun row past 50% of its timeout, runs the daemon's
monitor_running_steps, and asserts that exactly one step_warning_50pct
DaemonEvent lands in the daemon_events table — and that a second poll
cycle does not produce a duplicate (idempotency at the DB layer).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from sqlalchemy import select

from orch.config import DaemonConfig
from orch.daemon.project_registry import ProjectConfig
from orch.daemon.step_monitor import monitor_running_steps
from orch.db.models import (
    DaemonEvent,
    Project,
    RunStatus,
    StepRun,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session as SASession


def _config(tmp_path: Path) -> DaemonConfig:
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
        stall_threshold=600,
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


def _seed_running_step(
    session: SASession,
    *,
    started_seconds_ago: int,
    timeout_secs: int,
    pid: int = 12345,
) -> StepRun:
    """Insert WorkItem → WorkflowStep → running StepRun. test_project fixture
    provides the Project row; we add the rest within the test transaction."""
    item_id = "I-99500"
    session.add(
        WorkItem(
            project_id="test-proj",
            id=item_id,
            type=WorkItemType.Issue,
            title="Lifecycle test",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.work,
            config={},
            depends_on=[],
            blocks=[],
        )
    )
    session.flush()

    step = WorkflowStep(
        project_id="test-proj",
        work_item_id=item_id,
        step_number=1,
        step_id="S01",
        agent_label="QvGate",
        opencode_agent="qv-gate",
        step_type=StepType.quality_validation,
        gate="integration-tests",
        command="make allure-integration",
        timeout_secs=timeout_secs,
    )
    session.add(step)
    session.flush()

    now = datetime.now(UTC)
    run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.running,
        pid=pid,
        started_at=now - timedelta(seconds=started_seconds_ago),
        last_heartbeat=now - timedelta(seconds=10),
        timeout_secs=timeout_secs,
    )
    session.add(run)
    session.flush()
    return run


def test_full_lifecycle_emits_single_warn_then_idempotent(
    db_session: SASession,
    test_project: Project,  # noqa: ARG001 — fixture creates the test-proj row
    tmp_path: Path,
) -> None:
    """A run past 50% emits one DaemonEvent; a second poll cycle does not duplicate."""
    run = _seed_running_step(db_session, started_seconds_ago=320, timeout_secs=600)
    run_pk = run.id

    # PID liveness is faked True so the crashed branch never fires.
    # 320s of 600s budget = 53% — past the 50% warn threshold but below 100% timeout.
    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db_session, "test-proj", _config(tmp_path), _project_config())

    # Reload to see committed state from inside monitor_running_steps.
    db_session.expire_all()

    events = (
        db_session.execute(
            select(DaemonEvent).where(
                DaemonEvent.project_id == "test-proj",
                DaemonEvent.event_type == "step_warning_50pct",
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1, f"expected exactly one warn event, got {len(events)}"
    md = events[0].event_metadata
    assert md["pid"] == 12345
    assert md["timeout_secs"] == 600
    assert 50 <= md["percent"] <= 60

    refreshed_run = db_session.get(StepRun, run_pk)
    assert refreshed_run is not None
    assert refreshed_run.warned_50pct_at is not None
    assert refreshed_run.status == RunStatus.running, "warn is non-terminal"

    # Second poll cycle: must not emit a duplicate event.
    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db_session, "test-proj", _config(tmp_path), _project_config())

    db_session.expire_all()
    events_after = (
        db_session.execute(
            select(DaemonEvent).where(
                DaemonEvent.project_id == "test-proj",
                DaemonEvent.event_type == "step_warning_50pct",
            )
        )
        .scalars()
        .all()
    )
    assert len(events_after) == 1, "second poll cycle must not duplicate the warn event"


def test_lifecycle_below_50pct_emits_no_warn(
    db_session: SASession,
    test_project: Project,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    """A run below 50% emits no warn event."""
    _seed_running_step(db_session, started_seconds_ago=200, timeout_secs=600)

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db_session, "test-proj", _config(tmp_path), _project_config())

    db_session.expire_all()
    events = (
        db_session.execute(
            select(DaemonEvent).where(
                DaemonEvent.project_id == "test-proj",
                DaemonEvent.event_type == "step_warning_50pct",
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 0


def test_lifecycle_past_timeout_emits_timeout_not_warn(
    db_session: SASession,
    test_project: Project,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    """AC5 at the DB layer: past 100% timeout emits step_timeout, not step_warning_50pct."""
    run = _seed_running_step(db_session, started_seconds_ago=700, timeout_secs=600)
    run_pk = run.id

    with patch("orch.daemon.step_monitor.os.kill", return_value=None):
        monitor_running_steps(db_session, "test-proj", _config(tmp_path), _project_config())

    db_session.expire_all()
    warn_events = (
        db_session.execute(
            select(DaemonEvent).where(
                DaemonEvent.project_id == "test-proj",
                DaemonEvent.event_type == "step_warning_50pct",
            )
        )
        .scalars()
        .all()
    )
    timeout_events = (
        db_session.execute(
            select(DaemonEvent).where(
                DaemonEvent.project_id == "test-proj",
                DaemonEvent.event_type == "step_timeout",
            )
        )
        .scalars()
        .all()
    )
    assert len(warn_events) == 0, "timeout branch must shadow the warn branch"
    assert len(timeout_events) == 1

    refreshed_run = db_session.get(StepRun, run_pk)
    assert refreshed_run is not None
    assert refreshed_run.warned_50pct_at is None, "timeout shadowed warn — marker stays NULL"
    assert refreshed_run.status == RunStatus.timeout
