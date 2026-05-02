"""AC5/AC6: POST /project/{project_id}/api/item/{item_id}/restart-setup endpoint.

Tests the restart_setup endpoint's preconditions, state changes, and event emission.
Shares the same TestClient fixture pattern as test_restart_setup_backend.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# TestClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a TestClient that overrides get_db to use the test db_session."""
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Happy-path test (AC5)
# ---------------------------------------------------------------------------


class TestRestartSetupHappyPath:
    """AC5: restart_setup resets state correctly for a setup-failed item."""

    def test_restart_setup_happy_path(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """POST to restart_setup transitions WorkItem→approved, BatchItem→pending,
        resets all WorkflowSteps, deletes StepRuns, and emits setup_restarted event."""
        item_id = "CR00029-restart-happy"

        # WorkItem in failed status
        work_item = WorkItem(
            id=item_id,
            project_id=test_project.id,
            type=WorkItemType.Issue,
            title="CR-00029 Test Item",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(work_item)

        # Batch in approved state
        batch = Batch(
            id="CR00029-batch-restart-happy",
            project_id=test_project.id,
            status=BatchStatus.approved,
        )
        db_session.add(batch)
        db_session.flush()

        # BatchItem in setup_failed
        batch_item = BatchItem(
            project_id=test_project.id,
            work_item_id=item_id,
            batch_id="CR00029-batch-restart-happy",
            status=BatchItemStatus.setup_failed,
            notes="Setup failed: git worktree creation error",
        )
        db_session.add(batch_item)

        # All WorkflowSteps are still pending
        for step_id_label in [("S01", "Backend"), ("S02", "Frontend")]:
            step = WorkflowStep(
                project_id=test_project.id,
                work_item_id=item_id,
                step_number=1 if step_id_label[0] == "S01" else 2,
                step_id=step_id_label[0],
                agent_label=step_id_label[1],
                step_type=StepType.implementation,
                status=StepStatus.pending,
            )
            db_session.add(step)

        db_session.flush()
        db_session.commit()

        # Call the endpoint
        resp = client.post(f"/project/{test_project.id}/api/item/{item_id}/restart-setup")
        assert resp.status_code == 204, resp.text

        # --- Verify WorkItem.status = approved ---
        db_session.expire_all()
        item = db_session.scalar(select(WorkItem).where(WorkItem.id == item_id))
        assert item.status == WorkItemStatus.approved

        # --- Verify BatchItem.status = pending, notes cleared ---
        bi = db_session.scalar(select(BatchItem).where(BatchItem.work_item_id == item_id))
        assert bi.status == BatchItemStatus.pending
        assert bi.notes is None
        assert bi.started_at is None

        # --- Verify all WorkflowSteps are reset ---
        steps = list(
            db_session.scalars(
                select(WorkflowStep).where(WorkflowStep.work_item_id == item_id)
            ).all()
        )
        assert len(steps) == 2
        for step in steps:
            assert step.status == StepStatus.pending
            assert step.started_at is None
            assert step.completed_at is None
            assert step.report_file is None

        # --- Verify StepRuns are deleted ---
        step_ids = [s.id for s in steps]
        runs = list(db_session.scalars(select(StepRun).where(StepRun.step_id.in_(step_ids))).all())
        assert len(runs) == 0

        # --- Verify setup_restarted daemon event ---
        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "setup_restarted",
                DaemonEvent.entity_id == item_id,
            )
        )
        assert event is not None
        assert event.entity_type == "work_item"


# ---------------------------------------------------------------------------
# Precondition rejection tests (AC6)
# ---------------------------------------------------------------------------


