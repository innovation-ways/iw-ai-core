"""Integration tests for dashboard action endpoints against a real PostgreSQL testcontainer."""

from __future__ import annotations

import signal
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Any) -> Generator[TestClient, None, None]:
    import os

    import dashboard.middlewares.alembic_guard as mg

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    # Reset middleware globals so stale state from other test files doesn't
    # cause require_db_at_head to return 503 for tests that don't expect it.
    mg._alembic_guard_status = None
    mg._dashboard_last_check = 0.0
    try:

        def override_get_db() -> Generator[Any, None, None]:
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def make_item(
    db_session: Any,
    project_id: str = "test-proj",
    item_id: str = "I-00001",
    status: WorkItemStatus = WorkItemStatus.in_progress,
) -> WorkItem:
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Issue,
        title="Test item",
        status=status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()
    return item


def make_step(
    db_session: Any,
    project_id: str = "test-proj",
    item_id: str = "I-00001",
    step_id: str = "S01",
    step_number: int = 1,
    status: StepStatus = StepStatus.in_progress,
) -> WorkflowStep:
    step = WorkflowStep(
        project_id=project_id,
        work_item_id=item_id,
        step_number=step_number,
        step_id=step_id,
        agent_label="Backend",
        step_type=StepType.implementation,
        status=status,
    )
    db_session.add(step)
    db_session.flush()
    return step


def make_run(
    db_session: Any,
    step_db_id: int,
    run_number: int = 1,
    status: RunStatus = RunStatus.running,
    pid: int = 12345,
) -> StepRun:
    from datetime import UTC, datetime

    run = StepRun(
        step_id=step_db_id,
        run_number=run_number,
        status=status,
        pid=pid,
        pid_alive=True,
        command="claude -p '/execute I-00001 S01'",
        worktree_path="/repos/test/.worktrees/I-00001",
        cli_tool="claude",
        timeout_secs=1800,
        started_at=datetime.now(UTC),
    )
    db_session.add(run)
    db_session.flush()
    return run


# ---------------------------------------------------------------------------
# Kill step
# ---------------------------------------------------------------------------


