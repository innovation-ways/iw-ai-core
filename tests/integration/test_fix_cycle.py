"""Integration tests for fix cycle logic against a real PostgreSQL testcontainer."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from orch.config import DaemonConfig
from orch.daemon.fix_cycle import (
    attempt_fix_cycle,
    check_active_fix_cycles,
    should_attempt_fix,
)
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    FixCycle,
    FixStatus,
    FixTrigger,
    Project,
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project_config(fix_cycle_max: int = 5) -> ProjectConfig:
    return ProjectConfig(
        id="test-proj",
        display_name="Test",
        repo_root="/repos/test",
        enabled=True,
        cli_tool="claude",
        worktree_base="/repos/test/.worktrees",
        config={"fix_cycle_max": fix_cycle_max},
    )


def _daemon_config() -> DaemonConfig:
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
        pid_file="/tmp/test-daemon.pid",  # noqa: S108
        archive_dir="/tmp/test-archive",  # noqa: S108
        archive_ttl=90,
        log_level="DEBUG",
        log_file="/tmp/test-daemon.log",  # noqa: S108
    )


def _make_item(db: Any, status: WorkItemStatus = WorkItemStatus.in_progress) -> WorkItem:
    item = WorkItem(
        project_id="test-proj",
        id="CR-00001",
        type=WorkItemType.ChangeRequest,
        title="Test item",
        status=status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(item)
    db.flush()
    return item


def _make_step(
    db: Any,
    step_type: StepType = StepType.code_review,
    status: StepStatus = StepStatus.failed,
    step_id: str = "S02",
) -> WorkflowStep:
    step = WorkflowStep(
        project_id="test-proj",
        work_item_id="CR-00001",
        step_number=2,
        step_id=step_id,
        agent_label="CodeReview",
        step_type=step_type,
        status=status,
    )
    db.add(step)
    db.flush()
    return step


def _make_step_run(
    db: Any,
    step: WorkflowStep,
    status: RunStatus = RunStatus.failed,
    error_message: str = "Review found 2 mandatory findings",
) -> StepRun:
    run = StepRun(
        step_id=step.id,
        run_number=1,
        status=status,
        error_message=error_message,
    )
    db.add(run)
    db.flush()
    return run


def _make_fix_cycle(
    db: Any,
    step: WorkflowStep,
    cycle_number: int = 1,
    status: FixStatus = FixStatus.completed,
) -> FixCycle:
    fc = FixCycle(
        step_id=step.id,
        cycle_number=cycle_number,
        trigger_type=FixTrigger.code_review,
        status=status,
    )
    db.add(fc)
    db.flush()
    return fc


# ---------------------------------------------------------------------------
# should_attempt_fix
# ---------------------------------------------------------------------------


def test_should_attempt_fix_code_review(
    db_session: Any,
    test_project: Project,
) -> None:
    _make_item(db_session)
    step = _make_step(db_session, step_type=StepType.code_review)
    assert should_attempt_fix(db_session, step, _project_config()) is True


def test_should_attempt_fix_code_review_final(
    db_session: Any,
    test_project: Project,
) -> None:
    _make_item(db_session)
    step = _make_step(db_session, step_type=StepType.code_review_final)
    assert should_attempt_fix(db_session, step, _project_config()) is True


def test_should_not_attempt_fix_implementation(
    db_session: Any,
    test_project: Project,
) -> None:
    _make_item(db_session)
    step = _make_step(db_session, step_type=StepType.implementation)
    assert should_attempt_fix(db_session, step, _project_config()) is False


def test_should_not_attempt_fix_max_reached(
    db_session: Any,
    test_project: Project,
) -> None:
    _make_item(db_session)
    step = _make_step(db_session, step_type=StepType.code_review)
    # Create 5 completed fix cycles
    for i in range(1, 6):
        _make_fix_cycle(db_session, step, cycle_number=i)
    assert should_attempt_fix(db_session, step, _project_config(fix_cycle_max=5)) is False


def test_should_attempt_fix_under_max(
    db_session: Any,
    test_project: Project,
) -> None:
    _make_item(db_session)
    step = _make_step(db_session, step_type=StepType.code_review)
    _make_fix_cycle(db_session, step, cycle_number=1)
    _make_fix_cycle(db_session, step, cycle_number=2)
    assert should_attempt_fix(db_session, step, _project_config(fix_cycle_max=5)) is True


# ---------------------------------------------------------------------------
# attempt_fix_cycle
# ---------------------------------------------------------------------------


@patch("orch.daemon.fix_cycle._launch_fix_agent")
def test_attempt_fix_cycle_creates_record(
    mock_launch: Any,
    db_session: Any,
    test_project: Project,
) -> None:
    mock_launch.return_value = (12345, "/tmp/log.log", 2700)  # noqa: S108

    _make_item(db_session)
    step = _make_step(db_session, step_type=StepType.code_review, status=StepStatus.failed)
    _make_step_run(db_session, step)

    attempt_fix_cycle(
        db_session,
        step,
        "test-proj",
        _project_config(),
        _daemon_config(),
        {"path": "/tmp/worktree"},  # noqa: S108
    )

    # FixCycle record should exist
    cycles = db_session.query(FixCycle).filter_by(step_id=step.id).all()
    assert len(cycles) == 1
    assert cycles[0].cycle_number == 1
    assert cycles[0].status == FixStatus.in_progress
    assert cycles[0].trigger_type == FixTrigger.code_review
    assert cycles[0].fix_metadata["pid"] == 12345

    # Step should be in needs_fix
    db_session.refresh(step)
    assert step.status == StepStatus.needs_fix


@patch("orch.daemon.fix_cycle._launch_fix_agent")
def test_attempt_fix_cycle_increments_cycle_number(
    mock_launch: Any,
    db_session: Any,
    test_project: Project,
) -> None:
    mock_launch.return_value = (12345, "/tmp/log.log", 2700)  # noqa: S108

    _make_item(db_session)
    step = _make_step(db_session, step_type=StepType.code_review, status=StepStatus.failed)
    _make_step_run(db_session, step)
    # Create 2 existing cycles
    _make_fix_cycle(db_session, step, cycle_number=1)
    _make_fix_cycle(db_session, step, cycle_number=2)

    attempt_fix_cycle(
        db_session,
        step,
        "test-proj",
        _project_config(),
        _daemon_config(),
        {"path": "/tmp/worktree"},  # noqa: S108
    )

    cycles = (
        db_session.query(FixCycle).filter_by(step_id=step.id).order_by(FixCycle.cycle_number).all()
    )
    assert len(cycles) == 3
    assert cycles[2].cycle_number == 3


# ---------------------------------------------------------------------------
# check_active_fix_cycles — completion
# ---------------------------------------------------------------------------


@patch("orch.daemon.fix_cycle._is_pid_alive", return_value=False)
def test_check_active_cycles_completes_on_pid_death(
    mock_alive: Any,
    db_session: Any,
    test_project: Project,
) -> None:
    _make_item(db_session)
    step = _make_step(db_session, step_type=StepType.code_review, status=StepStatus.needs_fix)

    fc = FixCycle(
        step_id=step.id,
        cycle_number=1,
        trigger_type=FixTrigger.code_review,
        status=FixStatus.in_progress,
        fix_metadata={"pid": 99999, "timeout_secs": 2700},
    )
    db_session.add(fc)
    db_session.flush()

    check_active_fix_cycles(db_session, "test-proj", _project_config(), _daemon_config())

    db_session.refresh(fc)
    assert fc.status == FixStatus.completed
    assert fc.completed_at is not None

    # Step should be reset to pending for re-review
    db_session.refresh(step)
    assert step.status == StepStatus.pending


@patch("orch.daemon.fix_cycle._is_pid_alive", return_value=True)
def test_check_active_cycles_waits_while_alive(
    mock_alive: Any,
    db_session: Any,
    test_project: Project,
) -> None:
    from datetime import UTC, datetime

    _make_item(db_session)
    step = _make_step(db_session, step_type=StepType.code_review, status=StepStatus.needs_fix)

    fc = FixCycle(
        step_id=step.id,
        cycle_number=1,
        trigger_type=FixTrigger.code_review,
        status=FixStatus.in_progress,
        started_at=datetime.now(UTC),
        fix_metadata={"pid": 99999, "timeout_secs": 2700},
    )
    db_session.add(fc)
    db_session.flush()

    check_active_fix_cycles(db_session, "test-proj", _project_config(), _daemon_config())

    db_session.refresh(fc)
    assert fc.status == FixStatus.in_progress  # Still running

    db_session.refresh(step)
    assert step.status == StepStatus.needs_fix  # Still needs_fix


# ---------------------------------------------------------------------------
# check_active_fix_cycles — timeout
# ---------------------------------------------------------------------------


@patch("orch.daemon.fix_cycle._kill_pid")
@patch("orch.daemon.fix_cycle._is_pid_alive", return_value=True)
def test_check_active_cycles_kills_on_timeout(
    mock_alive: Any,
    mock_kill: Any,
    db_session: Any,
    test_project: Project,
) -> None:
    from datetime import UTC, datetime, timedelta

    _make_item(db_session)
    step = _make_step(db_session, step_type=StepType.code_review, status=StepStatus.needs_fix)

    fc = FixCycle(
        step_id=step.id,
        cycle_number=1,
        trigger_type=FixTrigger.code_review,
        status=FixStatus.in_progress,
        started_at=datetime.now(UTC) - timedelta(seconds=3000),  # Well past timeout
        fix_metadata={"pid": 99999, "timeout_secs": 2700},
    )
    db_session.add(fc)
    db_session.flush()

    check_active_fix_cycles(db_session, "test-proj", _project_config(), _daemon_config())

    mock_kill.assert_called_once_with(99999)

    db_session.refresh(fc)
    assert fc.status == FixStatus.failed

    db_session.refresh(step)
    assert step.status == StepStatus.failed