class TestRestartSetupPreconditions:
    """AC6: restart_setup returns 422 for non-setup-failure states."""

    def test_restart_setup_rejects_no_batch_item(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """422 when no BatchItem in setup_failed/failed exists for the item."""
        item_id = "CR00029-no-bi"

        work_item = WorkItem(
            id=item_id,
            project_id=test_project.id,
            type=WorkItemType.Issue,
            title="CR-00029 No BatchItem",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(work_item)
        db_session.flush()
        db_session.commit()

        resp = client.post(f"/project/{test_project.id}/api/item/{item_id}/restart-setup")
        assert resp.status_code == 422
        assert "Cannot restart setup" in resp.json()["detail"]
        assert "no BatchItem" in resp.json()["detail"]

    def test_restart_setup_rejects_progressed_step(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """422 when BatchItem is in failed status but a step has already started."""
        item_id = "CR00029-step-progressed"

        work_item = WorkItem(
            id=item_id,
            project_id=test_project.id,
            type=WorkItemType.Issue,
            title="CR-00029 Step Progressed",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(work_item)

        batch = Batch(
            id="CR00029-batch-progressed",
            project_id=test_project.id,
            status=BatchStatus.approved,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            work_item_id=item_id,
            batch_id="CR00029-batch-progressed",
            status=BatchItemStatus.failed,
            notes="Cascade failure",
        )
        db_session.add(batch_item)

        # One step is already in_progress (has progressed past pending)
        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.in_progress,
        )
        db_session.add(step)
        db_session.flush()
        db_session.commit()

        resp = client.post(f"/project/{test_project.id}/api/item/{item_id}/restart-setup")
        assert resp.status_code == 422
        assert "progressed past pending" in resp.json()["detail"]

    def test_restart_setup_rejects_executing(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """422 when the BatchItem is currently executing (in progress, not a setup failure)."""
        item_id = "CR00029-executing"

        work_item = WorkItem(
            id=item_id,
            project_id=test_project.id,
            type=WorkItemType.Issue,
            title="CR-00029 Executing",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(work_item)

        batch = Batch(
            id="CR00029-batch-executing",
            project_id=test_project.id,
            status=BatchStatus.approved,
        )
        db_session.add(batch)
        db_session.flush()

        # BatchItem is in `executing` (not setup_failed/failed)
        batch_item = BatchItem(
            project_id=test_project.id,
            work_item_id=item_id,
            batch_id="CR00029-batch-executing",
            status=BatchItemStatus.executing,
        )
        db_session.add(batch_item)

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.pending,
        )
        db_session.add(step)
        db_session.flush()
        db_session.commit()

        resp = client.post(f"/project/{test_project.id}/api/item/{item_id}/restart-setup")
        assert resp.status_code == 422
        assert "no BatchItem" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Batch reopening (AC5 part)
# ---------------------------------------------------------------------------


class TestRestartSetupBatchReopen:
    """AC5: restart_setup re-opens a batch that is completed_with_errors."""

    def test_restart_setup_reopens_completed_with_errors_batch(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """When parent Batch is completed_with_errors, restart_setup flips it back to approved."""
        item_id = "CR00029-batch-reopen"

        work_item = WorkItem(
            id=item_id,
            project_id=test_project.id,
            type=WorkItemType.Issue,
            title="CR-00029 Batch Reopen",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(work_item)

        # Parent batch is in completed_with_errors
        batch = Batch(
            id="CR00029-batch-cwe",
            project_id=test_project.id,
            status=BatchStatus.completed_with_errors,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            work_item_id=item_id,
            batch_id="CR00029-batch-cwe",
            status=BatchItemStatus.setup_failed,
            notes="Setup failed",
        )
        db_session.add(batch_item)

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.pending,
        )
        db_session.add(step)
        db_session.flush()
        db_session.commit()

        resp = client.post(f"/project/{test_project.id}/api/item/{item_id}/restart-setup")
        assert resp.status_code == 204, resp.text

        db_session.expire_all()

        # Batch should be back to approved
        batch_after = db_session.scalar(select(Batch).where(Batch.id == "CR00029-batch-cwe"))
        assert batch_after.status == BatchStatus.approved


# ---------------------------------------------------------------------------
# Event-type distinction from full_restart_item (AC5 note)
# ---------------------------------------------------------------------------


class TestRestartSetupEventDistinctFromFullRestart:
    """Verify restart_setup emits setup_restarted (not item_full_restarted)."""

    def test_restart_setup_emits_setup_restarted_event(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """The daemon event type must be 'setup_restarted', not 'item_full_restarted'."""
        item_id = "CR00029-event-type"

        work_item = WorkItem(
            id=item_id,
            project_id=test_project.id,
            type=WorkItemType.Issue,
            title="CR-00029 Event Type",
            status=WorkItemStatus.failed,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(work_item)

        batch = Batch(
            id="CR00029-batch-event",
            project_id=test_project.id,
            status=BatchStatus.approved,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            work_item_id=item_id,
            batch_id="CR00029-batch-event",
            status=BatchItemStatus.setup_failed,
            notes="Setup failed",
        )
        db_session.add(batch_item)

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.pending,
        )
        db_session.add(step)
        db_session.flush()
        db_session.commit()

        client.post(f"/project/{test_project.id}/api/item/{item_id}/restart-setup")

        # Must have a setup_restarted event
        setup_event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "setup_restarted",
                DaemonEvent.entity_id == item_id,
            )
        )
        assert setup_event is not None

        # Must NOT have an item_full_restarted event
        full_restart_event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "item_full_restarted",
                DaemonEvent.entity_id == item_id,
            )
        )
        assert full_restart_event is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
