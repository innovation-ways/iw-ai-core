"""Integration tests for batch_manager — real PostgreSQL via testcontainers.

Tests exercise the full DB lifecycle: batch approval → item execution →
step completion → merge queue ordering.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from orch.daemon.batch_manager import BatchManager
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_config() -> ProjectConfig:
    return ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        enabled=True,
        cli_tool="opencode",
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
    """BatchManager wired to the test DB session."""

    @contextmanager
    def session_factory():
        yield db_session

    return BatchManager(
        project_id="test-proj",
        project_config=project_config,
        session_factory=session_factory,
        config=daemon_config,
    )


def make_work_item(db: Session, item_id: str, title: str = "Test Item") -> WorkItem:
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.Feature,
        title=title,
        status=WorkItemStatus.approved,
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
) -> WorkflowStep:
    step = WorkflowStep(
        project_id="test-proj",
        work_item_id=item_id,
        step_number=step_number,
        step_id=step_id,
        agent_label=f"Agent_{step_id}",
        step_type=step_type,
        status=status,
    )
    db.add(step)
    db.flush()
    return step


def make_batch(
    db: Session,
    batch_id: str,
    status: BatchStatus = BatchStatus.approved,
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
    status: BatchItemStatus = BatchItemStatus.pending,
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


# ---------------------------------------------------------------------------
# Tests: full batch lifecycle
# ---------------------------------------------------------------------------


@pytest.fixture
def _alembic_guard_ok():
    """Mock the I-00040 check_db_at_head() pre-flight in _launch_item.

    Tests in this file exercise BatchManager's lifecycle, not the alembic
    guard. The pre-flight queries the live orch DB (port 5433 in the .env
    cached engine) which we don't want hitting the test transaction.
    """
    from orch.db.alembic_guard import GuardStatus

    ok = GuardStatus(current_rev="abc", head_rev="abc", pending=[], multiple_heads=[], ok=True)
    with patch("orch.daemon.batch_manager.check_db_at_head", return_value=ok):
        yield


class TestBatchLifecycleFull:
    @pytest.fixture(autouse=True)
    def _mock_alembic_guard(self, _alembic_guard_ok):
        pass

    def test_approved_batch_transitions_to_executing(
        self, db_session: Session, manager: BatchManager, test_project
    ):
        make_work_item(db_session, "F-00001")
        batch = make_batch(db_session, "B001", status=BatchStatus.approved)
        make_batch_item(db_session, "B001", "F-00001")

        with patch.object(manager, "_launch_item"):
            manager.process_batches()

        db_session.refresh(batch)
        assert batch.status == BatchStatus.executing

    def test_pending_item_gets_launched(
        self, db_session: Session, manager: BatchManager, test_project
    ):
        make_work_item(db_session, "F-00001")
        step = make_workflow_step(db_session, "F-00001", 1, "S01")
        make_batch(db_session, "B001")
        batch_item = make_batch_item(db_session, "B001", "F-00001")
        db_session.flush()

        fake_worktree = {"path": "/wt/F-00001", "branch": "agent/F-00001", "created_at": "now"}

        with (
            patch.object(manager, "_setup_worktree", return_value=fake_worktree),
            patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen,
            patch("pathlib.Path.open", MagicMock()),
            patch("pathlib.Path.mkdir"),
        ):
            mock_popen.return_value = MagicMock(pid=12345)
            manager.process_batches()

        db_session.refresh(batch_item)
        assert batch_item.status == BatchItemStatus.executing
        db_session.refresh(step)
        assert step.status == StepStatus.in_progress

    def test_step_completion_launches_next_step(
        self, db_session: Session, manager: BatchManager, test_project
    ):
        make_work_item(db_session, "F-00001")
        make_workflow_step(db_session, "F-00001", 1, "S01", status=StepStatus.completed)
        step2 = make_workflow_step(db_session, "F-00001", 2, "S02", status=StepStatus.pending)
        make_batch(db_session, "B001", status=BatchStatus.executing)
        batch_item = make_batch_item(
            db_session,
            "B001",
            "F-00001",
            status=BatchItemStatus.executing,
        )
        batch_item.worktree_info = {"path": "/wt/F-00001", "branch": "agent/F-00001"}
        db_session.flush()

        with (
            patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen,
            patch("pathlib.Path.open", MagicMock()),
            patch("pathlib.Path.mkdir"),
        ):
            mock_popen.return_value = MagicMock(pid=22222)
            manager.process_batches()

        db_session.refresh(step2)
        assert step2.status == StepStatus.in_progress

    def test_all_steps_done_marks_item_completed(
        self, db_session: Session, manager: BatchManager, test_project
    ):
        work_item = make_work_item(db_session, "F-00001")
        make_workflow_step(db_session, "F-00001", 1, "S01", status=StepStatus.completed)
        make_batch(db_session, "B001", status=BatchStatus.executing)
        batch_item = make_batch_item(
            db_session,
            "B001",
            "F-00001",
            status=BatchItemStatus.executing,
        )
        batch_item.worktree_info = {"path": "/wt/F-00001"}
        db_session.flush()

        manager.process_batches()

        db_session.refresh(batch_item)
        assert batch_item.status == BatchItemStatus.completed
        db_session.refresh(work_item)
        assert work_item.status == WorkItemStatus.completed

    def test_all_merged_completes_batch(
        self, db_session: Session, manager: BatchManager, test_project
    ):
        make_work_item(db_session, "F-00001")
        batch = make_batch(db_session, "B001", status=BatchStatus.executing)
        make_batch_item(
            db_session,
            "B001",
            "F-00001",
            status=BatchItemStatus.merged,
        )
        db_session.flush()

        manager.process_batches()

        db_session.refresh(batch)
        assert batch.status == BatchStatus.completed


class TestExecutionGroupAdvancement:
    @pytest.fixture(autouse=True)
    def _mock_alembic_guard(self, _alembic_guard_ok):
        pass

    def test_group_1_launches_after_group_0_all_merged(
        self, db_session: Session, manager: BatchManager, test_project
    ):
        make_work_item(db_session, "F-00001")
        make_work_item(db_session, "F-00002")

        make_batch(db_session, "B001", status=BatchStatus.executing)
        make_batch_item(
            db_session, "B001", "F-00001", execution_group=0, status=BatchItemStatus.merged
        )
        bi_f002 = make_batch_item(
            db_session, "B001", "F-00002", execution_group=1, status=BatchItemStatus.pending
        )
        make_workflow_step(db_session, "F-00002", 1, "S01")
        db_session.flush()

        fake_worktree = {"path": "/wt/F-00002", "branch": "agent/F-00002", "created_at": "now"}

        with (
            patch.object(manager, "_setup_worktree", return_value=fake_worktree),
            patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen,
            patch("pathlib.Path.open", MagicMock()),
            patch("pathlib.Path.mkdir"),
        ):
            mock_popen.return_value = MagicMock(pid=33333)
            manager.process_batches()

        db_session.refresh(bi_f002)
        assert bi_f002.status == BatchItemStatus.executing

    def test_group_1_does_not_launch_while_group_0_still_executing(
        self, db_session: Session, manager: BatchManager, test_project
    ):
        make_work_item(db_session, "F-00001")
        make_work_item(db_session, "F-00002")

        make_batch(db_session, "B001", status=BatchStatus.executing)
        bi_f001 = make_batch_item(
            db_session, "B001", "F-00001", execution_group=0, status=BatchItemStatus.executing
        )
        bi_f001.worktree_info = {"path": "/wt/F-00001"}
        bi_f002 = make_batch_item(
            db_session, "B001", "F-00002", execution_group=1, status=BatchItemStatus.pending
        )
        # F-00001 has an in_progress step so _check_executing_item won't advance it
        make_workflow_step(db_session, "F-00001", 1, "S01", status=StepStatus.in_progress)
        db_session.flush()

        launched: list[str] = []

        def capture_launch(db_, item_):
            launched.append(item_.work_item_id)

        manager._launch_item = capture_launch  # type: ignore[method-assign]

        manager.process_batches()

        assert "F-00002" not in launched
        db_session.refresh(bi_f002)
        assert bi_f002.status == BatchItemStatus.pending


class TestMergeQueueIntegration:
    def test_merge_queue_oldest_first(
        self, db_session: Session, manager: BatchManager, test_project
    ):
        make_work_item(db_session, "F-00001")
        make_work_item(db_session, "F-00002")

        make_batch(db_session, "B001", status=BatchStatus.executing)

        older_item = make_batch_item(
            db_session, "B001", "F-00001", status=BatchItemStatus.completed
        )
        older_item.started_at = datetime(2024, 1, 1, tzinfo=UTC)
        older_item.worktree_info = {"path": "/wt/F-00001"}

        newer_item = make_batch_item(
            db_session, "B001", "F-00002", status=BatchItemStatus.completed
        )
        newer_item.started_at = datetime(2024, 1, 2, tzinfo=UTC)
        newer_item.worktree_info = {"path": "/wt/F-00002"}

        db_session.flush()

        def fake_commit_script(*args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            cmd = args[0] if args else kwargs.get("args", [])
            if cmd and cmd[0] == "git":
                result.stdout = ""
                result.stderr = ""
            elif cmd and "worktree_commit.sh" in str(cmd):
                result.stdout = "squash ok"
                result.stderr = ""
            else:
                result.stdout = ""
                result.stderr = ""
            return result

        with (
            patch("orch.daemon.merge_queue.subprocess.run", side_effect=fake_commit_script),
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.run_pre_merge_dry_run") as mock_dry,
            patch("orch.daemon.merge_queue.run_post_merge_apply") as mock_apply,
        ):
            mock_dry.return_value = MagicMock(
                success=True, message="ok", final_batch_state="proceed_to_merge"
            )
            mock_apply.return_value = MagicMock(success=True, message="ok")
            manager.process_merge_queue()

        db_session.refresh(older_item)
        db_session.refresh(newer_item)

        # Only F-00001 (older) should be merged; F-00002 waits for next cycle
        assert older_item.status == BatchItemStatus.merged
        assert newer_item.status == BatchItemStatus.completed

    def test_merge_queue_one_at_a_time(
        self, db_session: Session, manager: BatchManager, test_project
    ):
        make_work_item(db_session, "F-00001")
        make_work_item(db_session, "F-00002")

        make_batch(db_session, "B001", status=BatchStatus.executing)

        merging_item = make_batch_item(
            db_session, "B001", "F-00001", status=BatchItemStatus.merging
        )
        merging_item.worktree_info = {"path": "/wt/F-00001"}

        ready_item = make_batch_item(
            db_session, "B001", "F-00002", status=BatchItemStatus.completed
        )
        ready_item.worktree_info = {"path": "/wt/F-00002"}

        db_session.flush()

        with patch("orch.daemon.merge_queue.subprocess.run") as mock_run:
            manager.process_merge_queue()

        # subprocess.run should NOT be called — F-00001 is still merging
        mock_run.assert_not_called()
        db_session.refresh(ready_item)
        assert ready_item.status == BatchItemStatus.completed  # unchanged
