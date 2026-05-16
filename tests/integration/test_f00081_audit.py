"""F-00081 S06: Audit shape integration tests.

Tests the exact shape of DaemonEvent rows emitted by runtime override changes.
Covers:
- Single-step PATCH → scope='step', step_ids=[sid]
- Bulk PATCH (5 steps) → scope='bulk', step_ids length == 5
- Item-level PATCH → scope='item', step_ids=null

Tests use testcontainer DB (no mocks) per tests/CLAUDE.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

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
# Seed fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_runtime_options(db_session: Session) -> list[AgentRuntimeOption]:
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
    for r in rows:
        db_session.merge(r)
    db_session.commit()
    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item_with_steps(
    db_session: Session,
    project: Project,
    item_id: str,
    *,
    statuses: list[StepStatus] | None = None,
) -> tuple[WorkItem, list[WorkflowStep]]:
    if statuses is None:
        statuses = [StepStatus.pending]

    item = WorkItem(
        id=item_id,
        project_id=project.id,
        type=WorkItemType.Feature,
        title=f"Test {item_id}",
        status=WorkItemStatus.draft,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()

    steps = []
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
        steps.append(step)

    db_session.flush()
    db_session.commit()
    return item, steps


def _get_test_client(db_session: Session):
    """Return a TestClient with get_db overridden to use db_session.

    Temporarily clears IW_CORE_TEST_CONTEXT so dashboard module imports
    don't trigger the live-DB guard. IW_CORE_EXPECTED_INSTANCE_ID is also
    cleared (any value here would be harmless but we clear it for clarity).
    """
    import os

    original_test_context = os.environ.pop("IW_CORE_TEST_CONTEXT", None)
    os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        from fastapi.testclient import TestClient

        from dashboard.app import create_app
        from dashboard.dependencies import get_db

        def override_get_db():
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        return TestClient(app, raise_server_exceptions=True)
    finally:
        if original_test_context is not None:
            os.environ["IW_CORE_TEST_CONTEXT"] = original_test_context


# ---------------------------------------------------------------------------
# Audit shape tests
# ---------------------------------------------------------------------------


class TestAuditSingleStepPatch:
    """Single-step PATCH → exactly one DaemonEvent, scope='step', step_ids=[sid]."""

    def test_single_step_override_emits_correct_event_shape(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """PATCH /step/{step_id}/runtime-override emits event with scope='step'."""
        item, steps = _item_with_steps(db_session, test_project, "audit-ss-item")
        step = steps[0]

        before = db_session.query(DaemonEvent).count()

        client = _get_test_client(db_session)
        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/step/{step.step_id}/runtime-override",
            data={"option_id": "3"},
        )
        assert resp.status_code == 200, resp.text
        assert 'id="item-steps-table"' in resp.text

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
        meta = event.event_metadata
        assert meta["scope"] == "step"
        assert meta["step_ids"] == [step.step_id]
        assert meta["old_option_id"] is None
        assert meta["new_option_id"] == 3
        assert "actor" in meta

    def test_event_entity_type_is_work_item(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """The DaemonEvent entity_type is 'work_item' (not 'workflow_step')."""
        item, steps = _item_with_steps(db_session, test_project, "audit-ss-type")
        step = steps[0]

        client = _get_test_client(db_session)
        client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/step/{step.step_id}/runtime-override",
            data={"option_id": "2"},
        )

        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "runtime_override_changed",
            )
        )
        assert event.entity_type == "work_item"

    def test_clear_step_override_emits_event(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Clearing a step override (empty option_id) still emits an event."""
        item, steps = _item_with_steps(db_session, test_project, "audit-ss-clear")
        step = steps[0]

        before = db_session.query(DaemonEvent).count()

        client = _get_test_client(db_session)
        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/step/{step.step_id}/runtime-override",
            data={"option_id": ""},
        )
        assert resp.status_code == 200
        assert 'id="item-steps-table"' in resp.text

        after = db_session.query(DaemonEvent).count()
        assert after == before + 1

        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "runtime_override_changed",
            )
        )
        assert event.event_metadata["new_option_id"] is None
        assert event.event_metadata["scope"] == "step"


