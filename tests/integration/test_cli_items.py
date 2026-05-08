"""Integration tests for item CLI commands (CR-00036 approve-merge).

Tests `iw approve-merge` happy path and rejection paths against a
real PostgreSQL testcontainer.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import contextmanager
from typing import TYPE_CHECKING

from click.testing import CliRunner
from sqlalchemy import select

from orch.cli.main import cli
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_awaiting_batch_item(
    db_session: Session,
    project_id: str,
    batch_id: str,
    work_item_id: str,
) -> BatchItem:
    """Create a WorkItem + Batch + BatchItem in awaiting_merge_approval state."""
    work_item = WorkItem(
        project_id=project_id,
        id=work_item_id,
        type=WorkItemType.Issue,
        title=f"Test item {work_item_id}",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(work_item)
    db_session.flush()

    batch = Batch(
        project_id=project_id,
        id=batch_id,
        status=BatchStatus.executing,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=False,
    )
    db_session.add(batch)
    db_session.flush()

    bi = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=work_item_id,
        execution_group=0,
        status=BatchItemStatus.awaiting_merge_approval,
        worktree_info={"path": "/tmp/worktrees/test"},
    )
    db_session.add(bi)
    db_session.flush()
    return bi


# ---------------------------------------------------------------------------
# approve-merge
# ---------------------------------------------------------------------------


def test_approve_merge_happy_path(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """approve-merge transitions awaiting_merge_approval → completed with exit 0."""
    bi = _make_awaiting_batch_item(
        db_session, test_project.id, "BATCH-CLI-HAPPY", "WI-CLI-HAPPY-01"
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "--json", "approve-merge", "WI-CLI-HAPPY-01"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"
    data = json.loads(result.output)
    assert data["status"] == "completed"
    assert data["item_id"] == "WI-CLI-HAPPY-01"

    db_session.refresh(bi)
    assert bi.status == BatchItemStatus.completed


def test_approve_merge_emits_daemon_event(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """approve-merge emits merge_approved_by_operator DaemonEvent."""
    _make_awaiting_batch_item(db_session, test_project.id, "BATCH-CLI-EVENT", "WI-CLI-EVENT-01")

    runner = CliRunner()
    runner.invoke(
        cli,
        ["--project", test_project.id, "approve-merge", "WI-CLI-EVENT-01"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    event = db_session.scalar(
        select(DaemonEvent).where(
            DaemonEvent.event_type == "merge_approved_by_operator",
            DaemonEvent.entity_id == "WI-CLI-EVENT-01",
        )
    )
    assert event is not None


def test_approve_merge_rejects_completed_item(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """approve-merge on a completed item returns exit 4, status unchanged."""
    work_item = WorkItem(
        project_id=test_project.id,
        id="WI-CLI-REJ-01",
        type=WorkItemType.Issue,
        title="Test item",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(work_item)
    db_session.flush()

    batch = Batch(
        project_id=test_project.id,
        id="BATCH-CLI-REJ",
        status=BatchStatus.executing,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=False,
    )
    db_session.add(batch)
    db_session.flush()

    bi = BatchItem(
        project_id=test_project.id,
        batch_id="BATCH-CLI-REJ",
        work_item_id="WI-CLI-REJ-01",
        execution_group=0,
        status=BatchItemStatus.completed,
    )
    db_session.add(bi)
    db_session.flush()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "approve-merge", "WI-CLI-REJ-01"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 4, (
        f"Expected exit 4 (rejection), got {result.exit_code}: {result.output}"
    )
    db_session.refresh(bi)
    assert bi.status == BatchItemStatus.completed


def test_approve_merge_rejects_merging_item(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """approve-merge on a merging item returns exit 4, status unchanged."""
    work_item = WorkItem(
        project_id=test_project.id,
        id="WI-CLI-MERGING-01",
        type=WorkItemType.Issue,
        title="Test item",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(work_item)
    db_session.flush()

    batch = Batch(
        project_id=test_project.id,
        id="BATCH-CLI-MERGING",
        status=BatchStatus.executing,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=True,
    )
    db_session.add(batch)
    db_session.flush()

    bi = BatchItem(
        project_id=test_project.id,
        batch_id="BATCH-CLI-MERGING",
        work_item_id="WI-CLI-MERGING-01",
        execution_group=0,
        status=BatchItemStatus.merging,
    )
    db_session.add(bi)
    db_session.flush()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "approve-merge", "WI-CLI-MERGING-01"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 4, f"Expected exit 4, got {result.exit_code}"
    db_session.refresh(bi)
    assert bi.status == BatchItemStatus.merging


def test_approve_merge_rejects_merged_item(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """approve-merge on a merged item returns exit 4, status unchanged."""
    work_item = WorkItem(
        project_id=test_project.id,
        id="WI-CLI-MERGED-01",
        type=WorkItemType.Issue,
        title="Test item",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(work_item)
    db_session.flush()

    batch = Batch(
        project_id=test_project.id,
        id="BATCH-CLI-MERGED",
        status=BatchStatus.completed,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=True,
    )
    db_session.add(batch)
    db_session.flush()

    bi = BatchItem(
        project_id=test_project.id,
        batch_id="BATCH-CLI-MERGED",
        work_item_id="WI-CLI-MERGED-01",
        execution_group=0,
        status=BatchItemStatus.merged,
    )
    db_session.add(bi)
    db_session.flush()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "approve-merge", "WI-CLI-MERGED-01"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 4, f"Expected exit 4, got {result.exit_code}"
    db_session.refresh(bi)
    assert bi.status == BatchItemStatus.merged


def test_approve_merge_not_found_exits_4(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """approve-merge on non-existent item exits 4 (not found / wrong state)."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "--json",
            "approve-merge",
            "WI-DOES-NOT-EXIST-12345",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    # Not found → exit 4 (rejection), same as wrong-state
    assert result.exit_code == 4, f"Expected exit 4, got {result.exit_code}: {result.output}"


def test_approve_merge_json_mode(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """approve-merge --json emits the documented payload."""
    _make_awaiting_batch_item(db_session, test_project.id, "BATCH-CLI-JSON", "WI-CLI-JSON-01")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "--json",
            "approve-merge",
            "WI-CLI-JSON-01",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "item_id" in data
    assert "status" in data
    assert data["item_id"] == "WI-CLI-JSON-01"
    assert data["status"] == "completed"


def test_approve_merge_cli_triggers_merge_queue_next_tick(
    db_session: Session,
    test_project: Project,
    cli_get_session: Callable[..., contextmanager],
) -> None:
    """AC7: CLI approve-merge transitions item to completed so merge queue can pick it up."""

    bi = _make_awaiting_batch_item(
        db_session, test_project.id, "BATCH-CLI-PIPELINE", "WI-CLI-PIPELINE-01"
    )
    db_session.flush()

    # Approve via CLI
    runner = CliRunner()
    approve_result = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "--json",
            "approve-merge",
            "WI-CLI-PIPELINE-01",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert approve_result.exit_code == 0

    db_session.refresh(bi)
    # The item must be in 'completed' state after approve_merge,
    # which is what makes it visible to process_merge_queue
    assert bi.status == BatchItemStatus.completed, (
        f"Expected completed after approve_merge, got {bi.status}"
    )
