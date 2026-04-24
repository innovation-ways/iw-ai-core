"""Tests for I-00037: batch progress parity between project dashboard and batches list views.

These tests verify that:
1. The bug from I-00036 (item-level progress_pct) is fixed.
2. _active_batches() and _all_batches() agree on progress_pct (parity lock).
3. The compute_batch_step_progress helper handles all edge cases.

Bug reproduction scenario (would FAIL on pre-S03 code):
- 1 work item with 10 steps (3 completed, 7 pending)
- 1 batch with 1 in_progress item
- Expected: progress_pct == 30 (step-based)
- Pre-S03 bug: progress_pct == 0 (item-based — batch has no completed items)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers.batches import _all_batches
from dashboard.routers.project_dashboard import _active_batches
from dashboard.utils.batch_progress import compute_batch_step_progress
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# TestClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient wired to the testcontainer db_session."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Generator[Session, None, None]:
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
# Helpers
# ---------------------------------------------------------------------------


def _seed_three_of_ten_steps(db_session: Session, project_id: str, work_item_id: str) -> None:
    """Seed 10 workflow steps for a work item: steps 1-3 completed, 4-10 pending."""
    for step_num in range(1, 11):
        status = StepStatus.completed if step_num <= 3 else StepStatus.pending
        db_session.add(
            WorkflowStep(
                project_id=project_id,
                work_item_id=work_item_id,
                step_id=f"{work_item_id}-step-{step_num}",
                step_number=step_num,
                step_type=StepType.implementation,
                agent_label="test-agent",
                status=status,
            )
        )
    db_session.flush()


def _seed_project_and_work_item(
    db_session: Session, project_id: str = "test-proj", work_item_id: str = "WI-001"
) -> None:
    """Minimal project + work item + batch setup for progress tests."""
    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)

    work_item = WorkItem(
        id=work_item_id,
        project_id=project_id,
        title="Test Work Item",
        type=WorkItemType.Feature,
        phase=WorkItemPhase.active,
        status=WorkItemStatus.in_progress,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(work_item)
    db_session.flush()


# ---------------------------------------------------------------------------
# Test: Reproduction + Parity (Requirement 2)
# ---------------------------------------------------------------------------


class TestI00037ProgressParity:
    """Reproduction test for the I-00036 bug + parity lock between the two routers."""

    def test_dashboard_home_and_batches_view_agree_on_progress(self, db_session: Session) -> None:
        """Reproduction + parity: 3/10 steps done → progress_pct must be 30 in both views.

        PRE-S03 BUG: _active_batches() returned item-level progress (0 completed items
        for the batch, so progress_pct=0). This test would FAIL against that code.
        """
        project_id = "test-parity-proj"
        work_item_id = "WI-PARITY-001"
        batch_id = "batch-parity-001"

        _seed_project_and_work_item(db_session, project_id, work_item_id)
        _seed_three_of_ten_steps(db_session, project_id, work_item_id)

        batch = Batch(
            id=batch_id,
            project_id=project_id,
            status=BatchStatus.executing,
        )
        db_session.add(batch)

        item = BatchItem(
            project_id=project_id,
            batch_id=batch_id,
            work_item_id=work_item_id,
            status=BatchItemStatus.executing,
            execution_group=1,
        )
        db_session.add(item)
        db_session.flush()

        dash_rows = _active_batches(project_id, db_session)
        full_rows = _all_batches(project_id, db_session, status_filter=[])

        assert len(dash_rows) == 1, f"Expected 1 active batch, got {len(dash_rows)}"
        assert len(full_rows) == 1, f"Expected 1 total batch, got {len(full_rows)}"

        dash = dash_rows[0]
        full = full_rows[0]

        assert dash.progress_pct == 30, (
            f"dashboard home: expected 30 (3/10 steps done), got {dash.progress_pct}"
        )
        assert full.progress_pct == 30, (
            f"batches list: expected 30 (3/10 steps done), got {full.progress_pct}"
        )
        assert dash.progress_pct == full.progress_pct, (
            "PARITY FAIL: _active_batches and _all_batches disagree on progress_pct"
        )
        assert dash.completed_items == 0, (
            f"Items column stays item-level: expected 0 completed items, got {dash.completed_items}"
        )
        assert dash.total_items == 1, (
            f"total_items is count of batch items, not steps: expected 1, got {dash.total_items}"
        )
        assert full.completed_items == 0
        assert full.total_items == 1


# ---------------------------------------------------------------------------
# Test: Regression — Helper Directly (Requirement 3)
# ---------------------------------------------------------------------------


class TestComputeBatchStepProgress:
    """Regression tests for compute_batch_step_progress edge cases."""

    def test_helper_empty_batch_ids_returns_empty_dict(self, db_session: Session) -> None:
        """Empty input → empty dict, no query needed."""
        project_id = "test-empty-proj"
        result = compute_batch_step_progress(project_id, batch_ids=[], db=db_session)
        assert result == {}

    def test_helper_single_batch_3_of_10_done(self, db_session: Session) -> None:
        """1 item, 10 steps, 3 completed → 30%."""
        project_id = "test-3of10-proj"
        work_item_id = "WI-3of10"
        batch_id = "batch-3of10"

        _seed_project_and_work_item(db_session, project_id, work_item_id)
        _seed_three_of_ten_steps(db_session, project_id, work_item_id)

        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        item = BatchItem(
            project_id=project_id,
            batch_id=batch_id,
            work_item_id=work_item_id,
            status=BatchItemStatus.executing,
            execution_group=1,
        )
        db_session.add(item)
        db_session.flush()

        result = compute_batch_step_progress(project_id, batch_ids=[batch_id], db=db_session)
        assert result == {batch_id: 30}

    def test_helper_all_steps_done_is_100(self, db_session: Session) -> None:
        """5 steps, all completed → 100%."""
        project_id = "test-all-done-proj"
        work_item_id = "WI-ALLDONE"
        batch_id = "batch-alldone"

        _seed_project_and_work_item(db_session, project_id, work_item_id)
        for i in range(1, 6):
            db_session.add(
                WorkflowStep(
                    project_id=project_id,
                    work_item_id=work_item_id,
                    step_id=f"{work_item_id}-step-{i}",
                    step_number=i,
                    step_type=StepType.implementation,
                    agent_label="test-agent",
                    status=StepStatus.completed,
                )
            )
        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=work_item_id,
                status=BatchItemStatus.executing,
                execution_group=1,
            )
        )
        db_session.flush()

        result = compute_batch_step_progress(project_id, batch_ids=[batch_id], db=db_session)
        assert result == {batch_id: 100}

    def test_helper_zero_steps_is_0_not_crash(self, db_session: Session) -> None:
        """1 item, 0 workflow step rows → 0% (no divide-by-zero)."""
        project_id = "test-no-steps-proj"
        work_item_id = "WI-NOSTEPS"
        batch_id = "batch-nosteps"

        _seed_project_and_work_item(db_session, project_id, work_item_id)
        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=work_item_id,
                status=BatchItemStatus.executing,
                execution_group=1,
            )
        )
        db_session.flush()

        result = compute_batch_step_progress(project_id, batch_ids=[batch_id], db=db_session)
        assert result == {batch_id: 0}

    def test_helper_skipped_counts_as_done(self, db_session: Session) -> None:
        """2 completed + 2 skipped + 6 pending = 4/10 done → 40%."""
        project_id = "test-skipped-proj"
        work_item_id = "WI-SKIPPED"
        batch_id = "batch-skipped"

        _seed_project_and_work_item(db_session, project_id, work_item_id)

        statuses = [
            StepStatus.completed,
            StepStatus.completed,
            StepStatus.skipped,
            StepStatus.skipped,
        ] + [StepStatus.pending] * 6
        for i, status in enumerate(statuses, start=1):
            db_session.add(
                WorkflowStep(
                    project_id=project_id,
                    work_item_id=work_item_id,
                    step_id=f"{work_item_id}-step-{i}",
                    step_number=i,
                    step_type=StepType.implementation,
                    agent_label="test-agent",
                    status=status,
                )
            )
        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=work_item_id,
                status=BatchItemStatus.executing,
                execution_group=1,
            )
        )
        db_session.flush()

        result = compute_batch_step_progress(project_id, batch_ids=[batch_id], db=db_session)
        assert result == {batch_id: 40}

    def test_helper_failed_does_not_count(self, db_session: Session) -> None:
        """3 completed + 2 failed + 5 pending → 3/10 done = 30% (NOT 50%)."""
        project_id = "test-failed-proj"
        work_item_id = "WI-FAILED"
        batch_id = "batch-failed"

        _seed_project_and_work_item(db_session, project_id, work_item_id)

        statuses = [StepStatus.completed] * 3 + [StepStatus.failed] * 2 + [StepStatus.pending] * 5
        for i, status in enumerate(statuses, start=1):
            db_session.add(
                WorkflowStep(
                    project_id=project_id,
                    work_item_id=work_item_id,
                    step_id=f"{work_item_id}-step-{i}",
                    step_number=i,
                    step_type=StepType.implementation,
                    agent_label="test-agent",
                    status=status,
                )
            )
        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=work_item_id,
                status=BatchItemStatus.executing,
                execution_group=1,
            )
        )
        db_session.flush()

        result = compute_batch_step_progress(project_id, batch_ids=[batch_id], db=db_session)
        assert result == {batch_id: 30}

    def test_helper_needs_fix_does_not_count(self, db_session: Session) -> None:
        """3 completed + 1 needs_fix + 6 pending → 3/10 = 30% (NOT 40%)."""
        project_id = "test-needs-fix-proj"
        work_item_id = "WI-NEEDSFIX"
        batch_id = "batch-needsfix"

        _seed_project_and_work_item(db_session, project_id, work_item_id)

        statuses = [StepStatus.completed] * 3 + [StepStatus.needs_fix] + [StepStatus.pending] * 6
        for i, status in enumerate(statuses, start=1):
            db_session.add(
                WorkflowStep(
                    project_id=project_id,
                    work_item_id=work_item_id,
                    step_id=f"{work_item_id}-step-{i}",
                    step_number=i,
                    step_type=StepType.implementation,
                    agent_label="test-agent",
                    status=status,
                )
            )
        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=work_item_id,
                status=BatchItemStatus.executing,
                execution_group=1,
            )
        )
        db_session.flush()

        result = compute_batch_step_progress(project_id, batch_ids=[batch_id], db=db_session)
        assert result == {batch_id: 30}

    def test_helper_in_progress_does_not_count(self, db_session: Session) -> None:
        """3 completed + 1 in_progress + 6 pending → 3/10 = 30%."""
        project_id = "test-inprog-proj"
        work_item_id = "WI-INPROG"
        batch_id = "batch-inprog"

        _seed_project_and_work_item(db_session, project_id, work_item_id)

        statuses = [StepStatus.completed] * 3 + [StepStatus.in_progress] + [StepStatus.pending] * 6
        for i, status in enumerate(statuses, start=1):
            db_session.add(
                WorkflowStep(
                    project_id=project_id,
                    work_item_id=work_item_id,
                    step_id=f"{work_item_id}-step-{i}",
                    step_number=i,
                    step_type=StepType.implementation,
                    agent_label="test-agent",
                    status=status,
                )
            )
        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=work_item_id,
                status=BatchItemStatus.executing,
                execution_group=1,
            )
        )
        db_session.flush()

        result = compute_batch_step_progress(project_id, batch_ids=[batch_id], db=db_session)
        assert result == {batch_id: 30}

    def test_helper_multi_batch_bulk(self, db_session: Session) -> None:
        """Ask for 4 batches in one call: A=1/10, B=5/10, C=0 steps, D=10/10."""
        project_id = "test-multi-proj"
        batch_a = "batch-multi-A"
        batch_b = "batch-multi-B"
        batch_c = "batch-multi-C"
        batch_d = "batch-multi-D"

        _seed_project_and_work_item(db_session, project_id)

        for wid in ["WI-MULTI-A", "WI-MULTI-B", "WI-MULTI-C", "WI-MULTI-D"]:
            wi = WorkItem(
                id=wid,
                project_id=project_id,
                title=f"Item {wid}",
                type=WorkItemType.Feature,
                phase=WorkItemPhase.active,
                status=WorkItemStatus.in_progress,
                config={},
                depends_on=[],
                blocks=[],
            )
            db_session.add(wi)
        db_session.flush()

        def add_batch_with_steps(
            batch_id: str,
            work_item_id: str,
            completed_count: int,
            total: int = 10,
        ) -> None:
            for i in range(1, total + 1):
                status = StepStatus.completed if i <= completed_count else StepStatus.pending
                db_session.add(
                    WorkflowStep(
                        project_id=project_id,
                        work_item_id=work_item_id,
                        step_id=f"{work_item_id}-step-{i}",
                        step_number=i,
                        step_type=StepType.implementation,
                        agent_label="test-agent",
                        status=status,
                    )
                )
            batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
            db_session.add(batch)
            db_session.add(
                BatchItem(
                    project_id=project_id,
                    batch_id=batch_id,
                    work_item_id=work_item_id,
                    status=BatchItemStatus.executing,
                    execution_group=1,
                )
            )

        add_batch_with_steps(batch_a, "WI-MULTI-A", completed_count=1, total=10)
        add_batch_with_steps(batch_b, "WI-MULTI-B", completed_count=5, total=10)
        db_session.flush()

        batch_c_batch = Batch(id=batch_c, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch_c_batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_c,
                work_item_id="WI-MULTI-C",
                status=BatchItemStatus.executing,
                execution_group=1,
            )
        )
        db_session.flush()

        add_batch_with_steps(batch_d, "WI-MULTI-D", completed_count=10, total=10)
        db_session.flush()

        result = compute_batch_step_progress(
            project_id, batch_ids=[batch_a, batch_b, batch_c, batch_d], db=db_session
        )
        assert result == {
            batch_a: 10,
            batch_b: 50,
            batch_c: 0,
            batch_d: 100,
        }

    def test_helper_missing_batch_id_defaults_to_0(self, db_session: Session) -> None:
        """Ask for [existing, DOESNOTEXIST] → no KeyError, missing key maps to 0."""
        project_id = "test-missing-proj"
        work_item_id = "WI-MISSING"
        batch_id = "batch-missing-existing"

        _seed_project_and_work_item(db_session, project_id, work_item_id)
        for i in range(1, 6):
            db_session.add(
                WorkflowStep(
                    project_id=project_id,
                    work_item_id=work_item_id,
                    step_id=f"{work_item_id}-step-{i}",
                    step_number=i,
                    step_type=StepType.implementation,
                    agent_label="test-agent",
                    status=StepStatus.completed,
                )
            )
        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=work_item_id,
                status=BatchItemStatus.executing,
                execution_group=1,
            )
        )
        db_session.flush()

        result = compute_batch_step_progress(
            project_id,
            batch_ids=[batch_id, "BATCH-DOES-NOT-EXIST"],
            db=db_session,
        )
        assert result == {batch_id: 100, "BATCH-DOES-NOT-EXIST": 0}

    def test_helper_scopes_by_project_id(self, db_session: Session) -> None:
        """Two projects with same-named work_item_id; only project A's steps are counted.

        Critical regression guard: ensure the join on BatchItem.project_id is not omitted.
        """
        project_a = "proj-A"
        project_b = "proj-B"
        work_item_id = "WI-SAME-ID"

        for pid in [project_a, project_b]:
            project = Project(
                id=pid, display_name=f"Project {pid}", repo_root="/repos/test", config={}
            )
            db_session.add(project)
            work_item = WorkItem(
                id=work_item_id,
                project_id=pid,
                title=f"Item in {pid}",
                type=WorkItemType.Feature,
                phase=WorkItemPhase.active,
                status=WorkItemStatus.in_progress,
                config={},
                depends_on=[],
                blocks=[],
            )
            db_session.add(work_item)
            db_session.flush()

            for i in range(1, 11):
                completed = 3 if pid == project_a else 8
                status = StepStatus.completed if i <= completed else StepStatus.pending
                db_session.add(
                    WorkflowStep(
                        project_id=pid,
                        work_item_id=work_item_id,
                        step_id=f"{pid}-{work_item_id}-step-{i}",
                        step_number=i,
                        step_type=StepType.implementation,
                        agent_label="test-agent",
                        status=status,
                    )
                )
            batch = Batch(id=f"batch-{pid}", project_id=pid, status=BatchStatus.executing)
            db_session.add(batch)
            db_session.add(
                BatchItem(
                    project_id=pid,
                    batch_id=f"batch-{pid}",
                    work_item_id=work_item_id,
                    status=BatchItemStatus.executing,
                    execution_group=1,
                )
            )
            db_session.flush()

        result_a = compute_batch_step_progress(project_a, batch_ids=["batch-proj-A"], db=db_session)
        result_b = compute_batch_step_progress(project_b, batch_ids=["batch-proj-B"], db=db_session)

        assert result_a == {"batch-proj-A": 30}, "Project A has 3/10 steps done → 30%, not 80%"
        assert result_b == {"batch-proj-B": 80}, "Project B has 8/10 steps done → 80%, not 30%"


# ---------------------------------------------------------------------------
# Test: Regression — via the routers (Requirement 4)
# ---------------------------------------------------------------------------


class TestRouterProgressMatch:
    """Router-level regression: _active_batches and _all_batches must agree."""

    def test_active_batches_and_all_batches_match_on_partial(self, db_session: Session) -> None:
        """Both routers return the same progress_pct for the same batch (3/10 done)."""
        project_id = "test-router-match"
        work_item_id = "WI-ROUTER-MATCH"
        batch_id = "batch-router-match"

        _seed_project_and_work_item(db_session, project_id, work_item_id)
        _seed_three_of_ten_steps(db_session, project_id, work_item_id)

        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=work_item_id,
                status=BatchItemStatus.executing,
                execution_group=1,
            )
        )
        db_session.flush()

        dash_rows = _active_batches(project_id, db_session)
        full_rows = _all_batches(project_id, db_session, status_filter=[])

        assert dash_rows[0].progress_pct == full_rows[0].progress_pct
        assert dash_rows[0].progress_pct == 30

    def test_active_batches_total_items_is_item_count_not_step_count(
        self, db_session: Session
    ) -> None:
        """total_items counts batch items (1), not workflow steps (10).

        Prevents a future refactor from accidentally switching total_items to a
        step count and breaking the semantics.
        """
        project_id = "test-item-count"
        work_item_id = "WI-ITEM-COUNT"
        batch_id = "batch-item-count"

        _seed_project_and_work_item(db_session, project_id, work_item_id)
        _seed_three_of_ten_steps(db_session, project_id, work_item_id)

        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=work_item_id,
                status=BatchItemStatus.executing,
                execution_group=1,
            )
        )
        db_session.flush()

        rows = _active_batches(project_id, db_session)
        assert rows[0].total_items == 1
        assert rows[0].completed_items == 0


# ---------------------------------------------------------------------------
# Test: HTTP smoke (Requirement 5)
# ---------------------------------------------------------------------------


class TestHttpProgressSmoke:
    """Smoke tests: confirm the progress percentage flows into the rendered HTML."""

    def test_project_dashboard_html_contains_30_percent(
        self, client: TestClient, db_session: Session
    ) -> None:
        """GET /project/{id}/ — rendered HTML must contain 30% in Active Batches card."""
        project_id = "test-http-dash"
        work_item_id = "WI-HTTP-DASH"
        batch_id = "batch-http-dash"

        _seed_project_and_work_item(db_session, project_id, work_item_id)
        _seed_three_of_ten_steps(db_session, project_id, work_item_id)

        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=work_item_id,
                status=BatchItemStatus.executing,
                execution_group=1,
            )
        )
        db_session.flush()
        db_session.commit()

        response = client.get(f"/project/{project_id}/")
        assert response.status_code == 200
        html = response.text
        assert "30%" in html or "30% complete" in html, html

    def test_batches_list_html_contains_30_percent(
        self, client: TestClient, db_session: Session
    ) -> None:
        """GET /project/{id}/batches — rendered HTML must contain 30% in Progress column."""
        project_id = "test-http-batches"
        work_item_id = "WI-HTTP-BATCHES"
        batch_id = "batch-http-batches"

        _seed_project_and_work_item(db_session, project_id, work_item_id)
        _seed_three_of_ten_steps(db_session, project_id, work_item_id)

        batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
        db_session.add(batch)
        db_session.add(
            BatchItem(
                project_id=project_id,
                batch_id=batch_id,
                work_item_id=work_item_id,
                status=BatchItemStatus.executing,
                execution_group=1,
            )
        )
        db_session.flush()
        db_session.commit()

        response = client.get(f"/project/{project_id}/batches")
        assert response.status_code == 200
        html = response.text
        assert "30%" in html or "30% complete" in html, html