class TestAuditBulkPatch:
    """Bulk PATCH on 5 pending steps → exactly one event, step_ids length == 5."""

    def test_bulk_five_steps_emits_one_event_with_5_step_ids(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Bulk PATCH on 5 pending steps emits exactly one event with step_ids of length 5."""
        item, steps = _item_with_steps(
            db_session,
            test_project,
            "audit-bulk-5",
            statuses=[StepStatus.pending] * 5,
        )

        before = db_session.query(DaemonEvent).count()

        client = _get_test_client(db_session)
        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
            data={"option_id": "3"},
        )
        assert resp.status_code == 200, resp.text
        assert 'id="item-steps-table"' in resp.text

        after = db_session.query(DaemonEvent).count()
        assert after == before + 1

        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "runtime_override_changed",
                DaemonEvent.entity_id == item.id,
            )
        )
        meta = event.event_metadata
        assert meta["scope"] == "bulk"
        assert len(meta["step_ids"]) == 5
        assert meta["new_option_id"] == 3

    def test_bulk_event_old_option_id_reflects_prior_state(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """The old_option_id in the bulk event reflects the step's prior override value."""
        item, steps = _item_with_steps(
            db_session,
            test_project,
            "audit-bulk-old",
            statuses=[StepStatus.pending] * 3,
        )
        # Pre-set step overrides to id=2
        for step in steps:
            step.agent_runtime_option_id = 2
        db_session.flush()
        db_session.commit()

        client = _get_test_client(db_session)
        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
            data={"option_id": "4"},
        )
        assert resp.status_code == 200
        assert 'id="item-steps-table"' in resp.text

        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "runtime_override_changed",
            )
        )
        # old_option_id is captured from the first editable step at emission time
        assert event.event_metadata["old_option_id"] == 2
        assert event.event_metadata["new_option_id"] == 4

    def test_bulk_with_mixed_editable_non_editable_emits_event_with_only_editable_ids(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Bulk PATCH on item with 2 pending + 1 completed steps emits event with 2 step_ids."""
        item, steps = _item_with_steps(
            db_session,
            test_project,
            "audit-bulk-mixed",
            statuses=[StepStatus.pending, StepStatus.pending, StepStatus.completed],
        )

        client = _get_test_client(db_session)
        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
            data={"option_id": "2"},
        )
        assert resp.status_code == 200
        assert 'id="item-steps-table"' in resp.text

        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "runtime_override_changed",
            )
        )
        # Only pending steps are in step_ids
        assert len(event.event_metadata["step_ids"]) == 2


class TestAuditItemPatch:
    """Item-level PATCH → exactly one DaemonEvent, scope='item', step_ids=null."""

    def test_item_override_emits_event_with_scope_item_and_null_step_ids(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """PATCH /item/{iid}/runtime-override emits event with scope='item' and step_ids=null."""
        item, _ = _item_with_steps(
            db_session,
            test_project,
            "audit-item",
            statuses=[StepStatus.pending, StepStatus.failed],
        )

        before = db_session.query(DaemonEvent).count()

        client = _get_test_client(db_session)
        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override",
            data={"option_id": "4"},
        )
        assert resp.status_code == 204, resp.text

        after = db_session.query(DaemonEvent).count()
        assert after == before + 1

        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "runtime_override_changed",
                DaemonEvent.entity_id == item.id,
            )
        )
        meta = event.event_metadata
        assert meta["scope"] == "item"
        assert meta["step_ids"] is None  # item scope → null
        assert meta["new_option_id"] == 4

    def test_item_override_clears_old_option_id(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Clearing item override (empty option_id) emits event with old_option_id set, new=null."""
        item, _ = _item_with_steps(db_session, test_project, "audit-item-clear")
        # Pre-set item override
        item.agent_runtime_option_id = 2
        db_session.flush()
        db_session.commit()

        client = _get_test_client(db_session)
        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override",
            data={"option_id": ""},
        )
        assert resp.status_code == 204

        event = db_session.scalar(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "runtime_override_changed",
            )
        )
        assert event.event_metadata["old_option_id"] == 2
        assert event.event_metadata["new_option_id"] is None
        assert event.event_metadata["scope"] == "item"
        assert event.event_metadata["step_ids"] is None

    def test_item_override_reflects_in_work_item_after_commit(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """The item override is actually persisted after the event is emitted."""
        item, _ = _item_with_steps(db_session, test_project, "audit-item-persist")
        item_id = item.id

        client = _get_test_client(db_session)
        client.patch(
            f"/project/{test_project.id}/api/item/{item_id}/runtime-override",
            data={"option_id": "3"},
        )

        db_session.expire_all()
        saved = db_session.scalar(select(WorkItem).where(WorkItem.id == item_id))
        assert saved.agent_runtime_option_id == 3


class TestAuditMultipleCalls:
    """Each distinct API call emits its own event (no coalescing across calls)."""

    def test_two_separate_item_patches_produce_two_events(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Two sequential item-level PATCH calls produce two distinct DaemonEvent rows."""
        item, _ = _item_with_steps(db_session, test_project, "audit-two-item")

        client = _get_test_client(db_session)

        # First call: set to option 2
        client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override",
            data={"option_id": "2"},
        )

        # Second call: change to option 4
        client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override",
            data={"option_id": "4"},
        )

        events = db_session.scalars(
            select(DaemonEvent).where(
                DaemonEvent.project_id == test_project.id,
                DaemonEvent.event_type == "runtime_override_changed",
                DaemonEvent.entity_id == item.id,
            )
        ).all()

        assert len(events) == 2
        # Events are in chronological order
        assert events[0].event_metadata["new_option_id"] == 2
        assert events[1].event_metadata["new_option_id"] == 4
