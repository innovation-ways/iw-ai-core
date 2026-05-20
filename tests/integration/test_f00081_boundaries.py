"""F-00081 S06: Boundary behavior integration tests.

Tests every row of the Boundary Behavior table from the F-00081 design doc:
https://www.notion.so/innovationways/F-00081-Per-Item-Per-Step-Agent-Model-Override

Each test corresponds to exactly one row in the Boundary Behavior table.

Tests use testcontainer DB (no mocks) per tests/CLAUDE.md.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from orch.agent_runtime.resolver import resolve_runtime
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
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session


def _make_test_client(db_session: Session) -> TestClient:
    """Return a TestClient with get_db overridden to use db_session.

    Temporarily clears IW_CORE_TEST_CONTEXT so dashboard module imports
    don't trigger the live-DB guard.
    """
    original = os.environ.pop("IW_CORE_TEST_CONTEXT", None)
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
        if original is not None:
            os.environ["IW_CORE_TEST_CONTEXT"] = original


# ---------------------------------------------------------------------------
# Seed fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_runtime_options(db_session: Session) -> list[AgentRuntimeOption]:
    """Insert 5 runtime option rows (same as migration seed)."""
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
    # Migration 0f11be8f2147 made Pi + MiniMax 2.7 the catalogue default.
    # Clear it so this fixture's id=1 row can hold the single is_default
    # slot without tripping the uq_agent_runtime_options_one_default index.
    db_session.execute(
        text("UPDATE agent_runtime_options SET is_default = false WHERE is_default = true")
    )
    for r in rows:
        db_session.merge(r)
    db_session.commit()
    return rows


# ---------------------------------------------------------------------------
# Minimal stand-ins
# ---------------------------------------------------------------------------


class FakeProjectConfig:
    def __init__(self, cli_tool: str = "opencode", model: str = "minimax") -> None:
        self.cli_tool = cli_tool
        self.model = model


# ---------------------------------------------------------------------------
# Helper: create item + steps
# ---------------------------------------------------------------------------


def _item_with_steps(
    db_session: Session,
    project: Project,
    item_id: str,
    *,
    statuses: list[StepStatus] | None = None,
    item_override: int | None = None,
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
        agent_runtime_option_id=item_override,
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


# ---------------------------------------------------------------------------
# Boundary 1: Catalogue empty (no rows match cli_tool)
# ---------------------------------------------------------------------------


class TestBoundaryCatalogueEmpty:
    """Row: 'Operator deleted all (opencode, *) rows; project cli_tool=opencode'."""

    def test_resolver_falls_back_to_default_and_warns(
        self,
        db_session: Session,
        test_project: Project,
        caplog,
    ) -> None:
        """With no opencode rows present, resolver falls back to is_default=true row."""
        import logging

        # Migration 0f11be8f2147 made Pi the catalogue default; clear it so
        # the id=1 row merged below can reclaim the single is_default slot.
        db_session.execute(
            text("UPDATE agent_runtime_options SET is_default = false WHERE is_default = true")
        )
        db_session.merge(
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
            )
        )
        db_session.merge(
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
            )
        )
        db_session.commit()

        item, steps = _item_with_steps(db_session, test_project, "b1-item")
        step = steps[0]

        with caplog.at_level(logging.WARNING):
            option = resolve_runtime(
                db_session,
                step=step,
                item=item,
                project=FakeProjectConfig(cli_tool="opencode", model="minimax"),
            )

        # Falls back to the (only) default row
        assert option.cli_tool == "opencode"
        assert option.model == "minimax"
        assert option.is_default is True


# ---------------------------------------------------------------------------
# Boundary 2: Override points to disabled row
# ---------------------------------------------------------------------------


class TestBoundaryDisabledOverride:
    """Row: 'step.agent_runtime_option_id refers to row with enabled=false'."""

    def test_resolver_skips_disabled_step_override_falls_to_item(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
        caplog,
    ) -> None:
        """Disabled step override is ignored; item override is used instead."""
        import logging

        item, steps = _item_with_steps(db_session, test_project, "b2-item", item_override=4)
        # Override step with disabled row (id=5 = claude-opus-4-7, enabled=False)
        steps[0].agent_runtime_option_id = 5
        db_session.flush()
        db_session.commit()

        with caplog.at_level(logging.WARNING):
            option = resolve_runtime(
                db_session,
                step=steps[0],
                item=item,
                project=FakeProjectConfig(),
            )

        # Skipped disabled step (5) → falls to item override (4)
        assert option.id == 4
        assert "disabled" in caplog.text.lower()

    def test_resolver_skips_disabled_item_override_falls_to_project(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
        caplog,
    ) -> None:
        """Disabled item override is ignored; project default is used."""
        import logging

        item, steps = _item_with_steps(
            db_session,
            test_project,
            "b2b-item",
            item_override=5,  # disabled
        )

        with caplog.at_level(logging.WARNING):
            option = resolve_runtime(
                db_session,
                step=steps[0],
                item=item,
                project=FakeProjectConfig(cli_tool="opencode", model="claude-sonnet-4-6"),
            )

        # Skipped disabled item (5) → falls to project.toml lookup → id=2
        assert option.id == 2
        assert "disabled" in caplog.text.lower()

    def test_resolver_skips_disabled_item_falls_to_catalogue_default(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
        caplog,
    ) -> None:
        """Disabled item + project pair not in catalogue → falls to catalogue default."""
        import logging

        item, steps = _item_with_steps(
            db_session,
            test_project,
            "b2c-item",
            item_override=5,  # disabled
        )

        with caplog.at_level(logging.WARNING):
            option = resolve_runtime(
                db_session,
                step=steps[0],
                item=item,
                project=FakeProjectConfig(cli_tool="opencode", model="nonexistent"),
            )

        # Falls all the way to catalogue default (id=1)
        assert option.id == 1
        assert option.is_default is True


# ---------------------------------------------------------------------------
# Boundary 3: Bulk PATCH on item with zero editable steps
# ---------------------------------------------------------------------------


class TestBoundaryBulkZeroEditable:
    """Row: 'All steps in_progress/completed; returns 200, affected: 0, no event.'"""

    def test_bulk_zero_editable_returns_204_and_no_event(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Bulk PATCH on item with only completed/in_progress steps emits no DaemonEvent."""
        item, _ = _item_with_steps(
            db_session,
            test_project,
            "b3-item",
            statuses=[StepStatus.completed, StepStatus.in_progress],
        )

        before = db_session.query(DaemonEvent).count()

        client = _make_test_client(db_session)
        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
            data={"option_id": "2"},
        )
        assert resp.status_code == 200
        assert 'id="item-steps-table"' in resp.text

        after = db_session.query(DaemonEvent).count()
        assert after == before  # no event emitted


