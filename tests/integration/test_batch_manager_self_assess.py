"""Integration tests for BatchManager soft-step semantics with self_assess.

AC3: a self_assess step that fails does NOT trigger a fix cycle and the
batch_item still proceeds to merging/completed.

Boundary: an implementation step that fails DOES trigger fix-cycle machinery.
Negative: verify the soft-step logic is narrow to self_assess only.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from orch.daemon.batch_manager import BatchManager
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    FixCycle,
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
    from pathlib import Path

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Fixtures (mirror test_batch_manager.py patterns)
# ---------------------------------------------------------------------------


@pytest.fixture
def project_config() -> ProjectConfig:
    return ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        enabled=True,
        cli_tool="opencode",
        model="minimax",
        worktree_base=".worktrees",
        config={},
    )


@pytest.fixture
def daemon_config(tmp_path: Path):
    from orch.config import DaemonConfig

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


@pytest.fixture
def manager(db_session: Session, test_project, project_config, daemon_config) -> BatchManager:
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
# Helpers
# ---------------------------------------------------------------------------


def make_work_item(
    db: Session,
    item_id: str,
    title: str = "Test Item",
    status: WorkItemStatus = WorkItemStatus.in_progress,
) -> WorkItem:
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.Feature,
        title=title,
        status=status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(item)
    db.flush()
    return item


def make_workflow_step(
    db: Session,
    item_id: str,
    step_number: int,
    step_id: str,
    step_type: StepType = StepType.implementation,
    status: StepStatus = StepStatus.pending,
    agent_label: str = "Agent",
) -> WorkflowStep:
    step = WorkflowStep(
        project_id="test-proj",
        work_item_id=item_id,
        step_number=step_number,
        step_id=step_id,
        agent_label=agent_label,
        step_type=step_type,
        status=status,
    )
    db.add(step)
    db.flush()
    return step


def make_batch(
    db: Session,
    batch_id: str,
    status: BatchStatus = BatchStatus.executing,
    max_parallel: int = 4,
) -> Batch:
    batch = Batch(
        project_id="test-proj",
        id=batch_id,
        status=status,
        max_parallel=max_parallel,
        cli_tool="opencode",
        auto_publish=False,
    )
    db.add(batch)
    db.flush()
    return batch


def make_batch_item(
    db: Session,
    batch_id: str,
    work_item_id: str,
    execution_group: int = 0,
    status: BatchItemStatus = BatchItemStatus.executing,
) -> BatchItem:
    item = BatchItem(
        project_id="test-proj",
        batch_id=batch_id,
        work_item_id=work_item_id,
        execution_group=execution_group,
        status=status,
    )
    db.add(item)
    db.flush()
    return item


def make_step_run(
    db: Session,
    step: WorkflowStep,
    run_number: int = 1,
    status: RunStatus = RunStatus.completed,
    worktree_path: str | None = None,
) -> StepRun:
    run = StepRun(
        step_id=step.id,
        run_number=run_number,
        status=status,
        worktree_path=worktree_path,
    )
    db.add(run)
    db.flush()
    return run


# ---------------------------------------------------------------------------
# Alembic guard mock (shared with test_batch_manager.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def _alembic_guard_ok():
    from orch.db.alembic_guard import GuardStatus

    ok = GuardStatus(current_rev="abc", head_rev="abc", pending=[], multiple_heads=[], ok=True)
    with patch("orch.daemon.batch_manager.check_db_at_head", return_value=ok):
        yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSelfAssessSoftStep:
    """AC3 + Invariant 1: self_assess failures never block merge."""

    @pytest.fixture(autouse=True)
    def _mock_alembic_guard(self, _alembic_guard_ok):
        pass

    def test_self_assess_failure_does_not_block_merge(
        self,
        db_session: Session,
        manager: BatchManager,
        test_project,
    ) -> None:
        """A self_assess step that fails lets the batch_item proceed to merging."""
        # Item has S01 (completed) → S02 (self_assess, failed) → no more steps
        make_work_item(db_session, "F-00001", status=WorkItemStatus.in_progress)
        make_workflow_step(
            db_session,
            "F-00001",
            1,
            "S01",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        self_assess_step = make_workflow_step(
            db_session,
            "F-00001",
            2,
            "S02",
            step_type=StepType.self_assess,
            status=StepStatus.failed,
            agent_label="SelfAssess",
        )
        make_batch(db_session, "B001", status=BatchStatus.executing)
        batch_item = make_batch_item(
            db_session,
            "B001",
            "F-00001",
            status=BatchItemStatus.executing,
        )
        batch_item.worktree_info = {"path": "/wt/F-00001", "branch": "agent/F-00001"}
        make_step_run(
            db_session,
            self_assess_step,
            status=RunStatus.failed,
            worktree_path="/wt/F-00001",
        )
        db_session.flush()

        # _check_executing_item must NOT raise, must not create a FixCycle
        manager.process_batches()

        # batch_item should advance to completed (all steps resolved, no fix cycle needed)
        db_session.refresh(batch_item)
        assert batch_item.status == BatchItemStatus.completed

        # Verify NO FixCycle was created for the self_assess step
        fix_cycles = (
            db_session.query(FixCycle)
            .filter(
                FixCycle.step_id == self_assess_step.id,
            )
            .all()
        )
        assert len(fix_cycles) == 0

    def test_self_assess_failed_renders_with_partial_data(
        self,
        db_session: Session,
        manager: BatchManager,
        test_project,
        tmp_path: Path,
    ) -> None:
        """A self_assess step that failed still allows the item to complete."""
        # Item with S01 completed → self_assess failed
        make_work_item(db_session, "F-00001", status=WorkItemStatus.in_progress)
        make_workflow_step(
            db_session,
            "F-00001",
            1,
            "S01",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        self_assess_step = make_workflow_step(
            db_session,
            "F-00001",
            2,
            "S02",
            step_type=StepType.self_assess,
            status=StepStatus.failed,
            agent_label="SelfAssess",
        )
        make_batch(db_session, "B001", status=BatchStatus.executing)
        batch_item = make_batch_item(
            db_session,
            "B001",
            "F-00001",
            status=BatchItemStatus.executing,
        )
        batch_item.worktree_info = {"path": "/wt/F-00001", "branch": "agent/F-00001"}

        # Write a partial findings file before failure
        reports_dir = tmp_path / "ai-dev" / "work" / "F-00001" / "reports"
        reports_dir.mkdir(parents=True)
        findings_file = reports_dir / "F-00001_self_assess_findings.json"
        findings_file.write_text(
            '{"narrative_md":"Partial before crash","findings":[]}',
            encoding="utf-8",
        )
        self_assess_step.report_file = str(reports_dir / "F-00001_self_assess_report.md")
        make_step_run(
            db_session,
            self_assess_step,
            status=RunStatus.failed,
            worktree_path="/wt/F-00001",
        )
        db_session.flush()

        manager.process_batches()

        db_session.refresh(batch_item)
        assert batch_item.status == BatchItemStatus.completed


class TestImplementationFailureBlocksMerge:
    """Negative: implementation step failures DO trigger fix-cycle machinery."""

    @pytest.fixture(autouse=True)
    def _mock_alembic_guard(self, _alembic_guard_ok):
        pass

    def test_implementation_failure_does_not_advance_to_completed(
        self,
        db_session: Session,
        manager: BatchManager,
        test_project,
    ) -> None:
        """An implementation step that fails keeps batch_item in executing state."""
        # Item has S01 (implementation, failed) — no other steps
        make_work_item(db_session, "F-00001", status=WorkItemStatus.in_progress)
        impl_step = make_workflow_step(
            db_session,
            "F-00001",
            1,
            "S01",
            step_type=StepType.implementation,
            status=StepStatus.failed,
            agent_label="Backend",
        )
        make_batch(db_session, "B001", status=BatchStatus.executing)
        batch_item = make_batch_item(
            db_session,
            "B001",
            "F-00001",
            status=BatchItemStatus.executing,
        )
        batch_item.worktree_info = {"path": "/wt/F-00001", "branch": "agent/F-00001"}
        make_step_run(
            db_session,
            impl_step,
            status=RunStatus.failed,
            worktree_path="/wt/F-00001",
        )
        db_session.flush()

        manager.process_batches()

        # Item should NOT advance to completed — implementation failures block
        db_session.refresh(batch_item)
        assert batch_item.status != BatchItemStatus.completed

    def test_self_assess_timeout_is_soft(
        self,
        db_session: Session,
        manager: BatchManager,
        test_project,
    ) -> None:
        """A self_assess step that times out also does not block merge."""
        make_work_item(db_session, "F-00001", status=WorkItemStatus.in_progress)
        make_workflow_step(
            db_session,
            "F-00001",
            1,
            "S01",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        self_assess_step = make_workflow_step(
            db_session,
            "F-00001",
            2,
            "S02",
            step_type=StepType.self_assess,
            status=StepStatus.failed,
            agent_label="SelfAssess",
        )
        make_batch(db_session, "B001", status=BatchStatus.executing)
        batch_item = make_batch_item(
            db_session,
            "B001",
            "F-00001",
            status=BatchItemStatus.executing,
        )
        batch_item.worktree_info = {"path": "/wt/F-00001", "branch": "agent/F-00001"}
        make_step_run(
            db_session,
            self_assess_step,
            status=RunStatus.timeout,
            worktree_path="/wt/F-00001",
        )
        db_session.flush()

        manager.process_batches()

        db_session.refresh(batch_item)
        assert batch_item.status == BatchItemStatus.completed
        fix_cycles = (
            db_session.query(FixCycle)
            .filter(
                FixCycle.step_id == self_assess_step.id,
            )
            .all()
        )
        assert len(fix_cycles) == 0
