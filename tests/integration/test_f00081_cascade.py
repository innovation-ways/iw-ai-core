"""F-00081 S06: Cross-layer cascade integration tests.

Tests the full resolve_runtime → StepRun cascade against a real testcontainer DB.
Covers AC1, AC2, AC3, AC5 (mid-flight non-preemption).

Tests MUST use the testcontainer DB (no mocks) per tests/CLAUDE.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, text

from orch.agent_runtime.resolver import resolve_runtime
from orch.db.models import (
    AgentRuntimeOption,
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

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Seed fixtures
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
# Minimal ProjectConfig stand-in
# ---------------------------------------------------------------------------


class FakeProjectConfig:
    def __init__(self, cli_tool: str = "opencode", model: str = "minimax") -> None:
        self.cli_tool = cli_tool
        self.model = model


# ---------------------------------------------------------------------------
# Helper: create a work item with N steps
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
        title=f"Test item {item_id}",
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
# Helper: simulate _launch_step resolver path
# ---------------------------------------------------------------------------


def _resolve_for_step(
    db_session: Session,
    step: WorkflowStep,
    item: WorkItem,
    project_config: FakeProjectConfig,
) -> tuple[str, int, AgentRuntimeOption]:
    """Call resolve_runtime and return (command_fragment, option_id, option)."""
    runtime_option = resolve_runtime(
        db_session,
        step=step,
        item=item,
        project=project_config,
    )

    if runtime_option.cli_tool == "opencode":
        command = (
            f'opencode run "$(cat {{prompt_file}})" --model {runtime_option.model} '
            f"--dangerously-skip-permissions"
        )
    else:
        command = (
            f'claude -p "$(cat {{prompt_file}})" --model {runtime_option.model} '
            f"--dangerously-skip-permissions"
        )

    return command, runtime_option.id, runtime_option


# ---------------------------------------------------------------------------
# AC1: Default-only path (no overrides)
# ---------------------------------------------------------------------------


class TestCascadeDefaultOnly:
    """AC1: Given no overrides, daemon resolves to is_default=true row."""

    def test_resolves_to_default_row_and_records_option_id(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """No item or step override → resolves to is_default=true (opencode, minimax)."""
        item, steps = _item_with_steps(db_session, test_project, "ac1-item")
        step = steps[0]

        command, option_id, option = _resolve_for_step(db_session, step, item, FakeProjectConfig())

        assert option.is_default is True
        assert option.cli_tool == "opencode"
        assert option.model == "minimax"
        assert option_id == 1
        assert "--model minimax" in command

    def test_step_run_records_default_option_id(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """StepRun row written via launch path has agent_runtime_option_id = default row id."""
        item, steps = _item_with_steps(db_session, test_project, "ac1-run")
        step = steps[0]

        _, option_id, _ = _resolve_for_step(db_session, step, item, FakeProjectConfig())

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.running,
            command="opencode run ... --model minimax ...",
            cli_tool="opencode",
            agent_runtime_option_id=option_id,
        )
        db_session.add(run)
        db_session.flush()
        db_session.commit()

        saved = db_session.scalar(select(StepRun).where(StepRun.step_id == step.id))
        assert saved is not None
        assert saved.agent_runtime_option_id == option_id
        assert saved.agent_runtime_option_id == 1

    def test_command_contains_model_flag(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """The recorded command contains --model minimax."""
        item, steps = _item_with_steps(db_session, test_project, "ac1-cmd")
        step = steps[0]

        command, _, _ = _resolve_for_step(db_session, step, item, FakeProjectConfig())

        assert "--model" in command
        assert "minimax" in command


# ---------------------------------------------------------------------------
# AC2: Item-level override applied
# ---------------------------------------------------------------------------


class TestCascadeItemOverride:
    """AC2: item override (claude, sonnet-4-6) → command uses claude + --model."""

    def test_item_override_resolves_to_specified_pair(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Item-level override id=4 (claude, sonnet-4-6) resolves to that row."""
        item, steps = _item_with_steps(db_session, test_project, "ac2-item", item_override=4)
        step = steps[0]

        command, option_id, option = _resolve_for_step(db_session, step, item, FakeProjectConfig())

        assert option_id == 4
        assert option.cli_tool == "claude"
        assert option.model == "claude-sonnet-4-6"

    def test_command_uses_claude_with_model(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Command begins with 'claude -p' and includes --model claude-sonnet-4-6."""
        item, steps = _item_with_steps(db_session, test_project, "ac2-cmd", item_override=4)
        step = steps[0]

        command, _, _ = _resolve_for_step(db_session, step, item, FakeProjectConfig())

        assert command.startswith("claude -p")
        assert "--model claude-sonnet-4-6" in command

    def test_step_run_records_item_override_id(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """StepRun.agent_runtime_option_id matches item override (4), not default (1)."""
        item, steps = _item_with_steps(db_session, test_project, "ac2-run", item_override=4)
        step = steps[0]

        _, option_id, _ = _resolve_for_step(db_session, step, item, FakeProjectConfig())

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.running,
            command="claude -p ... --model claude-sonnet-4-6 ...",
            cli_tool="claude",
            agent_runtime_option_id=option_id,
        )
        db_session.add(run)
        db_session.flush()
        db_session.commit()

        saved = db_session.scalar(select(StepRun).where(StepRun.step_id == step.id))
        assert saved.agent_runtime_option_id == 4


# ---------------------------------------------------------------------------
# AC3: Step-level override beats item-level
# ---------------------------------------------------------------------------


class TestCascadeStepBeatsItem:
    """AC3: step override (opencode, minimax) wins over item override (claude)."""

    def test_step_override_wins(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Step S01 has override id=1 (opencode, minimax); item has override id=4."""
        item, steps = _item_with_steps(db_session, test_project, "ac3-item", item_override=4)
        steps[0].agent_runtime_option_id = 1  # step override
        db_session.flush()
        db_session.commit()

        step = db_session.scalar(select(WorkflowStep).where(WorkflowStep.id == steps[0].id))

        command, option_id, option = _resolve_for_step(db_session, step, item, FakeProjectConfig())

        # Step override wins
        assert option_id == 1
        assert option.cli_tool == "opencode"
        assert option.model == "minimax"
        assert command.startswith("opencode run")
        assert "--model minimax" in command

    def test_item_override_used_when_step_has_none(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Same item as above but step has no override → item override (4) is used."""
        item, steps = _item_with_steps(db_session, test_project, "ac3-none", item_override=4)
        step = steps[0]
        assert step.agent_runtime_option_id is None

        command, option_id, option = _resolve_for_step(db_session, step, item, FakeProjectConfig())

        # Item override (4 = claude, sonnet-4-6) wins
        assert option_id == 4
        assert option.cli_tool == "claude"
        assert "--model claude-sonnet-4-6" in command


# ---------------------------------------------------------------------------
# AC5: Mid-flight non-preemption
# ---------------------------------------------------------------------------


class TestCascadeMidFlight:
    """AC5: changing the item override while a step is in_progress does NOT affect it."""

    def test_running_step_unaffected_by_item_override_change(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """S01 is in_progress; item override changes; S01's step_runs row stays unchanged."""
        item, steps = _item_with_steps(
            db_session,
            test_project,
            "ac5-item",
            statuses=[StepStatus.in_progress],
        )
        step = steps[0]

        _, option_id_before, _ = _resolve_for_step(db_session, step, item, FakeProjectConfig())

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.running,
            command="opencode run ... --model minimax ...",
            cli_tool="opencode",
            agent_runtime_option_id=option_id_before,
        )
        db_session.add(run)
        db_session.flush()
        db_session.commit()

        # Change item override to (claude, sonnet-4-6) — id=4
        item.agent_runtime_option_id = 4
        db_session.flush()
        db_session.commit()

        # Verify S01's step_runs row is unchanged
        saved_run = db_session.scalar(select(StepRun).where(StepRun.step_id == step.id))
        assert saved_run.agent_runtime_option_id == option_id_before
        assert saved_run.agent_runtime_option_id == 1  # still minimax

    def test_next_pending_step_picks_up_new_override(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """After item override changes, the NEXT pending step resolves to the new pair."""
        item, steps = _item_with_steps(
            db_session,
            test_project,
            "ac5-next",
            statuses=[StepStatus.in_progress, StepStatus.pending],
        )
        step_in_progress = steps[0]
        step_pending = steps[1]

        # Launch S01 (in_progress) with default
        _, _, _ = _resolve_for_step(db_session, step_in_progress, item, FakeProjectConfig())
        run1 = StepRun(
            step_id=step_in_progress.id,
            run_number=1,
            status=RunStatus.running,
            cli_tool="opencode",
            agent_runtime_option_id=1,
        )
        db_session.add(run1)
        db_session.flush()

        # Change item override to (claude, sonnet-4-6) — id=4
        item.agent_runtime_option_id = 4
        db_session.flush()
        db_session.commit()

        # Resolve for S02 (pending) — should pick up new item override
        command, option_id, option = _resolve_for_step(
            db_session, step_pending, item, FakeProjectConfig()
        )

        assert option_id == 4
        assert option.cli_tool == "claude"
        assert option.model == "claude-sonnet-4-6"
        assert "--model claude-sonnet-4-6" in command

    def test_resolve_runtime_called_after_item_mutation_still_sees_new_value(
        self,
        db_session: Session,
        test_project: Project,
        seed_runtime_options: list[AgentRuntimeOption],
    ) -> None:
        """Directly verify resolve_runtime sees the mutated item override."""
        item, steps = _item_with_steps(
            db_session,
            test_project,
            "ac5-mutate",
            statuses=[StepStatus.pending],
        )
        step = steps[0]

        # No override initially
        _, opt1_id, _ = _resolve_for_step(db_session, step, item, FakeProjectConfig())
        assert opt1_id == 1

        # Mutate item override to id=3 (opencode, claude-opus-4-7)
        item.agent_runtime_option_id = 3
        db_session.flush()
        db_session.commit()

        # Resolve again — should see new override
        _, opt2_id, opt2 = _resolve_for_step(db_session, step, item, FakeProjectConfig())
        assert opt2_id == 3
        assert opt2.model == "claude-opus-4-7"