# ---------------------------------------------------------------------------
# Boundary 4: Step transitions mid-PATCH (race)
# ---------------------------------------------------------------------------


class TestBoundaryStepRace:
    """Row: 'User PATCHes a pending step that just transitioned to in_progress.'"""

    def test_single_step_patch_returns_409_when_step_becomes_in_progress(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """When step transitions to in_progress before the PATCH, endpoint returns 409."""
        item, steps = _item_with_steps(
            db_session, test_project, "b4-item", statuses=[StepStatus.pending]
        )
        step = steps[0]

        # Transition step to in_progress before the PATCH
        step.status = StepStatus.in_progress
        db_session.flush()
        db_session.commit()

        client = _make_test_client(db_session)
        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/step/{step.step_id}/runtime-override",
            data={"option_id": "2"},
        )
        assert resp.status_code == 409
        assert "not editable" in resp.text.lower()

    def test_bulk_skips_step_that_becomes_non_editable(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Bulk PATCH skips a step that is now in_progress and only updates the rest."""
        item, steps = _item_with_steps(
            db_session,
            test_project,
            "b4b-item",
            statuses=[StepStatus.pending, StepStatus.pending],
        )
        step0 = steps[0]
        step1 = steps[1]

        # Transition S01 to in_progress (simulating a race)
        step0.status = StepStatus.in_progress
        db_session.flush()
        db_session.commit()

        client = _make_test_client(db_session)
        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
            data={"option_id": "3"},
        )
        assert resp.status_code == 200
        assert 'id="item-steps-table"' in resp.text

        db_session.expire_all()
        # S01 (in_progress) should be untouched
        s0 = db_session.scalar(select(WorkflowStep).where(WorkflowStep.id == step0.id))
        assert s0.agent_runtime_option_id is None
        # S02 (pending) should be updated
        s1 = db_session.scalar(select(WorkflowStep).where(WorkflowStep.id == step1.id))
        assert s1.agent_runtime_option_id == 3


# ---------------------------------------------------------------------------
# Boundary 5: projects.toml references missing pair
# ---------------------------------------------------------------------------


class TestBoundaryProjectMissingPair:
    """Row: 'cli_tool=opencode model=bogus in projects.toml; daemon logs warning.'"""

    def test_resolver_falls_back_when_project_pair_not_in_catalogue(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
        caplog,
    ) -> None:
        """Project.toml pair not in catalogue → falls to default; warning logged."""
        import logging

        item, steps = _item_with_steps(db_session, test_project, "b5-item")
        step = steps[0]

        with caplog.at_level(logging.WARNING):
            option = resolve_runtime(
                db_session,
                step=step,
                item=item,
                project=FakeProjectConfig(cli_tool="opencode", model="bogus-model"),
            )

        # Falls to catalogue default (id=1)
        assert option.id == 1
        assert option.is_default is True


# ---------------------------------------------------------------------------
# Boundary 6: Pre-feature item shape (NULL FKs)
# ---------------------------------------------------------------------------


class TestBoundaryPreFeatureItem:
    """Row: 'All rows have agent_runtime_option_id NULL; resolver falls back gracefully.'"""

    def test_null_overrides_fall_to_catalogue_default(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Existing item before this feature has NULL FKs; resolver returns catalogue default."""
        item, steps = _item_with_steps(
            db_session,
            test_project,
            "b6-item",
            statuses=[StepStatus.pending],
            item_override=None,  # explicitly NULL
        )
        step = steps[0]
        assert step.agent_runtime_option_id is None
        assert item.agent_runtime_option_id is None

        option = resolve_runtime(
            db_session,
            step=step,
            item=item,
            project=FakeProjectConfig(),
        )

        # Falls to catalogue default
        assert option.id == 1
        assert option.is_default is True


# ---------------------------------------------------------------------------
# Boundary 7: Catalogue row deletion attempted while in use
# ---------------------------------------------------------------------------


class TestBoundaryFKPreventsDelete:
    """Row: 'DELETE row referenced by step_runs; FK ON DELETE RESTRICT prevents it.'"""

    def test_delete_referenced_option_raises_integrity_error(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """FK violation (RESTRICT) when deleting an option that step_runs references."""
        default_opt = db_session.execute(
            select(AgentRuntimeOption).where(AgentRuntimeOption.is_default.is_(True))
        ).scalar_one()

        item, steps = _item_with_steps(db_session, test_project, "b7-item")
        step = steps[0]

        # Write a step_run referencing the default option
        from orch.db.models import RunStatus, StepRun

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            agent_runtime_option_id=default_opt.id,
        )
        db_session.add(run)
        db_session.flush()
        db_session.commit()

        # Attempt to delete the referenced option
        stmt = text("DELETE FROM agent_runtime_options WHERE id=:id")
        with pytest.raises(IntegrityError):
            db_session.execute(stmt, {"id": default_opt.id})


# ---------------------------------------------------------------------------
# Boundary 8: Override mutation on terminal item
# ---------------------------------------------------------------------------


class TestBoundaryTerminalItem:
    """Item status terminal; endpoint returns 400."""

    def test_item_override_on_done_item_returns_400(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Setting override on an item with only terminal steps returns 400."""
        item, steps = _item_with_steps(
            db_session,
            test_project,
            "b8-item",
            statuses=[StepStatus.completed, StepStatus.completed],
        )
        # Item status is already completed (terminal)
        item.status = WorkItemStatus.completed

        client = _make_test_client(db_session)
        resp = client.patch(
            f"/project/{test_project.id}/api/item/{item.id}/runtime-override",
            data={"option_id": "2"},
        )
        assert resp.status_code == 400
        assert "no editable steps" in resp.text.lower()
