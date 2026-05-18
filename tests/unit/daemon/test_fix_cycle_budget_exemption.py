"""I-00101: Scope-escalated fix cycles must not count against fix-cycle budgets.

When a fix-cycle agent edits a file outside `scope.allowed_paths`, the daemon
marks the cycle `escalated` with `fix_metadata.scope_violations` non-empty.
These scope-escalated cycles are operator-decidable (amend or revert) — they
are NOT real failed retry attempts and must NOT consume per-step or aggregate
fix-cycle budgets.

Pre-fix behaviour: `_is_scope_escalation()` did not exist; both `.count()`
queries in `should_attempt_fix()` counted every FixCycle row including scope-
escalated ones. A scope escalation burned one of the operator's 5 retry slots
with no way to recover it.

Post-fix behaviour: both queries filter with `not_(_is_scope_escalation())`,
excluding `status=escalated AND fix_metadata.scope_violations` non-empty rows.
The step retains its full budget for genuine failures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import not_

from orch.daemon.fix_cycle import _is_scope_escalation
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    FixCycle,
    FixStatus,
    FixTrigger,
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


def _make_project_config(
    qv_fix_cycle_max: dict[str, int] | None = None,
    aggregate_fix_cycle_max: int = 25,
) -> ProjectConfig:
    """Build a minimal ProjectConfig for budget tests."""
    return ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        enabled=True,
        cli_tool="opencode",
        model="test-model",
        worktree_base="/worktrees",
        config={},
        qv_fix_cycle_max=qv_fix_cycle_max or {},
        aggregate_fix_cycle_max=aggregate_fix_cycle_max,
    )


def _make_qv_step(
    db_session: Session, project: Project, gate: str = "security-secrets"
) -> WorkflowStep:
    """Create a minimal qv-gate WorkflowStep in needs_fix status."""
    item = WorkItem(
        project_id=project.id,
        id="I-00101-TEST",
        type=WorkItemType.Feature,
        title="I-00101 test item",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db_session.add(item)
    step = WorkflowStep(
        project_id=project.id,
        work_item_id="I-00101-TEST",
        step_number=1,
        step_id="S01",
        agent_label="test",
        step_type=StepType.quality_validation,
        gate=gate,
        status=StepStatus.needs_fix,
    )
    db_session.add(step)
    db_session.flush()
    return step


def _make_project(db_session: Session, project_id: str) -> Project:
    """Create a Project row for tests."""
    project = Project(
        id=project_id,
        display_name=f"Test Project {project_id}",
        repo_root="/repos/test",
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


class TestScopeEscalatedBudgetExemption:
    """AC4: scope-escalated cycles do not count against fix-cycle budgets."""

    def test_i00101_scope_escalated_cycle_not_counted_toward_per_step_budget(
        self, db_session: Session
    ) -> None:
        """A scope-escalated cycle must NOT count toward per-step budget.

        Pre-fix: count() includes the row, so remaining == 4 (1 consumed).
        Post-fix: count() excludes it, so remaining == 5 (none consumed).
        """
        project = _make_project(db_session, "test-proj-budget-perstep")
        step = _make_qv_step(db_session, project, gate="security-secrets")

        db_session.add(
            FixCycle(
                step_id=step.id,
                cycle_number=1,
                status=FixStatus.escalated,
                trigger_type=FixTrigger.quality_validation,
                fix_metadata={"scope_violations": [".gitleaks.toml"]},
            )
        )
        db_session.commit()

        # Budget config: qv_fix_cycle_max={"security-secrets": 5}, aggregate_fix_cycle_max=25
        max_cycles = 5  # from qv_fix_cycle_max
        existing = (
            db_session.query(FixCycle)
            .filter(FixCycle.step_id == step.id)
            .filter(not_(_is_scope_escalation()))  # type: ignore[no-untyped-call]
            .count()
        )
        remaining = max_cycles - existing
        assert remaining == 5, (
            "Scope-escalated cycle must be exempt from per-step budget count "
            f"(expected remaining == 5, got {remaining})"
        )

    def test_i00101_scope_escalated_cycle_not_counted_toward_aggregate_budget(
        self, db_session: Session
    ) -> None:
        """A scope-escalated cycle must NOT count toward aggregate per-work-item budget.

        Pre-fix: aggregate_used == 1 (scope-escalated counted), blocking further retries.
        Post-fix: aggregate_used == 0 (scope-escalated excluded), step can retry.
        """
        project = _make_project(db_session, "test-proj-budget-agg")
        step = _make_qv_step(db_session, project, gate="security-secrets")

        db_session.add(
            FixCycle(
                step_id=step.id,
                cycle_number=1,
                status=FixStatus.escalated,
                trigger_type=FixTrigger.quality_validation,
                fix_metadata={"scope_violations": [".gitleaks.toml"]},
            )
        )
        db_session.commit()

        aggregate_max = 25
        aggregate_used = (
            db_session.query(FixCycle)
            .join(WorkflowStep, FixCycle.step_id == WorkflowStep.id)
            .filter(WorkflowStep.work_item_id == step.work_item_id)
            .filter(WorkflowStep.project_id == step.project_id)
            .filter(not_(_is_scope_escalation()))  # type: ignore[no-untyped-call]
            .count()
        )
        assert aggregate_used == 0, (
            "Scope-escalated cycle must be exempt from aggregate budget count "
            f"(expected aggregate_used == 0, got {aggregate_used})"
        )
        assert aggregate_used < aggregate_max, (
            f"Scope-escalated cycle must not block retries: "
            f"aggregate_used={aggregate_used} < aggregate_max={aggregate_max}"
        )

    def test_i00101_non_scope_escalated_cycle_IS_counted(  # noqa: N802
        self, db_session: Session
    ) -> None:
        """A vanilla escalated cycle (no scope_violations) MUST still count.

        This proves the filter is narrow — only scope-driven escalations are exempt.
        """
        project = _make_project(db_session, "test-proj-budget-vanilla-escalation")
        step = _make_qv_step(db_session, project, gate="security-secrets")

        # Escalated but without scope_violations (some future different cause)
        db_session.add(
            FixCycle(
                step_id=step.id,
                cycle_number=1,
                status=FixStatus.escalated,
                trigger_type=FixTrigger.quality_validation,
                fix_metadata={},  # no scope_violations key
            )
        )
        db_session.commit()

        max_cycles = 5
        existing = (
            db_session.query(FixCycle)
            .filter(FixCycle.step_id == step.id)
            .filter(not_(_is_scope_escalation()))  # type: ignore[no-untyped-call]
            .count()
        )
        assert existing == 1, (
            "Vanilla escalated cycle (no scope_violations) must be counted "
            f"(expected existing == 1, got {existing})"
        )
        remaining = max_cycles - existing
        assert remaining == 4

    def test_i00101_failed_cycle_IS_counted(  # noqa: N802
        self, db_session: Session
    ) -> None:
        """A failed cycle (status=failed) MUST still count toward budget.

        This is a sanity check that the predicate doesn't accidentally exempt
        non-escalated rows.
        """
        project = _make_project(db_session, "test-proj-budget-failed")
        step = _make_qv_step(db_session, project, gate="security-secrets")

        db_session.add(
            FixCycle(
                step_id=step.id,
                cycle_number=1,
                status=FixStatus.failed,
                trigger_type=FixTrigger.quality_validation,
                fix_metadata={},
            )
        )
        db_session.commit()

        max_cycles = 5
        existing = (
            db_session.query(FixCycle)
            .filter(FixCycle.step_id == step.id)
            .filter(not_(_is_scope_escalation()))  # type: ignore[no-untyped-call]
            .count()
        )
        assert existing == 1, (
            f"Failed cycle must be counted (expected existing == 1, got {existing})"
        )
        remaining = max_cycles - existing
        assert remaining == 4

    def test_i00101_multiple_scope_escalated_cycles_all_excluded(self, db_session: Session) -> None:
        """Two scope-escalated cycles on the same step must both be excluded."""
        project = _make_project(db_session, "test-proj-multi-escalation")
        step = _make_qv_step(db_session, project, gate="security-secrets")

        for i in range(1, 3):
            db_session.add(
                FixCycle(
                    step_id=step.id,
                    cycle_number=i,
                    status=FixStatus.escalated,
                    trigger_type=FixTrigger.quality_validation,
                    fix_metadata={"scope_violations": [f".gitleaks-{i}.toml"]},
                )
            )
        db_session.commit()

        max_cycles = 5
        existing = (
            db_session.query(FixCycle)
            .filter(FixCycle.step_id == step.id)
            .filter(not_(_is_scope_escalation()))  # type: ignore[no-untyped-call]
            .count()
        )
        assert existing == 0, (
            "Two scope-escalated cycles must both be excluded "
            f"(expected existing == 0, got {existing})"
        )
        remaining = max_cycles - existing
        assert remaining == 5

    def test_i00101_mixed_scope_and_regular_cycles_only_regular_counted(
        self, db_session: Session
    ) -> None:
        """One scope-escalated + one failed cycle: only the failed one counts."""
        project = _make_project(db_session, "test-proj-mixed")
        step = _make_qv_step(db_session, project, gate="security-secrets")

        # Regular failed cycle
        db_session.add(
            FixCycle(
                step_id=step.id,
                cycle_number=1,
                status=FixStatus.failed,
                trigger_type=FixTrigger.quality_validation,
                fix_metadata={},
            )
        )
        # Scope-escalated cycle
        db_session.add(
            FixCycle(
                step_id=step.id,
                cycle_number=2,
                status=FixStatus.escalated,
                trigger_type=FixTrigger.quality_validation,
                fix_metadata={"scope_violations": [".gitleaks.toml"]},
            )
        )
        db_session.commit()

        max_cycles = 5
        existing = (
            db_session.query(FixCycle)
            .filter(FixCycle.step_id == step.id)
            .filter(not_(_is_scope_escalation()))  # type: ignore[no-untyped-call]
            .count()
        )
        assert existing == 1, (
            "Only the regular failed cycle should be counted; "
            f"scope-escalated must be excluded (expected existing == 1, got {existing})"
        )
        remaining = max_cycles - existing
        assert remaining == 4
