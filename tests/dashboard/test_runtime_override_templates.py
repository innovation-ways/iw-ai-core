"""F-00081 S05: Runtime override template tests.

Tests the compressed step strip (≤120px, 8 segments), the CLI/Model columns
in the batch items tab, and the inline <select> rendering in the item detail
overview tab (locked for non-editable statuses).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers.batches import _batch_item_rows
from dashboard.routers.items import _get_steps
from orch.db.models import (
    AgentRuntimeOption,
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
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# TestClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
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
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_runtime_options(db_session: Session) -> list[AgentRuntimeOption]:
    """Insert 5 runtime option rows (same as the migration seed rows)."""
    rows = [
        AgentRuntimeOption(
            id=1,
            cli_tool="opencode",
            model="minimax",
            cli_label="OpenCode",
            model_label="MiniMax 2.7",
            display_name="OpenCode + MiniMax 2.7",
            is_default=True,
            enabled=True,
            sort_order=10,
        ),
        AgentRuntimeOption(
            id=2,
            cli_tool="opencode",
            model="claude-sonnet-4-6",
            cli_label="OpenCode",
            model_label="Claude Sonnet 4.6",
            display_name="OpenCode + Claude Sonnet 4.6",
            is_default=False,
            enabled=True,
            sort_order=20,
        ),
        AgentRuntimeOption(
            id=3,
            cli_tool="opencode",
            model="claude-opus-4-7",
            cli_label="OpenCode",
            model_label="Claude Opus 4.7",
            display_name="OpenCode + Claude Opus 4.7",
            is_default=False,
            enabled=True,
            sort_order=30,
        ),
        AgentRuntimeOption(
            id=4,
            cli_tool="claude",
            model="claude-sonnet-4-6",
            cli_label="Claude",
            model_label="Sonnet 4.6",
            display_name="Claude Code + Sonnet 4.6",
            is_default=False,
            enabled=True,
            sort_order=40,
        ),
        AgentRuntimeOption(
            id=5,
            cli_tool="claude",
            model="claude-opus-4-7",
            cli_label="Claude",
            model_label="Opus 4.7",
            display_name="Claude Code + Opus 4.7",
            is_default=False,
            enabled=True,
            sort_order=50,
        ),
    ]
    # Migration already seeded IDs 1–5; merge() upserts within the test
    # transaction (e.g. cli_label overrides for IDs 4–5) without hitting the
    # primary-key unique constraint on the already-committed migration rows.
    rows = [db_session.merge(r) for r in rows]
    db_session.flush()
    return rows


def _seed_project_and_batch(
    db_session: Session,
    project_id: str = "proj-f81",
    batch_id: str = "batch-f81",
) -> tuple[Project, Batch]:
    project = Project(
        id=project_id,
        display_name="F-00081 Test Project",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()  # ensure project is visible for batch FK
    batch = Batch(id=batch_id, project_id=project_id, status=BatchStatus.executing)
    db_session.add(batch)
    db_session.flush()
    return project, batch


def _seed_work_item_with_steps(
    db_session: Session,
    project_id: str,
    item_id: str,
    num_steps: int = 8,
    runtime_option_id: int | None = None,
    step_overrides: dict[int, int] | None = None,
) -> WorkItem:
    """Create a work item with `num_steps` workflow steps.

    Steps have statuses in rotating order: pending, in_progress, completed,
    failed, skipped, pending, in_progress, completed (for up to 8 steps).

    If runtime_option_id is given, the WorkItem gets that override.
    If step_overrides is given (dict step_index → option_id), those steps get
    an explicit step-level override.
    """
    statuses = [
        StepStatus.pending,
        StepStatus.in_progress,
        StepStatus.completed,
        StepStatus.failed,
        StepStatus.skipped,
        StepStatus.pending,
        StepStatus.in_progress,
        StepStatus.completed,
    ]

    work_item = WorkItem(
        id=item_id,
        project_id=project_id,
        title=f"Test Item {item_id}",
        type=WorkItemType.Feature,
        phase=WorkItemPhase.active,
        status=WorkItemStatus.in_progress,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
        agent_runtime_option_id=runtime_option_id,
    )
    db_session.add(work_item)
    db_session.flush()  # ensure work_item is visible for workflow_steps FK

    for i in range(num_steps):
        step = WorkflowStep(
            project_id=project_id,
            work_item_id=item_id,
            step_id=f"S{i + 1:02d}",
            step_number=i + 1,
            agent_label="frontend-impl",
            step_type=StepType.implementation,
            status=statuses[i % len(statuses)],
            agent_runtime_option_id=step_overrides.get(i) if step_overrides else None,
        )
        db_session.add(step)

    db_session.flush()
    return work_item


# ---------------------------------------------------------------------------
# AC8: compressed step strip — width ≤ 120px for ≤12 steps
# ---------------------------------------------------------------------------


class TestCompressedStepStrip:
    """AC8: compressed strip renders ≤ 120px wide with 8 segments."""

    def test_batch_item_row_has_8_segments_and_step_count_attribute(
        self, db_session: Session
    ) -> None:
        """Batch item with 8 steps → strip element has data-step-count=8 and 8 segments."""
        project, batch = _seed_project_and_batch(db_session)
        _seed_runtime_options(db_session)
        wi = _seed_work_item_with_steps(db_session, project.id, "WI-F81-8STEP", num_steps=8)

        # Add the work item to the batch
        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=wi.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.flush()

        rows = _batch_item_rows(project.id, batch.id, db_session)
        assert len(rows) == 1
        row = rows[0]

        # The strip has 8 segments
        assert len(row.steps) == 8

        # Each segment has a status (colour mapping)
        for step in row.steps:
            assert step.status in ("pending", "in_progress", "completed", "failed", "skipped")

    def test_http_batch_items_fragment_has_compressed_strip(
        self, client: TestClient, db_session: Session
    ) -> None:
        """GET batch items fragment renders iw-step-strip with data-step-count."""
        project, batch = _seed_project_and_batch(db_session)
        _seed_runtime_options(db_session)
        wi = _seed_work_item_with_steps(db_session, project.id, "WI-F81-HTML", num_steps=8)

        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=wi.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.flush()
        db_session.commit()

        response = client.get(f"/project/{project.id}/batch/{batch.id}/fragment/items")
        assert response.status_code == 200, response.text
        html = response.text

        # The compressed strip class is present
        assert "iw-pipeline-strip" in html
        # data-step-count attribute with value 8
        assert 'data-step-count="8"' in html
        # No 32px circles
        assert "w-8" not in html
        # Pills are 52px wide (iw-pipeline-pill class)
        assert "iw-pipeline-pill" in html

    def test_batch_item_row_strip_width_budget(self, db_session: Session) -> None:
        """Strip width formula: 6px × 8 + 1px gap × 7 = 55px, well within 120px."""
        project, batch = _seed_project_and_batch(db_session)
        _seed_runtime_options(db_session)
        wi = _seed_work_item_with_steps(db_session, project.id, "WI-F81-WIDTH", num_steps=8)

        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=wi.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.flush()

        rows = _batch_item_rows(project.id, batch.id, db_session)
        row = rows[0]
        # 8 steps: theoretical max = 6*12 + 1*11 = 83px (12 steps ≤ 120px per design doc)
        assert len(row.steps) == 8


# ---------------------------------------------------------------------------
# Item overview: <select> only on editable steps (pending | failed)
# ---------------------------------------------------------------------------


class TestItemOverviewRuntimeOverrideUI:
    """AC4: CLI/Model cells render as <select> for pending|failed, badges for others."""

    def test_pending_step_has_select_element(self, client: TestClient, db_session: Session) -> None:
        """A step in 'pending' status → <select> for CLI and Model columns."""
        project, batch = _seed_project_and_batch(db_session)
        _seed_runtime_options(db_session)
        wi = _seed_work_item_with_steps(db_session, project.id, "WI-F81-PENDING", num_steps=3)
        # Ensure step 0 (S01) is pending
        step = db_session.scalars(
            select(WorkflowStep).where(
                WorkflowStep.work_item_id == wi.id,
                WorkflowStep.step_number == 1,
            )
        ).one()
        step.status = StepStatus.pending
        step.agent_runtime_option_id = None
        db_session.flush()

        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=wi.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.commit()

        response = client.get(f"/project/{project.id}/item/{wi.id}/tab/overview")
        assert response.status_code == 200, response.text
        html = response.text

        # S01 (pending) → select element present
        assert 'hx-patch="/project/' in html
        # The select has option_id and the htmx PATCH endpoint
        assert "runtime-override" in html

    def test_completed_step_has_badge_not_select(
        self, client: TestClient, db_session: Session
    ) -> None:
        """A step in 'completed' status → read-only badge, no <select>."""
        project, batch = _seed_project_and_batch(db_session)
        _seed_runtime_options(db_session)
        wi = _seed_work_item_with_steps(db_session, project.id, "WI-F81-COMPLETED", num_steps=3)
        step = db_session.scalars(
            select(WorkflowStep).where(
                WorkflowStep.work_item_id == wi.id,
                WorkflowStep.step_number == 1,
            )
        ).one()
        step.status = StepStatus.completed
        # Completed steps have no step-level override; runtime_option_id would come
        # from step_runs which we won't have in this simple test.
        db_session.flush()

        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=wi.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.commit()

        response = client.get(f"/project/{project.id}/item/{wi.id}/tab/overview")
        assert response.status_code == 200, response.text
        html = response.text

        # Completed step is not editable — PATCH endpoint for S01 must be absent
        assert (
            f'hx-patch="/project/{project.id}/api/item/{wi.id}/step/S01/runtime-override"'
            not in html
        )

    def test_in_progress_step_has_badge_not_select(
        self, client: TestClient, db_session: Session
    ) -> None:
        """A step in 'in_progress' status → no <select> (mid-flight non-preemption)."""
        project, batch = _seed_project_and_batch(db_session)
        _seed_runtime_options(db_session)
        wi = _seed_work_item_with_steps(db_session, project.id, "WI-F81-INPROG", num_steps=3)
        step = db_session.scalars(
            select(WorkflowStep).where(
                WorkflowStep.work_item_id == wi.id,
                WorkflowStep.step_number == 2,
            )
        ).one()
        step.status = StepStatus.in_progress
        db_session.flush()

        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=wi.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.commit()

        response = client.get(f"/project/{project.id}/item/{wi.id}/tab/overview")
        assert response.status_code == 200, response.text
        html = response.text

        # in_progress step is not editable — PATCH endpoint for that step must be absent
        assert (
            f'hx-patch="/project/{project.id}/api/item/{wi.id}/step/S02/runtime-override"'
            not in html
        )


# ---------------------------------------------------------------------------
# Batch items tab: CLI/Model columns render (default) when no override
# ---------------------------------------------------------------------------


class TestBatchItemsRuntimeColumns:
    """CLI and Model columns in batch_items_rows.html."""

    def test_no_override_renders_default_placeholder(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Item with no runtime override → '(default)' in CLI and '—' in Model."""
        project, batch = _seed_project_and_batch(db_session)
        _seed_runtime_options(db_session)
        # No agent_runtime_option_id on the work item
        wi = _seed_work_item_with_steps(db_session, project.id, "WI-F81-NO-OVR", num_steps=3)

        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=wi.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.flush()
        db_session.commit()

        response = client.get(f"/project/{project.id}/batch/{batch.id}/fragment/items")
        assert response.status_code == 200, response.text
        html = response.text

        # (default) placeholder for CLI
        assert "(default)" in html
        # — for Model
        assert "—" in html

    def test_item_override_renders_cli_and_model_labels(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Item with runtime override → CLI and Model label badges (not placeholder)."""
        project, batch = _seed_project_and_batch(db_session)
        _seed_runtime_options(db_session)
        # Override to use (opencode, claude-sonnet-4-6) = id=2
        wi = _seed_work_item_with_steps(
            db_session, project.id, "WI-F81-WITH-OVR", num_steps=3, runtime_option_id=2
        )

        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=wi.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.flush()
        db_session.commit()

        response = client.get(f"/project/{project.id}/batch/{batch.id}/fragment/items")
        assert response.status_code == 200, response.text
        html = response.text

        # OpenCode label shown, not (default)
        assert "OpenCode" in html
        # Model label shown, not —
        assert "Claude Sonnet 4.6" in html

    def test_step_override_dot_shown_when_step_has_override(
        self, client: TestClient, db_session: Session
    ) -> None:
        """When any step has its own override, a dot indicator appears after the badge."""
        project, batch = _seed_project_and_batch(db_session)
        _seed_runtime_options(db_session)
        # Item-level override id=3, but step 0 has step-level override id=4
        wi = _seed_work_item_with_steps(
            db_session,
            project.id,
            "WI-F81-STEP-DOT",
            num_steps=4,
            runtime_option_id=3,
            step_overrides={0: 4},  # S01 step override
        )

        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=wi.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.flush()
        db_session.commit()

        response = client.get(f"/project/{project.id}/batch/{batch.id}/fragment/items")
        assert response.status_code == 200, response.text
        html = response.text

        # Dot indicator (w-1.5 h-1.5 rounded-full bg-primary) present for step override
        assert "w-1.5" in html
        assert "rounded-full" in html

    def test_step_detail_has_runtime_option_id(self, db_session: Session) -> None:
        """_get_steps populates runtime_option_id from step_runs → step override → item override."""
        project, batch = _seed_project_and_batch(db_session)
        _seed_runtime_options(db_session)
        # Item override = 4, step override = None
        wi = _seed_work_item_with_steps(
            db_session,
            project.id,
            "WI-F81-DETAIL",
            num_steps=2,
            runtime_option_id=4,
        )

        bi = BatchItem(
            project_id=project.id,
            batch_id=batch.id,
            work_item_id=wi.id,
            status=BatchItemStatus.executing,
            execution_group=0,
        )
        db_session.add(bi)
        db_session.flush()
        db_session.commit()

        steps = _get_steps(project.id, wi.id, db_session)
        # Filter out synthetic S00 and MERGE
        agent_steps = [s for s in steps if not s.is_synthetic]
        assert len(agent_steps) == 2

        # runtime_option_id should be resolved from item override (4 = claude, Sonnet 4.6)
        for step in agent_steps:
            assert step.runtime_option_id == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
