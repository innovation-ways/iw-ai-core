"""Integration tests for phantom QV gate auto-skip at iw approve / iw batch-approve.

Uses a real PostgreSQL testcontainer.  Does NOT mock validate_qv_gate or auto_skip_phantom_qv_gates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from sqlalchemy.orm import Session as SASession

from orch.cli.main import cli
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(
    runner: CliRunner,
    args: list[str],
    get_session: Any,
    project_id: str = "test-proj",
) -> Any:
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


def invoke_json(
    runner: CliRunner,
    args: list[str],
    get_session: Any,
    project_id: str = "test-proj",
) -> Any:
    return runner.invoke(
        cli,
        ["--project", project_id, "--json", *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project_with_makefile(
    db_session: SASession,
    test_project: Project,
    tmp_path: Path,
) -> Project:
    """Update test_project's repo_root to a real temp directory with a Makefile.

    Uses the existing test_project row (id='test-proj') created by the
    test_project fixture, avoiding duplicate-key conflicts.
    The update is scoped to the test transaction and will be rolled back.
    """
    test_project.repo_root = str(tmp_path)
    db_session.flush()

    # Write a Makefile that tests can then modify in-place
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        "lint:\n"
        "\t@echo lint-ok\n"
        "format-check:\n"
        "\t@echo format-check-ok\n"
        "type-check:\n"
        "\t@echo type-check-ok\n"
        "test-unit:\n"
        "\t@echo test-unit-ok\n"
    )
    return test_project


# ---------------------------------------------------------------------------
# AC1 — phantom make-target gate auto-skipped at iw approve
# ---------------------------------------------------------------------------


def test_iw_approve_auto_skips_phantom_makefile_gate(
    db_session: SASession,
    tmp_project_with_makefile: Project,
    cli_get_session: Any,
) -> None:
    """AC1: iw approve auto-skips a make-target phantom gate.

    Setup: Makefile has 'lint' but not 'arch-check'.
    Item I-99001 with S01-impl, S02-qv-gate(lint), S03-qv-gate(arch-check).
    After approve: S03 must be skipped with reason 'missing_makefile_target'.
    """
    # ---- WorkItem in draft status ----
    item = WorkItem(
        project_id="test-proj",
        id="I-99001",
        type=WorkItemType.Issue,
        title="AC1 test item",
        status=WorkItemStatus.draft,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)

    # ---- QV steps: one runnable (lint), one phantom (arch-check) ----
    s01 = WorkflowStep(
        project_id="test-proj",
        work_item_id="I-99001",
        step_number=1,
        step_id="S01",
        agent_label="Backend",
        opencode_agent="backend-impl",
        step_type=StepType.implementation,
    )
    s02 = WorkflowStep(
        project_id="test-proj",
        work_item_id="I-99001",
        step_number=2,
        step_id="S02",
        agent_label="qv-gate",
        step_type=StepType.quality_validation,
        gate="lint",
        command="make lint",
        status=StepStatus.pending,
    )
    s03 = WorkflowStep(
        project_id="test-proj",
        work_item_id="I-99001",
        step_number=3,
        step_id="S03",
        agent_label="qv-gate",
        step_type=StepType.quality_validation,
        gate="arch-check",
        command="make arch-check",
        status=StepStatus.pending,
    )
    db_session.add_all([s01, s02, s03])
    db_session.flush()

    # ---- Approve ----
    runner = CliRunner()
    result = invoke_json(runner, ["approve", "I-99001"], cli_get_session)
    assert result.exit_code == 0, result.output

    # ---- Verify JSON output ----
    out = json.loads(result.output)
    skipped = out.get("auto_skipped_steps", [])
    assert {"step_id": "S03", "gate": "arch-check", "reason": "missing_makefile_target"} in skipped
    # Real gate not skipped
    assert all(s["step_id"] != "S02" for s in skipped)

    # ---- Verify DB state ----
    db_session.expire_all()
    s02_db = (
        db_session.query(WorkflowStep)
        .filter_by(project_id="test-proj", work_item_id="I-99001", step_id="S02")
        .one()
    )
    s03_db = (
        db_session.query(WorkflowStep)
        .filter_by(project_id="test-proj", work_item_id="I-99001", step_id="S03")
        .one()
    )
    assert s02_db.status == StepStatus.pending, "Real gate must stay pending"
    assert s03_db.status == StepStatus.skipped, "Phantom gate must be auto-skipped"
    assert s03_db.completed_at is not None, "completed_at must be set on skipped step"

    # ---- Verify audit event ----
    ev = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.event_type == "step_auto_skipped_phantom_gate",
            DaemonEvent.entity_id == "I-99001/S03",
        )
        .one()
    )
    assert ev.event_metadata["gate"] == "arch-check"
    assert ev.event_metadata["reason"] == "missing_makefile_target"
    assert ev.event_metadata["trigger"] == "approve"


# ---------------------------------------------------------------------------
# AC2 — phantom cd <dir> gate auto-skipped at iw approve
# ---------------------------------------------------------------------------


def test_iw_approve_auto_skips_phantom_cd_gate(
    db_session: SASession,
    tmp_project_with_makefile: Project,
    cli_get_session: Any,
) -> None:
    """AC2: iw approve auto-skips a 'cd <dir>' phantom gate.

    Makefile is fine; no frontend/ directory exists.
    Item with a qv-gate command 'cd frontend && npx tsc --noEmit'.
    After approve: step must be skipped with reason 'missing_directory'.
    """
    item = WorkItem(
        project_id="test-proj",
        id="I-99002",
        type=WorkItemType.Issue,
        title="AC2 test item",
        status=WorkItemStatus.draft,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)

    s01 = WorkflowStep(
        project_id="test-proj",
        work_item_id="I-99002",
        step_number=1,
        step_id="S01",
        agent_label="qv-gate",
        step_type=StepType.quality_validation,
        gate="frontend-tsc",
        command="cd frontend && npx tsc --noEmit",
        status=StepStatus.pending,
    )
    db_session.add(s01)
    db_session.flush()

    runner = CliRunner()
    result = invoke_json(runner, ["approve", "I-99002"], cli_get_session)
    assert result.exit_code == 0, result.output

    out = json.loads(result.output)
    skipped = out.get("auto_skipped_steps", [])
    assert {"step_id": "S01", "gate": "frontend-tsc", "reason": "missing_directory"} in skipped

    db_session.expire_all()
    s01_db = (
        db_session.query(WorkflowStep)
        .filter_by(project_id="test-proj", work_item_id="I-99002", step_id="S01")
        .one()
    )
    assert s01_db.status == StepStatus.skipped

    ev = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.event_type == "step_auto_skipped_phantom_gate",
            DaemonEvent.entity_id == "I-99002/S01",
        )
        .one()
    )
    assert ev.event_metadata["reason"] == "missing_directory"
    assert ev.event_metadata["trigger"] == "approve"


# ---------------------------------------------------------------------------
# AC3 — real gates are NOT auto-skipped
# ---------------------------------------------------------------------------


def test_iw_approve_does_not_skip_real_gates(
    db_session: SASession,
    tmp_project_with_makefile: Project,
    cli_get_session: Any,
) -> None:
    """AC3: real gates are NOT auto-skipped.

    Makefile has lint, format-check, type-check, test-unit.
    Item with all four qv-gates pointing at those targets.
    After approve: no steps marked skipped, no audit events emitted.
    """
    item = WorkItem(
        project_id="test-proj",
        id="I-99003",
        type=WorkItemType.Issue,
        title="AC3 test item",
        status=WorkItemStatus.draft,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)

    gates = [
        ("lint", "make lint"),
        ("format-check", "make format-check"),
        ("type-check", "make type-check"),
        ("test-unit", "make test-unit"),
    ]
    steps = []
    for idx, (gate, command) in enumerate(gates, start=1):
        step = WorkflowStep(
            project_id="test-proj",
            work_item_id="I-99003",
            step_number=idx,
            step_id=f"S{idx:02d}",
            agent_label="qv-gate",
            step_type=StepType.quality_validation,
            gate=gate,
            command=command,
            status=StepStatus.pending,
        )
        steps.append(step)
        db_session.add(step)
    db_session.flush()

    runner = CliRunner()
    result = invoke_json(runner, ["approve", "I-99003"], cli_get_session)
    assert result.exit_code == 0, result.output

    out = json.loads(result.output)
    assert out.get("auto_skipped_steps", []) == []

    count = (
        db_session.query(DaemonEvent)
        .filter(DaemonEvent.event_type == "step_auto_skipped_phantom_gate")
        .count()
    )
    assert count == 0, "No phantom-skip events must be emitted for real gates"

    db_session.expire_all()
    for step in steps:
        s = (
            db_session.query(WorkflowStep)
            .filter_by(project_id="test-proj", work_item_id="I-99003", step_id=step.step_id)
            .one()
        )
        assert s.status == StepStatus.pending, f"{step.step_id} must stay pending"


# ---------------------------------------------------------------------------
# AC4 — iw batch-approve safety net: gate that was OK at approve time
#       becomes phantom after main-branch drift
# ---------------------------------------------------------------------------


def test_iw_batch_approve_runs_safety_net(
    db_session: SASession,
    tmp_project_with_makefile: Project,
    cli_get_session: Any,
) -> None:
    """AC4: iw batch-approve auto-skips phantom gates that became phantom after item approval.

    1. Create item, write Makefile WITH 'security-sast' target, approve item — no skip.
    2. Remove the 'security-sast' target from Makefile (simulates main-branch drift).
    3. Create batch including the item, approve batch.
    4. Assert the previously-runnable step is now skipped with trigger='batch_approve'.
    """
    repo_root = Path(tmp_project_with_makefile.repo_root)
    makefile = repo_root / "Makefile"

    # Initial Makefile: 'security-sast' target EXISTS
    makefile.write_text("lint:\n\t@echo lint-ok\nsecurity-sast:\n\t@echo security-sast-ok\n")

    # ---- Item approved while target exists ----
    item = WorkItem(
        project_id="test-proj",
        id="I-99004",
        type=WorkItemType.Issue,
        title="AC4 test item",
        status=WorkItemStatus.draft,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)

    s01 = WorkflowStep(
        project_id="test-proj",
        work_item_id="I-99004",
        step_number=1,
        step_id="S01",
        agent_label="qv-gate",
        step_type=StepType.quality_validation,
        gate="security-sast",
        command="make security-sast",
        status=StepStatus.pending,
    )
    db_session.add(s01)
    db_session.flush()

    runner = CliRunner()
    result = invoke_json(runner, ["approve", "I-99004"], cli_get_session)
    assert result.exit_code == 0, result.output

    out = json.loads(result.output)
    assert out.get("auto_skipped_steps", []) == [], (
        "security-sast gate must NOT be skipped at approve time (target exists)"
    )

    # Verify step still pending
    db_session.expire_all()
    s01_after_approve = (
        db_session.query(WorkflowStep)
        .filter_by(project_id="test-proj", work_item_id="I-99004", step_id="S01")
        .one()
    )
    assert s01_after_approve.status == StepStatus.pending

    # ---- Simulate main-branch drift: remove the target ----
    makefile.write_text("lint:\n\t@echo lint-ok\n")

    # ---- Create batch and approve ----
    batch = Batch(
        project_id="test-proj",
        id="BATCH-99001",
        status=BatchStatus.planning,
        cli_tool="opencode",
    )
    db_session.add(batch)
    bi = BatchItem(
        project_id="test-proj",
        batch_id="BATCH-99001",
        work_item_id="I-99004",
        execution_group=0,
        status=BatchItemStatus.pending,
    )
    db_session.add(bi)
    db_session.flush()

    result = invoke_json(runner, ["batch-approve", "BATCH-99001"], cli_get_session)
    assert result.exit_code == 0, result.output

    out = json.loads(result.output)
    skipped = out.get("auto_skipped_steps", [])
    assert {
        "step_id": "S01",
        "gate": "security-sast",
        "reason": "missing_makefile_target",
    } in skipped

    # ---- Verify DB state: step now skipped ----
    db_session.expire_all()
    s01_db = (
        db_session.query(WorkflowStep)
        .filter_by(project_id="test-proj", work_item_id="I-99004", step_id="S01")
        .one()
    )
    assert s01_db.status == StepStatus.skipped

    ev = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.event_type == "step_auto_skipped_phantom_gate",
            DaemonEvent.entity_id == "I-99004/S01",
        )
        .one()
    )
    assert ev.event_metadata["reason"] == "missing_makefile_target"
    assert ev.event_metadata["trigger"] == "batch_approve"


# ---------------------------------------------------------------------------
# AC4 variant — batch-approve with multiple items, each with mixed gates
# ---------------------------------------------------------------------------


def test_iw_batch_approve_handles_multiple_items(
    db_session: SASession,
    tmp_project_with_makefile: Project,
    cli_get_session: Any,
) -> None:
    """Batch with several items, each with pending gates — batch-approve processes all.

    Items are placed directly in approved status (simulating items approved
    before the auto-skip feature was added, or externally approved).
    All have mixed runnable/phantom gates.  Batch-approve's safety-net runs
    and auto-skips the phantom ones.

    Note: the real gates (lint) are already 'approved' (pending QV status)
    and stay pending; only the phantom gates (arch-check) are skipped.
    """
    runner = CliRunner()

    def _make_approved_item(item_id: str) -> None:
        """Create an item already in approved status with mixed gates."""
        item = WorkItem(
            project_id="test-proj",
            id=item_id,
            type=WorkItemType.Issue,
            title=f"Multi-item batch test {item_id}",
            status=WorkItemStatus.approved,  # already approved externally
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(item)
        s01 = WorkflowStep(
            project_id="test-proj",
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="qv-gate",
            step_type=StepType.quality_validation,
            gate="lint",
            command="make lint",  # runnable
            status=StepStatus.pending,
        )
        s02 = WorkflowStep(
            project_id="test-proj",
            work_item_id=item_id,
            step_number=2,
            step_id="S02",
            agent_label="qv-gate",
            step_type=StepType.quality_validation,
            gate="arch-check",  # phantom
            command="make arch-check",
            status=StepStatus.pending,
        )
        db_session.add_all([s01, s02])
        db_session.flush()

    _make_approved_item("I-99101")
    _make_approved_item("I-99102")
    _make_approved_item("I-99103")

    # Create batch
    result = invoke_json(runner, ["batch-create", "I-99101", "I-99102", "I-99103"], cli_get_session)
    assert result.exit_code == 0, result.output
    batch_id = json.loads(result.output)["batch_id"]

    # Approve batch — safety-net runs on the already-approved items
    result = invoke_json(runner, ["batch-approve", batch_id], cli_get_session)
    assert result.exit_code == 0, result.output

    out = json.loads(result.output)
    skipped = out.get("auto_skipped_steps", [])

    # All three items have phantom arch-check gates — all three must be skipped
    assert len(skipped) == 3, f"Expected 3 skipped steps, got {[s['step_id'] for s in skipped]}"
    skipped_ids = [s["step_id"] for s in skipped]
    assert skipped_ids == ["S02", "S02", "S02"], f"Expected all S02, got {skipped_ids}"

    # Real gates (S01/lint) must all still be pending
    db_session.expire_all()
    for item_id in ["I-99101", "I-99102", "I-99103"]:
        s01 = (
            db_session.query(WorkflowStep)
            .filter_by(project_id="test-proj", work_item_id=item_id, step_id="S01")
            .one()
        )
        assert s01.status == StepStatus.pending, f"{item_id}/S01 must stay pending"
