"""Scenario 2 runtime complement to CR-00060 / P2-CR-B fix-cycle cap invariants."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orch.config import DaemonConfig
from orch.daemon import fix_cycle
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    FixCycle,
    FixStatus,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)


def _daemon_config(tmp_path: Path) -> DaemonConfig:
    """Build a minimal DaemonConfig for fix-cycle cap tests.

    Args:
        tmp_path: pytest tmp_path used for auxiliary file paths.

    Returns:
        A DaemonConfig instance with dummy (non-connectable) DB coordinates.
    """
    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("", encoding="utf-8")
    return DaemonConfig(
        db_host="127.0.0.1",
        db_port=1,
        db_name="ignored",
        db_user="ignored",
        db_password="ignored",  # noqa: S106
        db_url="postgresql+psycopg://ignored:ignored@127.0.0.1:1/ignored",
        dashboard_host="127.0.0.1",
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


def _project_config(cap: int) -> ProjectConfig:
    """Build a ProjectConfig with the given per-step fix-cycle cap.

    Args:
        cap: Maximum number of fix cycles allowed per step.

    Returns:
        A ProjectConfig for the ``test-proj`` project with ``fix_cycle_max=cap``.
    """
    return ProjectConfig(
        id="test-proj",
        display_name="Test",
        repo_root="/tmp/nonexistent",
        enabled=True,
        cli_tool="opencode",
        model="minimax",
        worktree_base=".worktrees",
        config={"fix_cycle_max": cap, "aggregate_fix_cycle_max": 50},
    )


def _seed_failed_review_step(db_session, item_id: str) -> WorkflowStep:
    """Insert a WorkItem and a failed code_review WorkflowStep into the test DB.

    Args:
        db_session: The SQLAlchemy session for the testcontainer DB.
        item_id: ID to assign to the new WorkItem (and used in step title).

    Returns:
        The committed WorkflowStep in ``StepStatus.failed`` state.
    """
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.Feature,
        title=f"Fix cycle cap {item_id}",
        status=WorkItemStatus.in_progress,
        config={},
    )
    db_session.add(item)
    db_session.flush()
    step = WorkflowStep(
        project_id="test-proj",
        work_item_id=item_id,
        step_number=1,
        step_id="S03",
        agent_label="CodeReview",
        opencode_agent="code-review-impl",
        step_type=StepType.code_review,
        command="echo review",
        status=StepStatus.failed,
        timeout_secs=600,
    )
    db_session.add(step)
    db_session.flush()
    db_session.add(
        StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.failed,
            command="echo review",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            error_message="code review failed with mandatory findings",
        )
    )
    db_session.commit()
    return step


def _run_failed_fix_cycle(db_session, step: WorkflowStep, tmp_path: Path, monkeypatch) -> None:
    """Execute one fix cycle for the given step and assert it terminates as failed.

    Args:
        db_session: The SQLAlchemy session for the testcontainer DB.
        step: The WorkflowStep to attempt a fix cycle against.
        tmp_path: pytest tmp_path used to create a fake worktree directory.
        monkeypatch: The pytest MonkeyPatch fixture used to stub ``_launch_fix_agent``.
    """
    wt = tmp_path / ".worktrees" / step.work_item_id
    wt.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        fix_cycle,
        "_launch_fix_agent",
        lambda *_args, **_kwargs: (12345, wt / "fix.log", 60, None),
    )

    fix_cycle.attempt_fix_cycle(
        db_session,
        step,
        "test-proj",
        _project_config(cap=5),
        _daemon_config(tmp_path),
        {"path": str(wt)},
    )
    db_session.refresh(step)
    cycle = (
        db_session.query(FixCycle)
        .filter(FixCycle.step_id == step.id)
        .order_by(FixCycle.cycle_number.desc())
        .first()
    )
    assert cycle is not None
    fix_cycle._fail_fix_cycle(  # noqa: SLF001
        db_session,
        cycle,
        "test-proj",
        datetime.now(UTC),
        "simulated persistent review failure",
    )
    db_session.commit()
    db_session.refresh(step)
    assert cycle.status == FixStatus.failed
    assert step.status == StepStatus.failed


@pytest.mark.integration
def test_fix_cycle_count_equals_cap_exactly(db_session, test_project, tmp_path, monkeypatch):
    """Verifies that exactly cap fix cycles are allowed and the (cap+1)th attempt is blocked."""
    cap = 5
    step = _seed_failed_review_step(db_session, "I-CAP-1")

    monkeypatch.setattr(fix_cycle, "_max_cycles_for", lambda *_args, **_kwargs: cap)
    for _ in range(cap):
        assert fix_cycle.should_attempt_fix(db_session, step, _project_config(cap)) is True
        _run_failed_fix_cycle(db_session, step, tmp_path, monkeypatch)

    assert fix_cycle.should_attempt_fix(db_session, step, _project_config(cap)) is False
    assert db_session.query(FixCycle).filter(FixCycle.step_id == step.id).count() == cap


@pytest.mark.integration
def test_no_further_fix_attempts_after_cap(db_session, test_project, tmp_path, monkeypatch):
    """Verifies that no new FixCycle rows are created once the fix-cycle cap is exhausted."""
    cap = 1
    step = _seed_failed_review_step(db_session, "I-CAP-2")

    monkeypatch.setattr(fix_cycle, "_max_cycles_for", lambda *_args, **_kwargs: cap)
    _run_failed_fix_cycle(db_session, step, tmp_path, monkeypatch)
    before = db_session.query(FixCycle).filter(FixCycle.step_id == step.id).count()

    assert fix_cycle.should_attempt_fix(db_session, step, _project_config(cap)) is False
    after = db_session.query(FixCycle).filter(FixCycle.step_id == step.id).count()
    assert before == cap
    assert after == cap


@pytest.mark.integration
def test_daemon_can_move_to_next_item_after_cap(db_session, test_project, tmp_path, monkeypatch):
    """Verifies that after one item exhausts its cap, a second item can still attempt fix cycles."""
    cap = 1
    first = _seed_failed_review_step(db_session, "I-CAP-FIRST")
    second = _seed_failed_review_step(db_session, "I-CAP-NEXT")

    monkeypatch.setattr(fix_cycle, "_max_cycles_for", lambda *_args, **_kwargs: cap)
    _run_failed_fix_cycle(db_session, first, tmp_path, monkeypatch)

    assert fix_cycle.should_attempt_fix(db_session, first, _project_config(cap)) is False
    assert fix_cycle.should_attempt_fix(db_session, second, _project_config(cap)) is True
