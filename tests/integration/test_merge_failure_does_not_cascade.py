"""CR-00028 AC2 + AC3 end-to-end: merge failure does NOT cascade to later groups.

AC2: merge_failed item in group 0 → group 1 item stays pending.
AC3: migration_invalid and migration_rebase_failed also don't cascade.

Integration test using real PostgreSQL via testcontainers.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from orch.daemon.batch_manager import BatchManager
from orch.daemon.merge_queue import process_merge_queue
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
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
def daemon_config(tmp_path: Path) -> Any:
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
def manager(
    db_session: Session,
    test_project: Project,
    project_config: ProjectConfig,
    daemon_config: Any,
) -> BatchManager:
    @contextmanager
    def session_factory() -> Any:
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


def make_batch(db: Session, batch_id: str, status: BatchStatus = BatchStatus.executing) -> Batch:
    batch = Batch(
        project_id="test-proj",
        id=batch_id,
        status=status,
        max_parallel=4,
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
    worktree_info: dict[str, Any] | None = None,
) -> BatchItem:
    item = BatchItem(
        project_id="test-proj",
        batch_id=batch_id,
        work_item_id=work_item_id,
        execution_group=execution_group,
        status=status,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    if worktree_info:
        item.worktree_info = worktree_info
    db.add(item)
    db.flush()
    return item


# ---------------------------------------------------------------------------
# AC2 + AC3: merge failure does NOT cascade
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMergeFailureDoesNotCascade:
    """CR-00028 AC2 + AC3: recoverable merge failures don't cascade to dependents."""

    @pytest.fixture(autouse=True)
    def _alembic_guard(self) -> None:
        """Skip alembic guard checks in these tests."""
        from orch.db.alembic_guard import GuardStatus

        ok = GuardStatus(
            current_rev="abc",
            head_rev="abc",
            pending=[],
            multiple_heads=[],
            ok=True,
        )
        with patch("orch.daemon.batch_manager.check_db_at_head", return_value=ok):
            yield

    @pytest.mark.parametrize(
        "recoverable_status",
        [
            BatchItemStatus.merge_failed,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rebase_failed,
        ],
    )
    def test_recoverable_merge_failure_does_not_cascade(
        self,
        db_session: Session,
        manager: BatchManager,
        recoverable_status: BatchItemStatus,
        test_project: Project,
    ) -> None:
        """AC2 + AC3: group-0 recoverable failure → group-1 item stays pending.

        Scenario:
        - I1 (group=0) in recoverable status
        - I2 (group=1) in pending
        - run batch_manager.process_batches()
        - I2 must still be pending (not cascade-failed)
        """
        # Setup: 2-item batch, I1 in recoverable status, I2 pending
        make_work_item(db_session, "F-00001")
        make_work_item(db_session, "F-00002")
        batch = make_batch(db_session, "B001", status=BatchStatus.executing)

        i1 = make_batch_item(
            db_session,
            "B001",
            "F-00001",
            execution_group=0,
            status=recoverable_status,
            worktree_info={"path": "/wt/F-00001"},
        )
        i2 = make_batch_item(
            db_session,
            "B001",
            "F-00002",
            execution_group=1,
            status=BatchItemStatus.pending,
        )
        db_session.flush()

        # Run batch processing
        manager.process_batches()

        # Refresh and assert
        db_session.refresh(i1)
        db_session.refresh(i2)
        db_session.refresh(batch)

        # AC2: I1 stays in recoverable status
        assert i1.status == recoverable_status

        # AC2: I2 stays pending — no cascade
        assert i2.status == BatchItemStatus.pending, (
            f"Cascade fired for {recoverable_status.value} — dependents should stay pending"
        )

        # AC3: batch stays executing (not completed_with_errors)
        assert batch.status == BatchStatus.executing

    def test_no_batch_dependency_failed_event_on_recoverable_failure(
        self,
        db_session: Session,
        manager: BatchManager,
        test_project: Project,
    ) -> None:
        """AC2: no batch_dependency_failed event when recoverable item fails."""
        make_work_item(db_session, "F-00001")
        make_work_item(db_session, "F-00002")
        make_batch(db_session, "B001", status=BatchStatus.executing)

        make_batch_item(
            db_session,
            "B001",
            "F-00001",
            execution_group=0,
            status=BatchItemStatus.merge_failed,
            worktree_info={"path": "/wt/F-00001"},
        )
        make_batch_item(
            db_session,
            "B001",
            "F-00002",
            execution_group=1,
            status=BatchItemStatus.pending,
        )
        db_session.flush()

        manager.process_batches()
        db_session.flush()

        # Count batch_dependency_failed events
        dep_fail_events = (
            db_session.query(DaemonEvent)
            .filter(
                DaemonEvent.project_id == "test-proj",
                DaemonEvent.event_type == "batch_dependency_failed",
            )
            .all()
        )

        # AC2: no cascade event emitted
        assert len(dep_fail_events) == 0, (
            "batch_dependency_failed event should NOT be emitted for recoverable failures"
        )


@pytest.mark.integration
class TestMergeQueueMergeFailedWritesCorrectStatus:
    """AC1 in integration: merge queue writes merge_failed (not failed)."""

    def test_merge_queue_process_writes_merge_failed_on_merge_error(
        self,
        db_session: Session,
        project_config: ProjectConfig,
        daemon_config: Any,
        test_project: Project,
    ) -> None:
        """AC1: process_merge_queue → merge_failed when worktree_commit.sh exits non-zero."""
        from orch.daemon.batch_manager import BatchManager

        # Create a completed batch item with a real worktree path
        make_work_item(db_session, "F-00001")
        make_batch(db_session, "B001", status=BatchStatus.executing)

        item = make_batch_item(
            db_session,
            "B001",
            "F-00001",
            execution_group=0,
            status=BatchItemStatus.completed,
            worktree_info={"path": "/tmp/fake/worktree"},
        )
        # batch_id is already "B001" from make_batch_item call above (FK constraint)
        db_session.flush()

        @contextmanager
        def session_factory() -> Any:
            yield db_session

        _mgr = BatchManager(
            project_id="test-proj",
            project_config=project_config,
            session_factory=session_factory,
            config=daemon_config,
        )

        # Mock subprocess.run to simulate merge failure
        # Also mock run_pre_merge_rebase to return success so we hit the commit script
        from orch.daemon.migration_rebase import RebaseResult

        mock_rebase = RebaseResult(
            success=True,
            rebased=False,
            rewrites=[],
            worktree_base_sha="abc",
            current_main_sha="def",
            message="already clean",
            error_message=None,
        )

        # Mock dry-run to succeed so we reach the subprocess.run call
        mock_dry_run = MagicMock()
        mock_dry_run.success = True
        mock_dry_run.message = "dry-run ok"

        with (
            patch("orch.daemon.merge_queue.run_pre_merge_rebase", return_value=mock_rebase),
            patch("orch.daemon.merge_queue.run_pre_merge_dry_run", return_value=mock_dry_run),
            patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
        ):
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="scope gate violation"
            )
            process_merge_queue(db_session, "test-proj", project_config, daemon_config)

        db_session.refresh(item)

        # AC1: must be merge_failed, not failed
        assert item.status == BatchItemStatus.merge_failed, (
            f"Expected merge_failed but got {item.status.value}"
        )
        assert "scope gate" in (item.notes or "")
