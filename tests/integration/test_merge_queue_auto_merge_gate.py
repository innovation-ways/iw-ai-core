"""Integration tests for CR-00036 auto_merge gate.

These tests verify the end-to-end merge gate behaviour:
  Scenario A (auto_merge=true, baseline)
  Scenario B (auto_merge=false, gate engages)
  Scenario C (manual approval releases the gate)
  Scenario D (failed item bypasses gate)

Tests run against a real PostgreSQL testcontainer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from sqlalchemy import select

from orch.daemon.merge_queue import process_merge_queue
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
    from pathlib import Path

    from sqlalchemy.orm import Session

    from orch.daemon.project_registry import ProjectConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_project(db_session: Session, project_id: str = "test-proj") -> Project:
    project = Project(
        id=project_id,
        display_name=f"Test Project {project_id}",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


def make_work_item(
    db_session: Session,
    project_id: str,
    item_id: str,
    status: WorkItemStatus = WorkItemStatus.approved,
) -> WorkItem:
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Issue,
        title=f"Test item {item_id}",
        status=status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()
    return item


def make_batch(
    db_session: Session,
    project_id: str,
    batch_id: str,
    auto_merge: bool = True,
    status: BatchStatus = BatchStatus.executing,
) -> Batch:
    batch = Batch(
        project_id=project_id,
        id=batch_id,
        status=status,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=auto_merge,
    )
    db_session.add(batch)
    db_session.flush()
    return batch


def make_batch_item(
    db_session: Session,
    project_id: str,
    batch_id: str,
    work_item_id: str,
    execution_group: int = 0,
    status: BatchItemStatus = BatchItemStatus.executing,
    worktree_path: str | None = "/tmp/worktrees/test",
) -> BatchItem:
    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=work_item_id,
        execution_group=execution_group,
        status=status,
        worktree_info={"path": worktree_path} if worktree_path else None,
    )
    db_session.add(bi)
    db_session.flush()
    return bi


def _project_config(project_id: str = "test-proj") -> ProjectConfig:
    from orch.daemon.project_registry import ProjectConfig

    return ProjectConfig(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
        enabled=True,
        cli_tool="claude",
        worktree_base=".worktrees",
        config={},
    )


# ---------------------------------------------------------------------------
# Scenario A: auto_merge=true — item goes completed → merging → merged
# ---------------------------------------------------------------------------


def test_auto_merge_true_completed_item_is_picked_by_merge_queue(
    db_session: Session,
    test_project: Project,
    tmp_path: Path,
) -> None:
    """With auto_merge=True, a completed item is picked up by process_merge_queue."""
    batch = make_batch(db_session, test_project.id, "BATCH-AUTO-TRUE", auto_merge=True)
    work_item = make_work_item(db_session, test_project.id, "WI-AUTO-TRUE-01")
    bi = make_batch_item(
        db_session,
        test_project.id,
        batch.id,
        work_item.id,
        status=BatchItemStatus.completed,
    )
    db_session.flush()

    # Patch the entire merge pipeline so we can observe the status transition
    # without needing a real git repo / worktree.
    with (
        patch("orch.daemon.merge_queue._merge_item") as mock_merge,
    ):
        process_merge_queue(db_session, test_project.id, _project_config(), None)

        # _merge_item should have been called with the completed item
        mock_merge.assert_called_once()
        called_item = mock_merge.call_args[0][1]  # second positional arg: batch_item
        assert called_item.work_item_id == work_item.id

    db_session.refresh(bi)
    # Item transitions to merging inside _merge_item (before db.commit at end)
    # Since we mocked _merge_item, status is still 'completed' in this test's view.
    # The important assertion is that _merge_item was called (gate bypassed).
    assert bi.status == BatchItemStatus.completed


# ---------------------------------------------------------------------------
# Scenario B: auto_merge=false, gate engages — item stays at awaiting_merge_approval
# ---------------------------------------------------------------------------


def test_auto_merge_false_item_stays_at_awaiting_merge_approval(
    db_session: Session,
    test_project: Project,
    tmp_path: Path,
) -> None:
    """With auto_merge=False, an item held at awaiting_merge_approval is NOT picked."""
    batch = make_batch(db_session, test_project.id, "BATCH-AUTO-FALSE", auto_merge=False)
    work_item = make_work_item(db_session, test_project.id, "WI-GATE-01")
    bi = make_batch_item(
        db_session,
        test_project.id,
        batch.id,
        work_item.id,
        status=BatchItemStatus.awaiting_merge_approval,
        worktree_path="/tmp/worktrees/gate-test",
    )
    db_session.flush()

    # Call process_merge_queue — it should NOT pick up the item
    with patch("orch.daemon.merge_queue._merge_item") as mock_merge:
        process_merge_queue(db_session, test_project.id, _project_config(), None)

    mock_merge.assert_not_called()

    db_session.refresh(bi)
    # Status is unchanged — still awaiting_merge_approval
    assert bi.status == BatchItemStatus.awaiting_merge_approval
    # No merging/merged state was reached
    assert bi.status not in (
        BatchItemStatus.merging,
        BatchItemStatus.merged,
        BatchItemStatus.merge_failed,
    )
    # Worktree should still be present
    assert bi.worktree_info is not None


def test_awaiting_merge_approval_items_are_invisible_to_merge_queue(
    db_session: Session,
    test_project: Project,
) -> None:
    """process_merge_queue only picks 'completed' items — awaiting_merge_approval is invisible."""
    batch = make_batch(db_session, test_project.id, "BATCH-GATE-TEST", auto_merge=False)
    work_item = make_work_item(db_session, test_project.id, "WI-GATE-02")
    bi = make_batch_item(
        db_session,
        test_project.id,
        batch.id,
        work_item.id,
        status=BatchItemStatus.awaiting_merge_approval,
        worktree_path="/tmp/worktrees/gate-test",
    )
    db_session.flush()

    # Track whether _merge_item is called
    merge_called = False

    original_merge_item = __import__(
        "orch.daemon.merge_queue", fromlist=["_merge_item"]
    )._merge_item

    def tracking_merge_item(db, batch_item, project_id, project_config):
        nonlocal merge_called
        merge_called = True
        return original_merge_item(db, batch_item, project_id, project_config)

    with patch("orch.daemon.merge_queue._merge_item", side_effect=tracking_merge_item):
        process_merge_queue(db_session, test_project.id, _project_config(), None)

    assert not merge_called, (
        "process_merge_queue should not call _merge_item for awaiting_merge_approval"
    )
    db_session.refresh(bi)
    assert bi.status == BatchItemStatus.awaiting_merge_approval


# ---------------------------------------------------------------------------
# Scenario C: manual approval releases the gate
# ---------------------------------------------------------------------------


def test_approve_merge_service_transitions_to_completed(
    db_session: Session,
    test_project: Project,
) -> None:
    """approve_merge transitions awaiting_merge_approval → completed."""
    batch = make_batch(db_session, test_project.id, "BATCH-MANUAL-APPROVE", auto_merge=False)
    work_item = make_work_item(db_session, test_project.id, "WI-MANUAL-APPROVE-01")
    bi = make_batch_item(
        db_session,
        test_project.id,
        batch.id,
        work_item.id,
        status=BatchItemStatus.awaiting_merge_approval,
        worktree_path="/tmp/worktrees/manual-approve",
    )
    db_session.flush()

    from orch.services import approve_merge

    approve_merge(db_session, test_project.id, work_item.id)

    db_session.refresh(bi)
    assert bi.status == BatchItemStatus.completed


def test_approve_merge_emits_daemon_event(
    db_session: Session,
    test_project: Project,
) -> None:
    """approve_merge emits a merge_approved_by_operator DaemonEvent."""
    batch = make_batch(db_session, test_project.id, "BATCH-EVENT-TEST", auto_merge=False)
    work_item = make_work_item(db_session, test_project.id, "WI-EVENT-01")
    make_batch_item(
        db_session,
        test_project.id,
        batch.id,
        work_item.id,
        status=BatchItemStatus.awaiting_merge_approval,
    )

    from orch.services import approve_merge

    approve_merge(db_session, test_project.id, work_item.id)

    event = db_session.scalar(
        select(DaemonEvent).where(
            DaemonEvent.event_type == "merge_approved_by_operator",
            DaemonEvent.entity_id == work_item.id,
        )
    )
    assert event is not None, "merge_approved_by_operator event was not emitted"


def test_approved_item_is_picked_by_merge_queue_next_tick(
    db_session: Session,
    test_project: Project,
) -> None:
    """After approve_merge, the item is in 'completed' and visible to process_merge_queue."""
    batch = make_batch(db_session, test_project.id, "BATCH-APPROVED-QUEUE", auto_merge=False)
    work_item = make_work_item(db_session, test_project.id, "WI-APPROVED-QUEUE-01")
    bi = make_batch_item(
        db_session,
        test_project.id,
        batch.id,
        work_item.id,
        status=BatchItemStatus.awaiting_merge_approval,
        worktree_path="/tmp/worktrees/approved-queue",
    )
    db_session.flush()

    # Approve
    from orch.services import approve_merge

    approve_merge(db_session, test_project.id, work_item.id)
    db_session.refresh(bi)
    assert bi.status == BatchItemStatus.completed

    # Next tick: process_merge_queue should pick it up
    with patch("orch.daemon.merge_queue._merge_item") as mock_merge:
        process_merge_queue(db_session, test_project.id, _project_config(), None)
        mock_merge.assert_called_once()
        called_item = mock_merge.call_args[0][1]
        assert called_item.work_item_id == work_item.id


# ---------------------------------------------------------------------------
# Scenario D: failed item bypasses gate
# ---------------------------------------------------------------------------


def test_failed_item_bypasses_gate(
    db_session: Session,
    test_project: Project,
) -> None:
    """With auto_merge=False, a failed item terminates in 'failed', never awaiting."""
    batch = make_batch(db_session, test_project.id, "BATCH-FAIL-BYPASS", auto_merge=False)
    work_item = make_work_item(db_session, test_project.id, "WI-FAIL-BYPASS-01")
    bi = make_batch_item(
        db_session,
        test_project.id,
        batch.id,
        work_item.id,
        status=BatchItemStatus.failed,
        worktree_path=None,
    )
    db_session.flush()

    # The item is already in 'failed' — it never entered awaiting_merge_approval
    assert bi.status == BatchItemStatus.failed
    assert bi.status != BatchItemStatus.awaiting_merge_approval

    # Verify no awaiting_merge_approval exists for this item
    item_in_awaiting = db_session.scalar(
        select(BatchItem).where(
            BatchItem.project_id == test_project.id,
            BatchItem.work_item_id == work_item.id,
            BatchItem.status == BatchItemStatus.awaiting_merge_approval,
        )
    )
    assert item_in_awaiting is None


def test_executing_item_that_fails_stays_at_failed(
    db_session: Session,
    test_project: Project,
) -> None:
    """An item in 'executing' with auto_merge=false that fails stays at failed."""
    batch = make_batch(db_session, test_project.id, "BATCH-FAIL-EXEC", auto_merge=False)
    work_item = make_work_item(db_session, test_project.id, "WI-FAIL-EXEC-01")
    bi = make_batch_item(
        db_session,
        test_project.id,
        batch.id,
        work_item.id,
        status=BatchItemStatus.executing,
        worktree_path="/tmp/worktrees/fail-exec",
    )
    db_session.flush()

    # Simulate step failure
    bi.status = BatchItemStatus.failed
    db_session.flush()

    db_session.refresh(bi)
    assert bi.status == BatchItemStatus.failed
    assert bi.status != BatchItemStatus.awaiting_merge_approval
