"""F-00081 S04: Runtime override API endpoint tests.

Tests the GET /project/{p}/api/runtime-options and
PATCH /project/{p}/api/item/{iid}/runtime-override (single, step, bulk) endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    AgentRuntimeOption,
    DaemonEvent,
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
# Seed fixture for runtime options
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_runtime_options(db_session: Session) -> list[AgentRuntimeOption]:
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
            cli_label="Claude Code",
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
            cli_label="Claude Code",
            model_label="Opus 4.7",
            display_name="Claude Code + Opus 4.7",
            is_default=False,
            enabled=False,
            sort_order=50,
        ),
    ]
    # Migration already seeded IDs 1–5; merge() upserts within the test
    # transaction so each test sees the fixture's intended values (e.g. ID 5
    # disabled) while the outer transaction rollback restores migration data
    # after each test.  Using add() would raise UniqueViolation on the
    # already-committed migration rows.
    # Migration 0f11be8f2147 made Pi + MiniMax 2.7 the catalogue default.
    # Clear it so the id=1 row merged below can hold the single is_default
    # slot without tripping the uq_agent_runtime_options_one_default index.
    db_session.execute(
        text("UPDATE agent_runtime_options SET is_default = false WHERE is_default = true")
    )
    merged = [db_session.merge(r) for r in rows]
    db_session.flush()
    return merged


# ---------------------------------------------------------------------------
# Helper: minimal WorkItem with one pending step
# ---------------------------------------------------------------------------


def _item_with_steps(
    db_session: Session,
    project: Project,
    item_id: str,
    statuses: list[StepStatus] | None = None,
) -> WorkItem:
    """Create a work item with one step per status in the list (default: one pending step)."""
    if statuses is None:
        statuses = [StepStatus.pending]

    item = WorkItem(
        id=item_id,
        project_id=project.id,
        type=WorkItemType.Feature,
        title=f"Test item {item_id}",
        status=WorkItemStatus.draft,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()

    for i, status in enumerate(statuses, start=1):
        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item_id,
            step_number=i,
            step_id=f"S{i:02d}",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=status,
        )
        db_session.add(step)

    db_session.flush()
    db_session.commit()
    return item


# ---------------------------------------------------------------------------
# GET /runtime-options tests
# ---------------------------------------------------------------------------


class TestGetRuntimeOptions:
    """GET /project/{p}/api/runtime-options — returns enabled rows ordered by sort_order."""

    def test_returns_enabled_rows_in_sort_order(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Only enabled rows are returned, sorted by sort_order then id."""
        resp = client.get(f"/project/{test_project.id}/api/runtime-options")
        assert resp.status_code == 200

        data = resp.json()
        # Disabled options must be excluded.
        ids = [r["id"] for r in data]
        assert 5 not in ids

        expected_ids = [
            row.id
            for row in db_session.scalars(
                select(AgentRuntimeOption)
                .where(AgentRuntimeOption.enabled.is_(True))
                .order_by(AgentRuntimeOption.sort_order, AgentRuntimeOption.id)
            ).all()
        ]
        assert ids == expected_ids

        # Check shape of first row
        row = data[0]
        assert row["id"] == 1
        assert row["cli_tool"] == "opencode"
        assert row["model"] == "minimax"
        assert row["cli_label"] == "OpenCode"
        assert row["model_label"] == "MiniMax 2.7"
        assert row["display_name"] == "OpenCode + MiniMax 2.7"
        assert row["is_default"] is True

    def test_includes_cache_header(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Cache-Control header is present (max-age=60)."""
        resp = client.get(f"/project/{test_project.id}/api/runtime-options")
        assert resp.status_code == 200
        assert "Cache-Control" in resp.headers
        assert "max-age=60" in resp.headers["Cache-Control"]

    def test_empty_catalogue_returns_empty_list(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """When no runtime options exist, returns an empty list (not 404)."""
        # Migration seeds 5 rows; delete them inside the test transaction so
        # this test verifies the empty-catalogue path without polluting others.
        db_session.query(AgentRuntimeOption).delete()
        db_session.flush()
        resp = client.get(f"/project/{test_project.id}/api/runtime-options")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# PATCH /runtime-override (item-level) tests
# ---------------------------------------------------------------------------


class TestPatchItemRuntimeOverride:
    """PATCH /project/{p}/api/item/{iid}/runtime-override — set/clear item-level override."""

    def test_sets_item_override(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """PATCH with option_id=2 sets work_items.agent_runtime_option_id = 2."""
        item = _item_with_steps(db_session, test_project, "item-set-override")

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override",
            data={"option_id": "2"},
        )
        assert resp.status_code == 204, resp.text

        db_session.expire_all()
        db_session.expire(item)
        saved = db_session.scalar(select(WorkItem).where(WorkItem.id == item.id))
        assert saved.agent_runtime_option_id == 2

    def test_clears_item_override(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """PATCH with no option_id (or empty) clears work_items.agent_runtime_option_id."""
        item = _item_with_steps(db_session, test_project, "item-clear-override")
        # Pre-set an override
        item.agent_runtime_option_id = 2
        db_session.commit()

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override",
            data={"option_id": ""},
        )
        assert resp.status_code == 204, resp.text

        db_session.expire_all()
        saved = db_session.scalar(select(WorkItem).where(WorkItem.id == item.id))
        assert saved.agent_runtime_option_id is None

    def test_emits_daemon_event(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Setting an override emits exactly one runtime_override_changed event."""
        item = _item_with_steps(db_session, test_project, "item-event")

        # Count events before
        before = db_session.query(DaemonEvent).count()

        client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override",
            data={"option_id": "3"},
        )

        after = db_session.query(DaemonEvent).count()
        assert after == before + 1

        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "runtime_override_changed",
                DaemonEvent.entity_id == item.id,
            )
        )
        assert event is not None
        assert event.event_metadata["scope"] == "item"
        assert event.event_metadata["new_option_id"] == 3
        assert event.event_metadata["old_option_id"] is None
        assert "step_ids" in event.event_metadata

    def test_rejects_nonexistent_option_id(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """404 when option_id does not reference an enabled row."""
        item = _item_with_steps(db_session, test_project, "item-bad-opt")

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override",
            data={"option_id": "999"},
        )
        assert resp.status_code == 404

    def test_rejects_disabled_option_id(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """404 when option_id references an enabled=False row (row 5 is disabled)."""
        item = _item_with_steps(db_session, test_project, "item-disabled-opt")

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override",
            data={"option_id": "5"},
        )
        assert resp.status_code == 404

    def test_rejects_item_with_no_editable_steps(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """400 when item has zero editable steps (all steps completed)."""
        item = _item_with_steps(
            db_session,
            test_project,
            "item-no-edit",
            statuses=[StepStatus.completed, StepStatus.completed],
        )

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override",
            data={"option_id": "2"},
        )
        assert resp.status_code == 400
        assert "no editable steps" in resp.text

    def test_rejects_nonexistent_item(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """404 when item does not exist or belongs to a different project."""
        resp = client.patch(
            f"/project/{test_project.id}/api/item/nonexistent-item/runtime-override",
            data={"option_id": "2"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /step/{step_id}/runtime-override tests
# ---------------------------------------------------------------------------


class TestPatchStepRuntimeOverride:
    """PATCH step-level runtime override endpoint."""

    def test_sets_step_override(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """PATCH with option_id=3 sets workflow_steps.agent_runtime_option_id = 3."""
        item = _item_with_steps(db_session, test_project, "step-set-override")

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/step/S01/runtime-override",
            data={"option_id": "3"},
        )
        assert resp.status_code == 200, resp.text
        assert 'id="item-steps-table"' in resp.text

        db_session.expire_all()
        step = db_session.scalar(
            select(WorkflowStep).where(
                WorkflowStep.work_item_id == item.id,
                WorkflowStep.step_id == "S01",
            )
        )
        assert step.agent_runtime_option_id == 3

    def test_clears_step_override(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """PATCH with empty option_id clears the step override."""
        item = _item_with_steps(db_session, test_project, "step-clear-override")
        step = db_session.scalar(
            select(WorkflowStep).where(
                WorkflowStep.work_item_id == item.id,
                WorkflowStep.step_id == "S01",
            )
        )
        step.agent_runtime_option_id = 3
        db_session.commit()

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/step/S01/runtime-override",
            data={"option_id": ""},
        )
        assert resp.status_code == 200, resp.text
        assert 'id="item-steps-table"' in resp.text

        db_session.expire_all()
        step = db_session.scalar(
            select(WorkflowStep).where(
                WorkflowStep.work_item_id == item.id,
                WorkflowStep.step_id == "S01",
            )
        )
        assert step.agent_runtime_option_id is None

    def test_emits_daemon_event_with_step_scope(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Emits runtime_override_changed with scope='step' and step_ids=[sid]."""
        item = _item_with_steps(db_session, test_project, "step-event")

        client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/step/S01/runtime-override",
            data={"option_id": "4"},
        )

        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "runtime_override_changed",
                DaemonEvent.entity_id == item.id,
            )
        )
        assert event is not None
        assert event.event_metadata["scope"] == "step"
        assert event.event_metadata["step_ids"] == ["S01"]
        assert event.event_metadata["new_option_id"] == 4

    def test_rejects_non_editable_step(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """409 Conflict when step status is not in {pending, failed, paused}."""
        item = _item_with_steps(
            db_session,
            test_project,
            "step-locked",
            statuses=[StepStatus.in_progress],
        )

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/step/S01/runtime-override",
            data={"option_id": "2"},
        )
        assert resp.status_code == 409
        assert "not editable" in resp.text
        assert "in_progress" in resp.text

    def test_rejects_completed_step(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """409 when step status is completed."""
        item = _item_with_steps(
            db_session,
            test_project,
            "step-done",
            statuses=[StepStatus.completed],
        )

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/step/S01/runtime-override",
            data={"option_id": "2"},
        )
        assert resp.status_code == 409
        assert "not editable" in resp.text

    def test_rejects_nonexistent_step(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """404 when step does not exist."""
        item = _item_with_steps(db_session, test_project, "step-missing")

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/step/S99/runtime-override",
            data={"option_id": "2"},
        )
        assert resp.status_code == 404

    def test_rejects_nonexistent_option_id(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """404 when option_id references a nonexistent or disabled row."""
        item = _item_with_steps(db_session, test_project, "step-bad-opt")

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/step/S01/runtime-override",
            data={"option_id": "999"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /runtime-override/bulk tests
# ---------------------------------------------------------------------------


class TestPatchBulkRuntimeOverride:
    """PATCH /project/{p}/api/item/{iid}/runtime-override/bulk — bulk update all editable steps."""

    def test_bulk_sets_all_editable_steps(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """All pending/failed steps are updated to the new option_id."""
        item = _item_with_steps(
            db_session,
            test_project,
            "bulk-set",
            statuses=[StepStatus.pending, StepStatus.failed],
        )

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
            data={"option_id": "2"},
        )
        assert resp.status_code == 200, resp.text
        assert 'id="item-steps-table"' in resp.text

        db_session.expire_all()
        steps = list(
            db_session.scalars(
                select(WorkflowStep).where(WorkflowStep.work_item_id == item.id)
            ).all()
        )
        for step in steps:
            assert step.agent_runtime_option_id == 2

    def test_bulk_skips_non_editable_steps(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Steps in completed/in_progress/skipped are silently skipped."""
        item = _item_with_steps(
            db_session,
            test_project,
            "bulk-skip",
            statuses=[
                StepStatus.pending,
                StepStatus.completed,
                StepStatus.in_progress,
                StepStatus.skipped,
            ],
        )

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
            data={"option_id": "2"},
        )
        assert resp.status_code == 200, resp.text
        assert 'id="item-steps-table"' in resp.text

        db_session.expire_all()
        steps = {
            s.step_id: s
            for s in db_session.scalars(
                select(WorkflowStep).where(WorkflowStep.work_item_id == item.id)
            ).all()
        }
        # Pending (editable) gets updated
        assert steps["S01"].agent_runtime_option_id == 2
        # Non-editable are untouched
        assert steps["S02"].agent_runtime_option_id is None
        assert steps["S03"].agent_runtime_option_id is None
        assert steps["S04"].agent_runtime_option_id is None

    def test_bulk_clears_all_editable_steps(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Bulk PATCH with empty option_id clears override on all editable steps."""
        item = _item_with_steps(
            db_session,
            test_project,
            "bulk-clear",
            statuses=[StepStatus.pending, StepStatus.failed],
        )
        # Pre-set all to option 3
        for step in db_session.scalars(
            select(WorkflowStep).where(WorkflowStep.work_item_id == item.id)
        ).all():
            step.agent_runtime_option_id = 3
        db_session.commit()

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
            data={"option_id": ""},
        )
        assert resp.status_code == 200, resp.text
        assert 'id="item-steps-table"' in resp.text

        db_session.expire_all()
        steps = list(
            db_session.scalars(
                select(WorkflowStep).where(WorkflowStep.work_item_id == item.id)
            ).all()
        )
        for step in steps:
            assert step.agent_runtime_option_id is None

    def test_bulk_emits_single_event(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Exactly one DaemonEvent is emitted regardless of how many steps are updated."""
        item = _item_with_steps(
            db_session,
            test_project,
            "bulk-event",
            statuses=[
                StepStatus.pending,
                StepStatus.failed,
            ],
        )

        before = db_session.query(DaemonEvent).count()

        client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
            data={"option_id": "4"},
        )

        after = db_session.query(DaemonEvent).count()
        assert after == before + 1

        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "runtime_override_changed",
                DaemonEvent.entity_id == item.id,
            )
        )
        assert event is not None
        assert event.event_metadata["scope"] == "bulk"
        # Both editable steps
        assert sorted(event.event_metadata["step_ids"]) == ["S01", "S02"]
        assert event.event_metadata["new_option_id"] == 4

    def test_bulk_zero_editable_steps_emits_no_event(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """When zero steps are updated, no DaemonEvent is emitted."""
        item = _item_with_steps(
            db_session,
            test_project,
            "bulk-zero",
            statuses=[StepStatus.completed, StepStatus.skipped],
        )

        before = db_session.query(DaemonEvent).count()

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
            data={"option_id": "2"},
        )
        assert resp.status_code == 200, resp.text
        assert 'id="item-steps-table"' in resp.text

        after = db_session.query(DaemonEvent).count()
        assert after == before  # no new event

    def test_bulk_rejects_invalid_option_id(
        self,
        client: TestClient,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """404 when option_id references a nonexistent or disabled row."""
        item = _item_with_steps(
            db_session,
            test_project,
            "bulk-bad-opt",
            statuses=[StepStatus.pending],
        )

        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
            data={"option_id": "999"},
        )
        assert resp.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
