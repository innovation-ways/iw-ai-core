"""Integration tests for CR-00097: pre-existing QV failure suppression.

Verifies:
- AC1/AC2: BatchManager._upsert_qv_baseline UPDATE path does not raise
- AC4: attempt_fix_cycle transitions failed → skipped when all failures are pre-existing
- AC5: New failures (not in baseline) are NOT suppressed
- AC6: Stale baseline SHA triggers recompute and STILL suppresses when failures match

Uses real PostgreSQL testcontainer via the shared fixtures (db_engine, db_session,
test_project). NEVER connects to the live DB on port 5433.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from orch.daemon.batch_manager import BatchManager
from orch.daemon.fix_cycle import _get_review_findings, attempt_fix_cycle
from orch.daemon.qv_baseline import (
    FailureEntry,
    Fingerprint,
    _SuppressedFindings,
)
from orch.db.models import (
    DaemonEvent,
    FixCycle,
    Project,
    QvBaseline,
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


def _unique_id(prefix: str = "CR-00097") -> str:
    """Generate a unique ID with a UUID suffix for test isolation.

    Args:
        prefix: Prefix to prepend to the UUID hex suffix.

    Returns:
        A unique string in the form ``<prefix>-<8-char-hex>``.
    """
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _make_worktree(
    tmp_path: Path,
    item_id: str,
    gate: str = "integration-tests",
) -> Path:
    """Create a minimal worktree with manifest + .git marker."""
    worktree = tmp_path / "worktrees" / item_id
    worktree.mkdir(parents=True, exist_ok=True)
    (worktree / ".git").mkdir()
    (worktree / ".git").chmod(0o755)

    manifest_dir = worktree / "ai-dev" / "active" / item_id
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": item_id,
        "steps": [
            {
                "step": f"{item_id}-S14",
                "gate": gate,
                "command": "make allure-integration",
            }
        ],
    }
    (manifest_dir / "workflow-manifest.json").write_text(json.dumps(manifest))
    return worktree


def _create_qv_step(
    db: Session,
    project_id: str,
    item_id: str,
    gate: str,
    step_number: int = 14,
) -> WorkflowStep:
    """Create WorkItem + QV WorkflowStep (or reuse if already exists)."""
    existing = db.execute(
        select(WorkItem).where(
            WorkItem.project_id == project_id,
            WorkItem.id == item_id,
        )
    ).scalar_one_or_none()

    if existing is None:
        item = WorkItem(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Test item {item_id}",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db.add(item)
        db.flush()
    else:
        item = existing

    step = WorkflowStep(
        project_id=project_id,
        work_item_id=item_id,
        step_number=step_number,
        step_id=f"{item_id}-S{step_number}",
        agent_label=f"Test_{gate}",
        step_type=StepType.quality_validation,
        status=StepStatus.failed,
        gate=gate,
        command="make allure-integration",
    )
    db.add(step)
    db.flush()
    return step


def _insert_pre_existing_baseline(
    db: Session,
    step_id: int,
    gate: str,
    base_sha: str,
    failures: list[dict[str, str]],
) -> None:
    """Insert a QvBaseline row representing pre-existing failures."""
    fp: dict[str, Any] = {"failures": failures, "unparseable": []}
    db.add(
        QvBaseline(
            step_id=step_id,
            gate_name=gate,
            base_sha=base_sha,
            fingerprint=fp,
        )
    )
    db.flush()


def _insert_failed_step_run(
    db: Session,
    step_id: int,
    log_content: str,
) -> None:
    """Insert a failed StepRun for the given step."""
    db.add(
        StepRun(
            step_id=step_id,
            run_number=1,
            status=RunStatus.failed,
            log_content=log_content,
            log_file=None,
            error_message="integration-tests failed: exit=2",
        )
    )
    db.flush()


# ---------------------------------------------------------------------------
# Test 1 (AC1/AC2): BatchManager._upsert_qv_baseline UPDATE path
# ---------------------------------------------------------------------------


def test_upsert_qv_baseline_update_path_no_error(
    db_session: Session,
    test_project: Project,
    tmp_path: Path,
) -> None:
    """AC1/AC2: Updating an existing baseline row must not raise.

    The UPDATE path (same step_id + gate + base_sha, new fingerprint) was
    broken pre-CR-00097 — psycopg raised ProgrammingError on the UPDATE
    statement because the INSERT attempted to violate the partial uniqueness
    constraint implied by the WHERE clause. CR-00097 fixed _upsert_qv_baseline
    to DELETE stale rows first, then SELECT, then UPDATE or INSERT as appropriate.
    """
    item_id = _unique_id("ITM")
    _make_worktree(tmp_path, item_id)

    bm = BatchManager(
        project_id=test_project.id,
        project_config=MagicMock(
            id=test_project.id,
            worktree_base=".worktrees",
            working_dir=str(tmp_path),
        ),
        session_factory=lambda: db_session,
        config=MagicMock(baseline_qv_enabled=True),
    )

    step = _create_qv_step(db_session, test_project.id, item_id, "integration-tests")
    db_session.flush()

    # INSERT path
    fp_v1 = {
        "failures": [{"kind": "test", "key": "tests/foo.py::test_bar"}],
        "unparseable": [],
    }
    bm._upsert_qv_baseline(db_session, step.id, "integration-tests", "sha1abc", fp_v1)
    db_session.commit()

    row_after_insert = db_session.execute(
        select(QvBaseline).where(
            QvBaseline.step_id == step.id,
            QvBaseline.gate_name == "integration-tests",
        )
    ).scalar_one()
    assert row_after_insert.fingerprint == fp_v1

    # UPDATE path — must not raise
    fp_v2 = {"failures": [], "unparseable": []}
    bm._upsert_qv_baseline(db_session, step.id, "integration-tests", "sha1abc", fp_v2)
    db_session.commit()

    row = db_session.execute(
        select(QvBaseline).where(
            QvBaseline.step_id == step.id,
            QvBaseline.gate_name == "integration-tests",
        )
    ).scalar_one()
    assert row.fingerprint == fp_v2, "UPDATE path did not apply — fingerprint not updated"
    assert row.fingerprint["failures"] == []
    assert row.base_sha == "sha1abc"


# ---------------------------------------------------------------------------
# Test 2 (AC4): failed → skipped, no FixCycle, event with correct metadata
# ---------------------------------------------------------------------------


def test_pre_existing_only_marks_step_skipped_no_fix_cycle(
    db_session: Session,
    test_project: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: All failures are pre-existing → step transitions failed → skipped.

    attempt_fix_cycle must:
    - Detect the _SuppressedFindings marker from _get_qv_findings
    - Call _suppress_pre_existing_gate → step.status = skipped
    - Emit a qv_pre_existing_suppressed DaemonEvent
    - NOT create any FixCycle row
    """
    item_id = _unique_id("ITM")
    worktree = _make_worktree(tmp_path, item_id)

    step = _create_qv_step(db_session, test_project.id, item_id, "integration-tests")
    step.status = StepStatus.failed

    _insert_pre_existing_baseline(
        db_session,
        step.id,
        "integration-tests",
        "sha-base",
        [{"kind": "test", "key": "tests/test_foo.py::test_hardcoded_row_count"}],
    )
    _insert_failed_step_run(
        db_session,
        step.id,
        log_content="FAILED tests/test_foo.py::test_hardcoded_row_count",
    )
    db_session.commit()

    project_config = MagicMock(
        id=test_project.id,
        worktree_base=".worktrees",
        working_dir=str(tmp_path),
        qv_fix_cycle_max={},
        aggregate_fix_cycle_max=50,
        cascade_thrashing_threshold=3,
        cascade_thrashing_jaccard_min=0.5,
        config={},
        always_in_scope_paths=[],
    )
    daemon_config = MagicMock(baseline_qv_enabled=True)
    worktree_info = {"path": str(worktree)}

    monkeypatch.setenv("IW_CORE_BASELINE_QV", "true")
    with patch(
        "orch.daemon.fix_cycle._resolve_worktree_base_sha",
        return_value="sha-base",
    ):
        attempt_fix_cycle(
            db_session,
            step,
            test_project.id,
            project_config,
            daemon_config,
            worktree_info,
        )

    db_session.refresh(step)
    assert step.status == StepStatus.skipped, f"Expected step status=skipped, got {step.status!r}"

    fix_cycles = db_session.query(FixCycle).filter(FixCycle.step_id == step.id).all()
    assert len(fix_cycles) == 0, (
        f"Expected no FixCycle rows (suppression returned before _launch_fix_agent), "
        f"got {len(fix_cycles)}"
    )

    event = (
        db_session.query(DaemonEvent)
        .filter_by(project_id=test_project.id, event_type="qv_pre_existing_suppressed")
        .order_by(DaemonEvent.id.desc())
        .first()
    )
    assert event is not None, "Expected a qv_pre_existing_suppressed DaemonEvent"
    assert event.event_metadata is not None
    assert event.event_metadata["suppressed_count"] == 1
    assert event.event_metadata["gate_name"] == "integration-tests"
    suppressed_keys = event.event_metadata["suppressed_keys"]
    assert "tests/test_foo.py::test_hardcoded_row_count" in suppressed_keys