def test_kill_updates_db(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    item = make_item(db_session)
    step = make_step(db_session)
    run = make_run(db_session, step.id, pid=12345)

    with patch("dashboard.routers.actions.os.kill") as mock_kill:
        resp = client.post(
            f"/project/{test_project.id}/api/item/{item.id}/kill-step/{step.step_id}"
        )

    assert resp.status_code == 204
    mock_kill.assert_called_once_with(12345, signal.SIGTERM)

    db_session.refresh(run)
    assert run.status == RunStatus.killed
    assert run.error_message == "Killed by user"
    assert run.completed_at is not None

    db_session.refresh(step)
    assert step.status == StepStatus.failed
    assert step.completed_at is not None


def test_kill_handles_already_dead_pid(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """SIGTERM to a dead PID (ProcessLookupError) should not crash the endpoint."""
    item = make_item(db_session)
    step = make_step(db_session)
    make_run(db_session, step.id, pid=99999)

    with patch("dashboard.routers.actions.os.kill", side_effect=ProcessLookupError):
        resp = client.post(
            f"/project/{test_project.id}/api/item/{item.id}/kill-step/{step.step_id}"
        )

    assert resp.status_code == 204
    db_session.refresh(step)
    assert step.status == StepStatus.failed


def test_kill_non_running_returns_422(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    item = make_item(db_session)
    step = make_step(db_session, status=StepStatus.failed)
    make_run(db_session, step.id, status=RunStatus.failed)

    resp = client.post(f"/project/{test_project.id}/api/item/{item.id}/kill-step/{step.step_id}")
    assert resp.status_code == 422


def test_kill_emits_daemon_event(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    item = make_item(db_session)
    step = make_step(db_session)
    make_run(db_session, step.id)

    with patch("dashboard.routers.actions.os.kill"):
        client.post(f"/project/{test_project.id}/api/item/{item.id}/kill-step/{step.step_id}")

    event = db_session.scalar(select(DaemonEvent).where(DaemonEvent.event_type == "step_killed"))
    assert event is not None
    assert event.entity_id == item.id


# ---------------------------------------------------------------------------
# Restart step
# ---------------------------------------------------------------------------


def test_restart_creates_pending_run(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    item = make_item(db_session)
    step = make_step(db_session, status=StepStatus.failed)
    old_run = make_run(db_session, step.id, run_number=1, status=RunStatus.failed)

    resp = client.post(f"/project/{test_project.id}/api/item/{item.id}/restart-step/{step.step_id}")
    assert resp.status_code == 204

    db_session.refresh(step)
    assert step.status == StepStatus.pending
    assert step.started_at is None
    assert step.completed_at is None

    # New run should be created with run_number = 2
    new_run = db_session.scalar(
        select(StepRun).where(
            StepRun.step_id == step.id,
            StepRun.run_number == 2,
        )
    )
    assert new_run is not None
    assert new_run.status == RunStatus.pending
    assert new_run.command == old_run.command
    assert new_run.worktree_path == old_run.worktree_path


def test_restart_invalid_state_returns_422(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    item = make_item(db_session)
    step = make_step(db_session, status=StepStatus.in_progress)
    make_run(db_session, step.id, status=RunStatus.running)

    resp = client.post(f"/project/{test_project.id}/api/item/{item.id}/restart-step/{step.step_id}")
    assert resp.status_code == 422


def test_restart_unblocks_failed_item(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    item = make_item(db_session, status=WorkItemStatus.failed)
    step = make_step(db_session, status=StepStatus.failed)
    make_run(db_session, step.id, status=RunStatus.failed)

    resp = client.post(f"/project/{test_project.id}/api/item/{item.id}/restart-step/{step.step_id}")
    assert resp.status_code == 204

    db_session.refresh(item)
    assert item.status == WorkItemStatus.in_progress


# ---------------------------------------------------------------------------
# Skip step
# ---------------------------------------------------------------------------


def test_skip_marks_skipped(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    item = make_item(db_session)
    step = make_step(db_session, status=StepStatus.failed)

    resp = client.post(f"/project/{test_project.id}/api/item/{item.id}/skip-step/{step.step_id}")
    assert resp.status_code == 204

    db_session.refresh(step)
    assert step.status == StepStatus.skipped
    assert step.completed_at is not None


def test_skip_invalid_state_returns_422(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    item = make_item(db_session)
    step = make_step(db_session, status=StepStatus.in_progress)

    resp = client.post(f"/project/{test_project.id}/api/item/{item.id}/skip-step/{step.step_id}")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Restart from step N
# ---------------------------------------------------------------------------


def test_restart_from_resets_downstream_steps(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    item = make_item(db_session)
    step1 = make_step(db_session, step_id="S01", step_number=1, status=StepStatus.completed)
    step2 = make_step(db_session, step_id="S02", step_number=2, status=StepStatus.failed)
    step3 = make_step(db_session, step_id="S03", step_number=3, status=StepStatus.pending)

    # Give step2 a run so restart-from can copy command
    make_run(db_session, step2.id, status=RunStatus.failed)

    resp = client.post(f"/project/{test_project.id}/api/item/{item.id}/restart-from/S02")
    assert resp.status_code == 204

    db_session.refresh(step1)
    db_session.refresh(step2)
    db_session.refresh(step3)

    # S01 untouched (before restart point)
    assert step1.status == StepStatus.completed

    # S02 and S03 reset to pending
    assert step2.status == StepStatus.pending
    assert step3.status == StepStatus.pending

    # New pending run created for S02
    new_run = db_session.scalar(
        select(StepRun).where(
            StepRun.step_id == step2.id,
            StepRun.run_number == 2,
        )
    )
    assert new_run is not None
    assert new_run.status == RunStatus.pending

    db_session.refresh(item)
    assert item.status == WorkItemStatus.in_progress


# ---------------------------------------------------------------------------
# Confirm dialog
# ---------------------------------------------------------------------------


def test_confirm_dialog_returns_fragment(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    item = make_item(db_session)
    step = make_step(db_session)

    resp = client.get(f"/project/{test_project.id}/api/confirm/kill-step/{item.id}/{step.step_id}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    body = resp.text
    assert "Kill" in body
    assert step.step_id in body


def test_confirm_unknown_action_returns_400(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    item = make_item(db_session)
    make_step(db_session)

    resp = client.get(f"/project/{test_project.id}/api/confirm/explode-everything/{item.id}/S01")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Running tasks page (smoke test)
# ---------------------------------------------------------------------------


def test_running_page_returns_200(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    resp = client.get("/system/running")
    assert resp.status_code == 200
    assert "Running Tasks" in resp.text


def test_running_fragment_returns_tbody(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    resp = client.get("/system/running-fragment")
    assert resp.status_code == 200
    # Fragment has no full HTML structure
    assert "<html" not in resp.text


# ---------------------------------------------------------------------------
# Batch approval actions
# ---------------------------------------------------------------------------


def _make_batch(
    db_session: Any,
    project_id: str = "test-proj",
    batch_id: str = "BATCH-00001",
    status: BatchStatus | None = None,
    auto_merge: bool = True,
) -> Batch:
    batch = Batch(
        project_id=project_id,
        id=batch_id,
        status=status or BatchStatus.planning,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=auto_merge,
    )
    db_session.add(batch)
    db_session.flush()
    return batch


def test_approve_batch_planning_to_approved(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    batch = _make_batch(db_session)

    resp = client.post(f"/project/{test_project.id}/api/batch/{batch.id}/approve")
    assert resp.status_code == 204

    db_session.refresh(batch)
    assert batch.status == BatchStatus.approved


def test_approve_batch_wrong_state_returns_422(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    batch = _make_batch(db_session, status=BatchStatus.executing)

    resp = client.post(f"/project/{test_project.id}/api/batch/{batch.id}/approve")
    assert resp.status_code == 422


def test_pause_batch_executing_to_paused(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    batch = _make_batch(db_session, status=BatchStatus.executing)

    resp = client.post(f"/project/{test_project.id}/api/batch/{batch.id}/pause")
    assert resp.status_code == 204

    db_session.refresh(batch)
    assert batch.status == BatchStatus.paused


def test_resume_batch_paused_to_executing(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    batch = _make_batch(db_session, status=BatchStatus.paused)

    resp = client.post(f"/project/{test_project.id}/api/batch/{batch.id}/resume")
    assert resp.status_code == 204

    db_session.refresh(batch)
    assert batch.status == BatchStatus.executing


def test_cancel_batch_planning_to_cancelled(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    batch = _make_batch(db_session)

    resp = client.post(f"/project/{test_project.id}/api/batch/{batch.id}/cancel")
    assert resp.status_code == 204

    db_session.refresh(batch)
    assert batch.status == BatchStatus.cancelled


def test_cancel_batch_approved_to_cancelled(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    batch = _make_batch(db_session, status=BatchStatus.approved)

    resp = client.post(f"/project/{test_project.id}/api/batch/{batch.id}/cancel")
    assert resp.status_code == 204

    db_session.refresh(batch)
    assert batch.status == BatchStatus.cancelled


def test_cancel_batch_wrong_state_returns_422(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    batch = _make_batch(db_session, status=BatchStatus.executing)

    resp = client.post(f"/project/{test_project.id}/api/batch/{batch.id}/cancel")
    assert resp.status_code == 422


def test_confirm_batch_dialog_returns_fragment(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    batch = _make_batch(db_session)

    resp = client.get(f"/project/{test_project.id}/api/confirm-batch/approve/{batch.id}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Approve" in resp.text
    assert batch.id in resp.text


def test_confirm_batch_unknown_action_returns_400(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    batch = _make_batch(db_session)

    resp = client.get(f"/project/{test_project.id}/api/confirm-batch/destroy/{batch.id}")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# CR-00036: approve-merge endpoint
# ---------------------------------------------------------------------------


def _make_batch_item_awaiting(
    db_session: Any,
    project_id: str = "test-proj",
    batch_id: str = "BATCH-00001",
    item_id: str = "I-00001",
) -> BatchItem:
    """Create a BatchItem in awaiting_merge_approval status with its WorkItem."""
    # Create the WorkItem first (required for FK constraint)
    work_item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Issue,
        title="Test item for batch",
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

    batch_item = BatchItem(
        project_id=project_id,
        batch_id=batch_id,
        work_item_id=item_id,
        execution_group=0,
        status=BatchItemStatus.awaiting_merge_approval,
    )
    db_session.add(batch_item)
    db_session.flush()
    return batch_item


def test_approve_merge_happy_path(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """approve-merge transitions awaiting_merge_approval → completed and returns 204."""
    batch_item = _make_batch_item_awaiting(db_session)

    resp = client.post(
        f"/project/{test_project.id}/api/item/{batch_item.work_item_id}/approve-merge"
    )
    assert resp.status_code == 204

    db_session.refresh(batch_item)
    assert batch_item.status == BatchItemStatus.completed


def test_approve_merge_emits_daemon_event(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """approve-merge emits a merge_approved_by_operator DaemonEvent."""
    batch_item = _make_batch_item_awaiting(db_session)

    client.post(f"/project/{test_project.id}/api/item/{batch_item.work_item_id}/approve-merge")

    event = db_session.scalar(
        select(DaemonEvent).where(
            DaemonEvent.event_type == "merge_approved_by_operator",
            DaemonEvent.entity_id == batch_item.work_item_id,
        )
    )
    assert event is not None


def test_approve_merge_rejection_wrong_status_returns_409(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """approve-merge returns 409 when item is not in awaiting_merge_approval."""
    # Create a batch item in completed status instead
    batch = Batch(
        project_id=test_project.id,
        id="BATCH-00002",
        status=BatchStatus.executing,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=False,
    )
    db_session.add(batch)
    db_session.flush()

    item = WorkItem(
        project_id=test_project.id,
        id="I-00002",
        type=WorkItemType.Issue,
        title="Test item",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()

    batch_item = BatchItem(
        project_id=test_project.id,
        batch_id="BATCH-00002",
        work_item_id="I-00002",
        execution_group=0,
        status=BatchItemStatus.completed,  # Wrong status
    )
    db_session.add(batch_item)
    db_session.flush()

    resp = client.post(f"/project/{test_project.id}/api/item/I-00002/approve-merge")
    assert resp.status_code == 409

    # Verify no mutation occurred
    db_session.refresh(batch_item)
    assert batch_item.status == BatchItemStatus.completed


def test_approve_merge_rejection_merging_returns_409(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """approve-merge returns 409 when item is already merging."""
    # Set up a batch item in 'merging' status (merge in progress)
    batch = Batch(
        project_id=test_project.id,
        id="BATCH-APPROVE-MERGING",
        status=BatchStatus.executing,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=True,
    )
    db_session.add(batch)
    db_session.flush()

    work_item = WorkItem(
        project_id=test_project.id,
        id="WI-APPROVE-MERGING",
        type=WorkItemType.Issue,
        title="Test item",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(work_item)
    db_session.flush()

    batch_item = BatchItem(
        project_id=test_project.id,
        batch_id="BATCH-APPROVE-MERGING",
        work_item_id="WI-APPROVE-MERGING",
        execution_group=0,
        status=BatchItemStatus.merging,
    )
    db_session.add(batch_item)
    db_session.flush()

    resp = client.post(f"/project/{test_project.id}/api/item/WI-APPROVE-MERGING/approve-merge")
    assert resp.status_code == 409


def test_approve_merge_rejection_merged_returns_409(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """approve-merge returns 409 when item is already merged."""
    batch = Batch(
        project_id=test_project.id,
        id="BATCH-APPROVE-MERGED",
        status=BatchStatus.completed,
        max_parallel=4,
        cli_tool="claude",
        auto_publish=False,
        auto_merge=True,
    )
    db_session.add(batch)
    db_session.flush()

    work_item = WorkItem(
        project_id=test_project.id,
        id="WI-APPROVE-MERGED",
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

    batch_item = BatchItem(
        project_id=test_project.id,
        batch_id="BATCH-APPROVE-MERGED",
        work_item_id="WI-APPROVE-MERGED",
        execution_group=0,
        status=BatchItemStatus.merged,
    )
    db_session.add(batch_item)
    db_session.flush()

    resp = client.post(f"/project/{test_project.id}/api/item/WI-APPROVE-MERGED/approve-merge")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# CR-00036: update_batch_auto_merge endpoint
# ---------------------------------------------------------------------------


def test_update_batch_auto_merge_planning_to_on(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """auto-merge can be enabled on a planning batch."""
    batch = _make_batch(db_session, status=BatchStatus.planning)

    resp = client.post(
        f"/project/{test_project.id}/api/batch/{batch.id}/auto-merge",
        data={"auto_merge": "on"},
    )
    assert resp.status_code == 204

    db_session.refresh(batch)
    assert batch.auto_merge is True


def test_update_batch_auto_merge_planning_to_off(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """auto-merge can be disabled on a planning batch."""
    batch = _make_batch(db_session, status=BatchStatus.planning, auto_merge=True)

    resp = client.post(
        f"/project/{test_project.id}/api/batch/{batch.id}/auto-merge",
        data={"auto_merge": "off"},
    )
    assert resp.status_code == 204

    db_session.refresh(batch)
    assert batch.auto_merge is False


def test_update_batch_auto_merge_checkbox_only_sends_when_checked(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """When checkbox is unchecked, the field is absent (None) and treated as False."""
    batch = _make_batch(db_session, status=BatchStatus.planning, auto_merge=True)

    # No auto_merge field at all — simulates unchecked checkbox
    resp = client.post(
        f"/project/{test_project.id}/api/batch/{batch.id}/auto-merge",
        data={},
    )
    assert resp.status_code == 204

    db_session.refresh(batch)
    assert batch.auto_merge is False


def test_update_batch_auto_merge_rejection_executing(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """auto-merge cannot be changed while batch is executing."""
    batch = _make_batch(db_session, status=BatchStatus.executing)

    resp = client.post(
        f"/project/{test_project.id}/api/batch/{batch.id}/auto-merge",
        data={"auto_merge": "on"},
    )
    assert resp.status_code == 409
    assert "Cannot change auto-merge while batch is executing" in resp.text


def test_update_batch_auto_merge_rejection_completed(
    client: TestClient,
    db_session: Any,
    test_project: Project,
) -> None:
    """auto-merge cannot be changed while batch is completed."""
    batch = _make_batch(db_session, status=BatchStatus.completed)

    resp = client.post(
        f"/project/{test_project.id}/api/batch/{batch.id}/auto-merge",
        data={"auto_merge": "on"},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# CR-00036: create_batch_from_selection auto_merge handling
# ---------------------------------------------------------------------------


def test_create_batch_inherits_auto_merge_default(
    client: TestClient,
    db_session: Any,
    test_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When auto_merge form field is absent, batch inherits project default (True)."""
    # Create an approved work item
    item = WorkItem(
        project_id=test_project.id,
        id="I-INHERIT-01",
        type=WorkItemType.Issue,
        title="Test item",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()

    # Mock at the source module where it's defined
    class FakeProjConfig:
        auto_merge_default = False

    class FakeProjectsToml:
        def get(self, project_id: str) -> FakeProjConfig | None:
            return FakeProjConfig()

    monkeypatch.setattr(
        "orch.daemon.project_registry.load_projects_toml",
        lambda *_: FakeProjectsToml(),
    )

    resp = client.post(
        f"/project/{test_project.id}/api/batch/create-from-selection",
        data={"item_ids": ["I-INHERIT-01"]},
    )
    assert resp.status_code == 204

    batch_id = resp.headers.get("location", "").split("/")[-1]
    batch = db_session.scalar(select(Batch).where(Batch.id == batch_id))
    if batch is None:
        # Fallback: query by project_id and created_at recently
        batch = db_session.scalar(
            select(Batch)
            .where(Batch.project_id == test_project.id)
            .order_by(Batch.created_at.desc())
        )
    assert batch is not None
    assert batch.auto_merge is False  # Inherited from project default (False)


def test_create_batch_respects_auto_merge_override(
    client: TestClient,
    db_session: Any,
    test_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When auto_merge form field is present, it overrides the project default."""
    item = WorkItem(
        project_id=test_project.id,
        id="I-OVERRIDE-01",
        type=WorkItemType.Issue,
        title="Test item",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()

    # Mock at the source module where it's defined
    class FakeProjConfig:
        auto_merge_default = False

    class FakeProjectsToml:
        def get(self, project_id: str) -> FakeProjConfig | None:
            return FakeProjConfig()

    monkeypatch.setattr(
        "orch.daemon.project_registry.load_projects_toml",
        lambda *_: FakeProjectsToml(),
    )

    # Explicitly set auto_merge=on (True), overriding project default (False)
    resp = client.post(
        f"/project/{test_project.id}/api/batch/create-from-selection",
        data={"item_ids": ["I-OVERRIDE-01"], "auto_merge": "on"},
    )
    assert resp.status_code == 204

    batch = db_session.scalar(
        select(Batch).where(Batch.project_id == test_project.id).order_by(Batch.created_at.desc())
    )
    assert batch is not None
    assert batch.auto_merge is True  # Override respected
