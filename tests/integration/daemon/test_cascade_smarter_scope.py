"""Tests for the smarter cascade reset logic that skips irrelevant QV gates."""

from __future__ import annotations

from orch.daemon import fix_cycle
from orch.db.models import (
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)


def test_gate_is_relevant_python_file_resets_all_known_gates() -> None:
    """Verifies that a changed Python file marks every registered gate as relevant."""
    gate_extensions = getattr(fix_cycle, "_GATE_RELEVANT_EXTENSIONS", {})
    assert gate_extensions

    gate_is_relevant = getattr(fix_cycle, "_gate_is_relevant", None)
    assert callable(gate_is_relevant)
    results = {
        gate_name: gate_is_relevant(gate_name, ["orch/foo.py"]) for gate_name in gate_extensions
    }

    assert results == dict.fromkeys(gate_extensions, True)


def test_gate_is_relevant_txt_file_skips_python_only_gates() -> None:
    """Verifies that a .txt file change is not relevant to lint/format but is relevant to assertion-
    check.
    """
    gate_is_relevant = getattr(fix_cycle, "_gate_is_relevant", None)
    assert callable(gate_is_relevant)
    lint_relevant = gate_is_relevant("lint", ["tests/assertion_free_baseline.txt"])
    format_relevant = gate_is_relevant("format", ["tests/assertion_free_baseline.txt"])
    assertion_relevant = gate_is_relevant("assertion-check", ["tests/assertion_free_baseline.txt"])

    assert lint_relevant is False
    assert format_relevant is False
    assert assertion_relevant is True


def test_gate_is_relevant_empty_changed_files_is_conservative() -> None:
    """Verifies that an empty changed-files list conservatively marks the gate as relevant."""
    gate_is_relevant = getattr(fix_cycle, "_gate_is_relevant", None)
    assert callable(gate_is_relevant)
    assert gate_is_relevant("lint", []) is True


def test_gate_is_relevant_unknown_gate_is_conservative() -> None:
    """Verifies that an unregistered gate name is conservatively treated as relevant for any file
    type.
    """
    gate_is_relevant = getattr(fix_cycle, "_gate_is_relevant", None)
    assert callable(gate_is_relevant)
    result_readme = gate_is_relevant("some-new-gate", ["README.md"])
    result_python = gate_is_relevant("some-new-gate", ["orch/foo.py"])

    assert result_readme is True
    assert result_python is True


def _seed_cascade_fixture(db_session):
    """Insert a project, work item, and three QV gate steps (lint, assertion-check, unit-tests) into
    the DB.

    Args:
        db_session: The SQLAlchemy session for the testcontainer DB.

    Returns:
        A tuple of (lint_gate, assertion_gate, failing_step) WorkflowStep rows.
    """
    project = Project(
        id="proj-cascade",
        display_name="Cascade",
        repo_root="/tmp/cascade",
        config={},
    )
    item = WorkItem(
        project_id=project.id,
        id="CR-00089-CASCADE",
        type=WorkItemType.Feature,
        title="cascade",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )

    lint_gate = WorkflowStep(
        project_id=project.id,
        work_item_id=item.id,
        step_number=1,
        step_id="S01",
        agent_label="qv",
        step_type=StepType.quality_validation,
        gate="lint",
        status=StepStatus.completed,
    )
    assertion_gate = WorkflowStep(
        project_id=project.id,
        work_item_id=item.id,
        step_number=2,
        step_id="S02",
        agent_label="qv",
        step_type=StepType.quality_validation,
        gate="assertion-check",
        status=StepStatus.completed,
    )
    failing_step = WorkflowStep(
        project_id=project.id,
        work_item_id=item.id,
        step_number=3,
        step_id="S03",
        agent_label="qv",
        step_type=StepType.quality_validation,
        gate="unit-tests",
        status=StepStatus.needs_fix,
    )

    db_session.add(project)
    db_session.add(item)
    db_session.add(lint_gate)
    db_session.add(assertion_gate)
    db_session.add(failing_step)
    db_session.flush()

    return lint_gate, assertion_gate, failing_step


def test_cascade_reset_skips_irrelevant_gates(db_session) -> None:
    """Verifies that cascade reset only resets gates relevant to the changed files (.txt skips
    lint).
    """
    lint_gate, assertion_gate, failing_step = _seed_cascade_fixture(db_session)

    cascade_reset = getattr(fix_cycle, "_cascade_reset_upstream_qv_gates", None)
    assert callable(cascade_reset)
    reset_ids = cascade_reset(
        db_session,
        cycle=None,
        failing_step=failing_step,
        project_id="proj-cascade",
        changed_files=["tests/assertion_free_baseline.txt"],
    )

    assert reset_ids == ["S02"]
    assert lint_gate.status == StepStatus.completed
    assert assertion_gate.status == StepStatus.pending


def test_cascade_reset_empty_changed_files_resets_all(db_session) -> None:
    """Verifies that cascade reset resets all upstream gates when the changed-files list is."""
    lint_gate, assertion_gate, failing_step = _seed_cascade_fixture(db_session)

    cascade_reset = getattr(fix_cycle, "_cascade_reset_upstream_qv_gates", None)
    assert callable(cascade_reset)
    reset_ids = cascade_reset(
        db_session,
        cycle=None,
        failing_step=failing_step,
        project_id="proj-cascade",
        changed_files=[],
    )

    assert reset_ids == ["S01", "S02"]
    assert lint_gate.status == StepStatus.pending
    assert assertion_gate.status == StepStatus.pending