# ---------------------------------------------------------------------------
# Test 3 (AC5): New failures are NOT suppressed
# ---------------------------------------------------------------------------


def test_new_failure_is_not_suppressed(
    db_session: Session,
    test_project: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: A failure NOT present in baseline must produce ordinary findings, not marker."""
    item_id = _unique_id("ITM")
    worktree = _make_worktree(tmp_path, item_id)

    step = _create_qv_step(db_session, test_project.id, item_id, "integration-tests")
    step.status = StepStatus.failed

    _insert_pre_existing_baseline(
        db_session,
        step.id,
        "integration-tests",
        "sha-base",
        [{"kind": "test", "key": "tests/test_foo.py::test_hardcoded_row_count"}],
    )
    _insert_failed_step_run(
        db_session,
        step.id,
        log_content=(
            "FAILED tests/test_foo.py::test_hardcoded_row_count\n"
            "FAILED tests/test_bar.py::test_new_failure"
        ),
    )
    db_session.commit()

    daemon_config = MagicMock(baseline_qv_enabled=True)
    monkeypatch.setenv("IW_CORE_BASELINE_QV", "true")

    with patch(
        "orch.daemon.fix_cycle._resolve_worktree_base_sha",
        return_value="sha-base",
    ):
        findings = _get_review_findings(db_session, step, str(worktree), daemon_config)

    assert not isinstance(findings, _SuppressedFindings), (
        "New failure must NOT produce _SuppressedFindings marker"
    )
    assert findings != "", (
        f"Non-empty findings expected (new failure must surface); got {findings!r}"
    )
    assert "test_new_failure" in findings
    assert "test_hardcoded_row_count" not in findings, (
        "Pre-existing failure must be baseline-subtracted from findings"
    )


# ---------------------------------------------------------------------------
# Test 4 (AC6): Stale SHA recomputes and STILL suppresses
# ---------------------------------------------------------------------------


def test_stale_sha_recomputes_then_suppresses(
    db_session: Session,
    test_project: Project,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC6: Stale baseline SHA → recompute → still suppresses (pre-existing failures match).

    After a rebase, _get_qv_findings deletes the stale baseline, runs the gate command
    to recompute a fresh fingerprint, re-inserts the new baseline, and evaluates whether
    current failures are pre-existing in the RECOMPUTED baseline. If they still match,
    _SuppressedFindings is returned and the step is skipped. No FixCycle is created.
    """
    item_id = _unique_id("ITM")
    worktree = _make_worktree(tmp_path, item_id)

    step = _create_qv_step(db_session, test_project.id, item_id, "integration-tests")
    step.status = StepStatus.failed

    _insert_pre_existing_baseline(
        db_session,
        step.id,
        "integration-tests",
        "sha-OLD",
        [{"kind": "test", "key": "tests/test_foo.py::test_hardcoded_row_count"}],
    )
    _insert_failed_step_run(
        db_session,
        step.id,
        log_content="FAILED tests/test_foo.py::test_hardcoded_row_count",
    )
    db_session.commit()

    project_config = MagicMock(
        id=test_project.id,
        worktree_base=".worktrees",
        working_dir=str(tmp_path),
        qv_fix_cycle_max={},
        aggregate_fix_cycle_max=50,
        cascade_thrashing_threshold=3,
        cascade_thrashing_jaccard_min=0.5,
        config={},
        always_in_scope_paths=[],
    )
    daemon_config = MagicMock(baseline_qv_enabled=True)
    worktree_info = {"path": str(worktree)}

    pre_existing_key = "tests/test_foo.py::test_hardcoded_row_count"
    recomputed_fp = Fingerprint(
        failures=(FailureEntry(kind="test", key=pre_existing_key),),
        unparseable=(),
    )

    with (
        patch(
            "orch.daemon.fix_cycle._resolve_worktree_base_sha",
            return_value="sha-NEW",
        ),
        patch(
            "orch.daemon.fix_cycle._recompute_baseline_for_gate",
            return_value=recomputed_fp,
        ),
    ):
        attempt_fix_cycle(
            db_session,
            step,
            test_project.id,
            project_config,
            daemon_config,
            worktree_info,
        )

    db_session.refresh(step)
    assert step.status == StepStatus.skipped, (
        f"Expected step status=skipped (recomputed baseline matched current), got {step.status!r}"
    )

    fix_cycles = db_session.query(FixCycle).filter(FixCycle.step_id == step.id).all()
    assert len(fix_cycles) == 0, (
        f"Expected no FixCycle rows (suppression returned before _launch_fix_agent); "
        f"got {len(fix_cycles)}"
    )

    event = (
        db_session.query(DaemonEvent)
        .filter_by(project_id=test_project.id, event_type="qv_pre_existing_suppressed")
        .order_by(DaemonEvent.id.desc())
        .first()
    )
    assert event is not None, "Expected qv_pre_existing_suppressed event after stale-SHA recompute"
    assert event.event_metadata["suppressed_count"] == 1
    assert event.event_metadata["gate_name"] == "integration-tests"

    remaining = db_session.query(QvBaseline).filter(QvBaseline.step_id == step.id).all()
    assert len(remaining) == 1, (
        f"Expected exactly 1 baseline row (stale sha-OLD replaced by sha-NEW); got {len(remaining)}"
    )
    assert remaining[0].base_sha == "sha-NEW"
