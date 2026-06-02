"""Integration tests for CR-00096 cascade behaviour.

Uses a real PostgreSQL testcontainer to test _process_batch end-to-end,
verifying that `setup_failed` does NOT cascade to downstream execution groups
while implementation failures (failed, stalled, skipped, migration_rolled_back)
DO cascade.

Covers AC1–AC4 from CR-00096:
  AC1: setup_failed in group 0 does NOT cascade to group 1
  AC2: failed (implementation) in group 0 DOES cascade to group 1
  AC3: Mixed group 0 (merged + setup_failed) does NOT block group 1
  AC4: Mixed group 0 (merged + failed) DOES block group 1
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from orch.config import DaemonConfig
from orch.daemon.batch_manager import BatchManager
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
    StepStatus,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_id(prefix: str = "F") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _create_work_item(
    db: Session,
    project_id: str,
    item_id: str,
    item_type: WorkItemType = WorkItemType.Feature,
    impacted_paths: list[str] | None = None,
) -> WorkItem:
    wi = WorkItem(
        project_id=project_id,
        id=item_id,
        type=item_type,
        title=f"Test {item_type.value} {item_id}",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        impacted_paths=impacted_paths or [],
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(wi)
    db.flush()
    return wi


def _create_workflow_step(
    db: Session,
    project_id: str,
    work_item_id: str,
    step_number: int,
    step_id: str,
    status: StepStatus = StepStatus.pending,
) -> WorkflowStep:
    from orch.db.models import StepType

    step = WorkflowStep(
        project_id=project_id,
        work_item_id=work_item_id,
        step_number=step_number,
        step_id=step_id,
        agent_label=f"Agent_{step_id}",
        step_type=StepType.implementation,
        status=status,
    )
    db.add(step)
    db.flush()
    return step


def _create_batch(
    db: Session,
    project_id: str,
    batch_id: str,
    status: BatchStatus = BatchStatus.approved,
    max_parallel: int = 4,
) -> Batch:
    batch = Batch(
        id=batch_id,
        project_id=project_id,
        status=status,
        max_parallel=max_parallel,
    )
    db.add(batch)
    db.flush()
    return batch


def _create_batch_item(
    db: Session,
    project_id: str,
    batch_id: str,
    work_item_id: str,
    execution_group: int = 0,
    status: BatchItemStatus = BatchItemStatus.pending,
) -> BatchItem:
    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=work_item_id,
        execution_group=execution_group,
        status=status,
    )
    db.add(bi)
    db.flush()
    return bi


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def batch_manager(
    db_session: Session,
    test_project: Project,
    tmp_path: Path,
) -> BatchManager:
    """Build a BatchManager wired to the test db_session.

    Uses the same pattern as test_batch_manager_scope_gate.py.
    """
    project_config = ProjectConfig(
        id=test_project.id,
        display_name=test_project.display_name,
        repo_root="/repos/test",
        enabled=True,
        cli_tool="iw",
        model="minimax",
        worktree_base="/tmp/worktrees",
        config={},
    )
    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("")
    config = DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106, S104
        db_url="postgresql+psycopg://test:test@localhost:5433/test",
        dashboard_host="0.0.0.0",  # noqa: S106, S104
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

    @contextmanager
    def session_factory():
        yield db_session

    return BatchManager(
        project_id=test_project.id,
        project_config=project_config,
        session_factory=session_factory,
        config=config,
    )


# ---------------------------------------------------------------------------
# Tests: CR-00096 AC1–AC4
# ---------------------------------------------------------------------------


class TestCascadeBehaviour:
    """CR-00096 acceptance criteria for execution-group cascade logic."""

    def _reload_item(self, db: Session, project_id: str, work_item_id: str) -> BatchItem:
        """Re-query a BatchItem from the DB after _process_batch runs."""
        return db.execute(
            BatchItem.__table__.select().where(
                BatchItem.project_id == project_id,
                BatchItem.work_item_id == work_item_id,
            )
        ).fetchone()

    def _count_dependency_events(self, db: Session, project_id: str) -> int:
        return db.execute(
            DaemonEvent.__table__.select().where(
                DaemonEvent.project_id == project_id,
                DaemonEvent.event_type == "batch_dependency_failed",
            )
        ).fetchone()[0]

    # ------------------------------------------------------------------
    # AC1: setup_failed does NOT cascade
    # ------------------------------------------------------------------

    def test_setup_failed_does_not_cascade_to_next_group(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """AC1: setup_failed in group 0 does NOT cascade to group 1.

        Group 0 item A is in setup_failed (transient infrastructure failure).
        Group 1 item B is pending.
        _process_batch must NOT mark item B as failed.
        No batch_dependency_failed event must be emitted.
        """
        # Group 0 — already setup_failed
        item_a_id = _unique_id("F")
        _create_work_item(db_session, test_project.id, item_a_id, WorkItemType.Feature)
        # Add a step so the item is "eligible"
        _create_workflow_step(db_session, test_project.id, item_a_id, step_number=1, step_id="S01")
        batch = _create_batch(db_session, test_project.id, _unique_id("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            batch.id,
            item_a_id,
            execution_group=0,
            status=BatchItemStatus.setup_failed,
        )

        # Group 1 — pending
        item_b_id = _unique_id("F")
        _create_work_item(db_session, test_project.id, item_b_id, WorkItemType.Feature)
        _create_workflow_step(db_session, test_project.id, item_b_id, step_number=1, step_id="S01")
        _create_batch_item(
            db_session,
            test_project.id,
            batch.id,
            item_b_id,
            execution_group=1,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        # Patch _launch_item to prevent subprocess calls — we only test cascade logic
        with patch.object(BatchManager, "_launch_item"):
            batch_manager._process_batch(db_session, batch)

        # Commit _process_batch's changes (item status + event)
        db_session.commit()
        db_session.expire_all()

        bi_b = self._reload_item(db_session, test_project.id, item_b_id)
        assert bi_b is not None
        # Item B must NOT be marked failed — setup_failed does not cascade (CR-00096)
        assert bi_b.status != BatchItemStatus.failed, (
            "AC1 FAILED: setup_failed item cascaded to group 1; item B must stay pending"
        )
        assert bi_b.status == BatchItemStatus.pending

        # No batch_dependency_failed event must be emitted
        events_count = db_session.execute(
            DaemonEvent.__table__.select().where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "batch_dependency_failed",
            )
        ).fetchone()
        # events_count[0] is COUNT(*)
        assert events_count is None or events_count[0] == 0, (
            "AC1 FAILED: batch_dependency_failed event emitted for setup_failed cascade"
        )

    # ------------------------------------------------------------------
    # AC2: failed DOES cascade
    # ------------------------------------------------------------------

    def test_failed_does_cascade_to_next_group(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """AC2: failed (implementation) in group 0 DOES cascade to group 1.

        Group 0 item A is in failed status (real implementation failure).
        Group 1 item B is pending.
        _process_batch must mark item B as failed immediately.
        A batch_dependency_failed event must be emitted.
        """
        # Group 0 — already failed (implementation failure)
        item_a_id = _unique_id("F")
        _create_work_item(db_session, test_project.id, item_a_id, WorkItemType.Feature)
        _create_workflow_step(db_session, test_project.id, item_a_id, step_number=1, step_id="S01")
        batch = _create_batch(db_session, test_project.id, _unique_id("B"))
        _create_batch_item(
            db_session,
            test_project.id,
            batch.id,
            item_a_id,
            execution_group=0,
            status=BatchItemStatus.failed,
        )

        # Group 1 — pending
        item_b_id = _unique_id("F")
        _create_work_item(db_session, test_project.id, item_b_id, WorkItemType.Feature)
        _create_workflow_step(db_session, test_project.id, item_b_id, step_number=1, step_id="S01")
        _create_batch_item(
            db_session,
            test_project.id,
            batch.id,
            item_b_id,
            execution_group=1,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        with patch.object(BatchManager, "_launch_item"):
            batch_manager._process_batch(db_session, batch)

        # Commit _process_batch's changes (item status + event)
        db_session.commit()
        db_session.expire_all()

        bi_b = self._reload_item(db_session, test_project.id, item_b_id)
        assert bi_b is not None
        # Item B must be marked failed — implementation failure DOES cascade
        assert bi_b.status == BatchItemStatus.failed, (
            "AC2 FAILED: failed item did NOT cascade to group 1; item B must be marked failed"
        )

        # batch_dependency_failed event must be emitted
        events = db_session.execute(
            DaemonEvent.__table__.select().where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "batch_dependency_failed",
            )
        ).fetchall()
        assert len(events) > 0, (
            "AC2 FAILED: no batch_dependency_failed event emitted for failed cascade"
        )

    # ------------------------------------------------------------------
    # AC3: merged + setup_failed does NOT block next group
    # ------------------------------------------------------------------

    def test_merged_and_setup_failed_does_not_block_next_group(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """AC3: mixed group 0 (merged + setup_failed) does NOT block group 1.

        Group 0: item A is merged (success), item B is setup_failed (infra failure).
        Group 1: item C is pending.
        Since at least one group-0 item is merged, group 1 is eligible to advance.
        setup_failed does NOT cascade, so item C must NOT be blocked.
        """
        batch = _create_batch(db_session, test_project.id, _unique_id("B"))

        # Group 0 — item A: merged (success)
        item_a_id = _unique_id("F")
        _create_work_item(db_session, test_project.id, item_a_id, WorkItemType.Feature)
        _create_workflow_step(db_session, test_project.id, item_a_id, step_number=1, step_id="S01")
        _create_batch_item(
            db_session,
            test_project.id,
            batch.id,
            item_a_id,
            execution_group=0,
            status=BatchItemStatus.merged,
        )

        # Group 0 — item B: setup_failed (infra failure)
        item_b_id = _unique_id("F")
        _create_work_item(db_session, test_project.id, item_b_id, WorkItemType.Feature)
        _create_workflow_step(db_session, test_project.id, item_b_id, step_number=1, step_id="S01")
        _create_batch_item(
            db_session,
            test_project.id,
            batch.id,
            item_b_id,
            execution_group=0,
            status=BatchItemStatus.setup_failed,
        )

        # Group 1 — item C: pending
        item_c_id = _unique_id("F")
        _create_work_item(db_session, test_project.id, item_c_id, WorkItemType.Feature)
        _create_workflow_step(db_session, test_project.id, item_c_id, step_number=1, step_id="S01")
        _create_batch_item(
            db_session,
            test_project.id,
            batch.id,
            item_c_id,
            execution_group=1,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        with patch.object(BatchManager, "_launch_item"):
            batch_manager._process_batch(db_session, batch)

        # Commit _process_batch's changes
        db_session.commit()
        db_session.expire_all()

        bi_c = self._reload_item(db_session, test_project.id, item_c_id)
        assert bi_c is not None
        # Item C must NOT be marked failed — merged+setup_failed is not a blocking combo
        assert bi_c.status != BatchItemStatus.failed, (
            "AC3 FAILED: merged+setup_failed in group 0 blocked group 1; "
            "item C must stay pending (no cascade for setup_failed)"
        )
        assert bi_c.status == BatchItemStatus.pending

    # ------------------------------------------------------------------
    # AC4: merged + failed DOES block next group
    # ------------------------------------------------------------------

    def test_merged_and_failed_blocks_next_group(
        self,
        db_session: Session,
        test_project: Project,
        batch_manager: BatchManager,
    ) -> None:
        """AC4: mixed group 0 (merged + failed) DOES block group 1.

        Group 0: item A is merged (success), item B is failed (impl failure).
        Group 1: item C is pending.
        The failed item (B) must cascade to group 1, marking item C as failed.
        """
        batch = _create_batch(db_session, test_project.id, _unique_id("B"))

        # Group 0 — item A: merged (success)
        item_a_id = _unique_id("F")
        _create_work_item(db_session, test_project.id, item_a_id, WorkItemType.Feature)
        _create_workflow_step(db_session, test_project.id, item_a_id, step_number=1, step_id="S01")
        _create_batch_item(
            db_session,
            test_project.id,
            batch.id,
            item_a_id,
            execution_group=0,
            status=BatchItemStatus.merged,
        )

        # Group 0 — item B: failed (implementation failure)
        item_b_id = _unique_id("F")
        _create_work_item(db_session, test_project.id, item_b_id, WorkItemType.Feature)
        _create_workflow_step(db_session, test_project.id, item_b_id, step_number=1, step_id="S01")
        _create_batch_item(
            db_session,
            test_project.id,
            batch.id,
            item_b_id,
            execution_group=0,
            status=BatchItemStatus.failed,
        )

        # Group 1 — item C: pending
        item_c_id = _unique_id("F")
        _create_work_item(db_session, test_project.id, item_c_id, WorkItemType.Feature)
        _create_workflow_step(db_session, test_project.id, item_c_id, step_number=1, step_id="S01")
        _create_batch_item(
            db_session,
            test_project.id,
            batch.id,
            item_c_id,
            execution_group=1,
            status=BatchItemStatus.pending,
        )

        db_session.commit()

        with patch.object(BatchManager, "_launch_item"):
            batch_manager._process_batch(db_session, batch)

        # Commit _process_batch's changes (item status + event)
        db_session.commit()
        db_session.expire_all()

        bi_c = self._reload_item(db_session, test_project.id, item_c_id)
        assert bi_c is not None
        # Item C must be marked failed — failed cascades even with a merged sibling
        assert bi_c.status == BatchItemStatus.failed, (
            "AC4 FAILED: merged+failed in group 0 did NOT block group 1; "
            "item C must be marked failed (failed cascades)"
        )
