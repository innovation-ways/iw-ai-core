"""I-00116 — Daemon must recover review-step run when verdict report exists on disk.

Pre-fix: when a code-review agent exits cleanly without calling `iw step-done`,
the daemon marks the run as crashed even when a well-formed verdict report file
is present on disk. This file tests the recovery path that S01 adds.

Three sub-bugs of I-00116:
  (a) step_monitor has no report-file-exists guard before declaring crash
  (b) fix_cycle caps per-step but not per-item (tested in integration suite)
  (c) review prompt scopes diff to unbounded `git diff HEAD` (tested separately)

Tests mock at the `_is_pid_alive` and `_probe_for_child` boundaries — NOT at
`_try_recover_completed_review_step` itself — so the bug-class blind spot cannot
recur via mock-over-mocking.

For each test, the StepRun is created via the ORM (so SQLAlchemy relationship
traversal works and _update_parent_step can reach the DB row via db.get()).
step_type and work_item_id are read from the WorkflowStep row (ws), NOT from
StepRun — StepRun does not have these columns. The F4 fix ensures this is safe
in production too.

For tests 1-3, run.step_id is the integer FK to workflow_steps.id. The
_try_recover_completed_review_step helper resolves step_str via db.get(WorkflowStep,
run.step_id).step_id so the glob pattern uses the correct string identifier.
Test 4 uses a mock db so db.get() returns a mock_step with the correct step_id.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orch.daemon.step_monitor import _check_step_health


def _make_report(tmp_path: Path, item_id: str, step_id: str, verdict: str = "pass") -> Path:
    """Write a well-formed reviewer report and return its path."""
    reports_dir = tmp_path / "ai-dev" / "active" / item_id / "reports"
    reports_dir.mkdir(parents=True)
    report = reports_dir / f"{item_id}_{step_id}_CodeReview_report.md"
    body = (
        f"# {item_id} {step_id} review\n\n"
        "```json\n"
        + json.dumps(
            {"step": step_id, "verdict": verdict, "findings": [], "mandatory_fix_count": 0}
        )
        + "\n```\n"
    )
    report.write_text(body)
    return report


# ---------------------------------------------------------------------------
# Test 1: canonical RED repro — report on disk → recovered, NOT crashed
# ---------------------------------------------------------------------------


def test_i00116_review_step_with_report_on_disk_is_recovered_not_crashed(
    db_session: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reproduction: agent exited cleanly + report on disk → run completed, NOT crashed.

    S01 adds a report-file-exists guard before `_handle_crashed`. The test:
      1. Creates a real StepRun via db_session with step_type=code_review
      2. Creates a well-formed verdict report on disk (mtime > started_at)
      3. Mocks PID-dead + no child → both guards fail (triggers the new path)
      4. Calls _check_step_health
      5. Asserts _handle_crashed was NOT called (the recovery path fired instead)

    Semantic assertion:
      - crashed.called == False  (BUG-FIXED: report found, step was recovered)

    Deleting the report-file guard or routing it past the correct boundary
    would cause this test to FAIL — catching the regression before it ships.
    """
    from orch.daemon import step_monitor as sm
    from orch.db.models import (
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

    session: object = db_session

    project = Project(
        id="test-proj-i00116-t1",
        display_name="Test Project I-00116 Test 1",
        repo_root=str(tmp_path),
        config={},
    )
    session.add(project)
    session.flush()

    item = WorkItem(
        project_id=project.id,
        id="I-00116-T1",
        type=WorkItemType.Feature,
        title="I-00116 test 1",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    session.add(item)
    session.flush()

    step = WorkflowStep(
        project_id=project.id,
        work_item_id=item.id,
        step_number=1,
        step_id="S02",
        agent_label="test",
        step_type=StepType.code_review,
        status=StepStatus.in_progress,
    )
    session.add(step)
    session.flush()

    now = datetime.now(UTC)
    _make_report(tmp_path, "I-00116-T1", "S02", verdict="pass")

    run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.running,
        pid=9999,
        pid_alive=True,
        command="test command",
        worktree_path=str(tmp_path),
        cli_tool="opencode",
        started_at=now - timedelta(minutes=5),
        last_heartbeat=now - timedelta(minutes=5),
        timeout_secs=1800,
    )
    session.add(run)
    session.flush()

    mock_config = MagicMock()
    mock_config.stall_threshold = 60

    monkeypatch.chdir(tmp_path)

    with (
        patch("orch.daemon.step_monitor._is_pid_alive", return_value=False),
        patch("orch.daemon.step_monitor._probe_for_child", return_value=False),
        patch("orch.daemon.step_monitor._handle_crashed") as crashed,
    ):
        sm._check_step_health(session, run, project_id=project.id, config=mock_config)

    # Semantic: report found → recovery path → NOT crashed
    assert not crashed.called, (
        "I-00116: review step with a verdict report on disk must NOT be marked crashed. "
        "_handle_crashed was called — the report-file guard is missing or broken."
    )


# ---------------------------------------------------------------------------
# Test 2: negative path — no report → _handle_crashed still fires
# ---------------------------------------------------------------------------


def test_i00116_review_step_without_report_still_marked_crashed(
    db_session: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Negative path: no report on disk → original _handle_crashed still fires.

    When the report is absent, the guard should fall through to `_handle_crashed`
    unchanged. This preserves the existing crash-detection safety net.

    Semantic assertion:
      - crashed.call_count == 1  (no report → true crash)
    """
    from orch.daemon import step_monitor as sm
    from orch.db.models import (
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

    session: object = db_session

    project = Project(
        id="test-proj-i00116-t2",
        display_name="Test Project I-00116 Test 2",
        repo_root=str(tmp_path),
        config={},
    )
    session.add(project)
    session.flush()

    item = WorkItem(
        project_id=project.id,
        id="I-00116-T2",
        type=WorkItemType.Feature,
        title="I-00116 test 2",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    session.add(item)
    session.flush()

    step = WorkflowStep(
        project_id=project.id,
        work_item_id=item.id,
        step_number=1,
        step_id="S03",
        agent_label="test",
        step_type=StepType.code_review,
        status=StepStatus.in_progress,
    )
    session.add(step)
    session.flush()

    now = datetime.now(UTC)
    # Deliberately NO report file — just the directory structure
    (tmp_path / "ai-dev" / "active" / "I-00116-T2" / "reports").mkdir(parents=True)

    run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.running,
        pid=9998,
        pid_alive=True,
        command="test command",
        worktree_path=str(tmp_path),
        cli_tool="opencode",
        started_at=now - timedelta(minutes=5),
        last_heartbeat=now - timedelta(minutes=5),
        timeout_secs=1800,
    )
    session.add(run)
    session.flush()

    mock_config = MagicMock()
    mock_config.stall_threshold = 60

    monkeypatch.chdir(tmp_path)

    with (
        patch("orch.daemon.step_monitor._is_pid_alive", return_value=False),
        patch("orch.daemon.step_monitor._probe_for_child", return_value=False),
        patch("orch.daemon.step_monitor._handle_crashed") as crashed,
    ):
        sm._check_step_health(session, run, project_id=project.id, config=mock_config)

    assert crashed.call_count == 1, (
        f"Expected exactly 1 call to _handle_crashed (no report on disk), got {crashed.call_count}."
    )


# ---------------------------------------------------------------------------
# Test 3: non-review step types follow the original _handle_crashed path
# ---------------------------------------------------------------------------


def test_i00116_non_review_step_type_is_unchanged(
    db_session: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Implementation step types follow the original _handle_crashed path.

    The report-file guard is scoped to code_review / code_review_final only.
    All other step types (implementation, qv, etc.) should be unaffected.

    Semantic assertion:
      - crashed.call_count == 1  (non-review type → old path)
    """
    from orch.daemon import step_monitor as sm
    from orch.db.models import (
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

    session: object = db_session

    project = Project(
        id="test-proj-i00116-t3",
        display_name="Test Project I-00116 Test 3",
        repo_root=str(tmp_path),
        config={},
    )
    session.add(project)
    session.flush()

    item = WorkItem(
        project_id=project.id,
        id="I-00116-T3",
        type=WorkItemType.Feature,
        title="I-00116 test 3",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    session.add(item)
    session.flush()

    step = WorkflowStep(
        project_id=project.id,
        work_item_id=item.id,
        step_number=1,
        step_id="S01",
        agent_label="test",
        step_type=StepType.implementation,  # NOT a review type
        status=StepStatus.in_progress,
    )
    session.add(step)
    session.flush()

    now = datetime.now(UTC)
    _make_report(tmp_path, "I-00116-T3", "S01", verdict="pass")

    run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.running,
        pid=9997,
        pid_alive=True,
        command="test command",
        worktree_path=str(tmp_path),
        cli_tool="opencode",
        started_at=now - timedelta(minutes=5),
        last_heartbeat=now - timedelta(minutes=5),
        timeout_secs=1800,
    )
    session.add(run)
    session.flush()

    mock_config = MagicMock()
    mock_config.stall_threshold = 60

    monkeypatch.chdir(tmp_path)

    with (
        patch("orch.daemon.step_monitor._is_pid_alive", return_value=False),
        patch("orch.daemon.step_monitor._probe_for_child", return_value=False),
        patch("orch.daemon.step_monitor._handle_crashed") as crashed,
    ):
        sm._check_step_health(session, run, project_id=project.id, config=mock_config)

    assert crashed.call_count == 1, (
        f"Expected exactly 1 call to _handle_crashed (non-review type), got {crashed.call_count}."
    )


# ---------------------------------------------------------------------------
# Test 4: recovery emits a DaemonEvent with the verdict in event_metadata
# ---------------------------------------------------------------------------


def test_i00116_recovered_run_emits_daemon_event_with_verdict(
    db_session: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """On successful recovery, a DaemonEvent of type 'step_run_recovered_from_report' is emitted.

    Uses a mock_db that intercepts db.get() so the string step_id works for glob matching
    while still allowing _update_parent_step to resolve the real WorkflowStep. The
    DaemonEvent is captured via a tracking mock to verify the event_type and metadata.

    Semantic assertions:
      - emit_event called once
      - event_type == 'step_run_recovered_from_report'
      - event_metadata['verdict'] == 'pass'
      - event_metadata['step_id'] == 'S02'
      - run.status == RunStatus.completed
    """
    from orch.daemon import step_monitor as sm
    from orch.db.models import (
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

    session: object = db_session

    project = Project(
        id="test-proj-i00116-e4",
        display_name="Test Project I-00116 Event Test",
        repo_root=str(tmp_path),
        config={},
    )
    session.add(project)
    session.flush()

    item = WorkItem(
        project_id=project.id,
        id="I-00116-E4",
        type=WorkItemType.Feature,
        title="I-00116 event test",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    session.add(item)
    session.flush()

    step = WorkflowStep(
        project_id=project.id,
        work_item_id=item.id,
        step_number=1,
        step_id="S02",
        agent_label="test",
        step_type=StepType.code_review,
        status=StepStatus.in_progress,
    )
    session.add(step)
    session.flush()

    now = datetime.now(UTC)
    _make_report(tmp_path, "I-00116-E4", "S02", verdict="pass")

    run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.running,
        pid=9999,
        pid_alive=True,
        command="test command",
        worktree_path=str(tmp_path),
        cli_tool="opencode",
        started_at=now - timedelta(minutes=5),
        last_heartbeat=now - timedelta(minutes=5),
        timeout_secs=1800,
    )
    session.add(run)
    session.flush()

    mock_config = MagicMock()
    mock_config.stall_threshold = 60

    monkeypatch.chdir(tmp_path)

    # Track _emit_event calls to verify the DaemonEvent was emitted correctly
    emit_events: list = []

    def tracking_emit(
        db: object,
        project_id: str,
        event_type: str,
        entity_id: str | None,
        entity_type: str | None = None,
        message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        emit_events.append(
            {
                "event_type": event_type,
                "entity_id": entity_id,
                "message": message,
                "metadata": metadata,
            }
        )

    # mock_step simulates the WorkflowStep row returned by db.get(WorkflowStep, run.step_id).
    # step_type must be set to a review type so the guard passes; step_id and work_item_id
    # are used for the glob pattern and the emitted event.
    mock_step = MagicMock()
    mock_step.id = step.id
    mock_step.step_id = "S02"
    mock_step.work_item_id = item.id
    mock_step.step_type = StepType.code_review

    mock_db = MagicMock()
    mock_db.get.return_value = mock_step
    mock_db.flush.return_value = None

    with (
        patch("orch.daemon.step_monitor._is_pid_alive", return_value=False),
        patch("orch.daemon.step_monitor._probe_for_child", return_value=False),
        patch("orch.daemon.step_monitor._emit_event", side_effect=tracking_emit),
    ):
        sm._check_step_health(mock_db, run, project_id=project.id, config=mock_config)

    # Semantic: exactly one recovery event emitted with the correct verdict
    assert len(emit_events) == 1, f"Expected exactly 1 _emit_event call, got {len(emit_events)}."
    assert emit_events[0]["event_type"] == "step_run_recovered_from_report", (
        f"Event type should be 'step_run_recovered_from_report', "
        f"got {emit_events[0]['event_type']!r}"
    )
    assert emit_events[0]["entity_id"] == "I-00116-E4", (
        f"Entity ID should be 'I-00116-E4', got {emit_events[0]['entity_id']!r}"
    )
    meta = emit_events[0]["metadata"] or {}
    assert meta.get("verdict") == "pass", (
        f"Event metadata verdict should be 'pass', got {meta.get('verdict')!r}"
    )
    assert meta.get("step_id") == "S02", (
        f"Event metadata step_id should be 'S02', got {meta.get('step_id')!r}"
    )

    # Semantic: run status is completed (verdict=pass)
    assert run.status == RunStatus.completed, (
        f"StepRun should be completed after recovery, got {run.status}"
    )
