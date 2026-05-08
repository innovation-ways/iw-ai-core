"""Integration tests for fix-cycle cascade replay (Change 1 & Change 2).

Change 1: cascade-reset upstream QV gates when a fix cycle completes.
Change 2: re-invoke layer-specific code-review steps for files the fix
          patch touched.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from orch.config import DaemonConfig
from orch.daemon.fix_cycle import (
    _complete_fix_cycle,
    _reset_review_steps_for_agents,
    check_active_fix_cycles,
)
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    DaemonEvent,
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

# ---------------------------------------------------------------------------
# Helpers (mirror the patterns from test_fix_cycle.py)
# ---------------------------------------------------------------------------


def _project_config() -> ProjectConfig:
    return ProjectConfig(
        id="test-proj",
        display_name="Test",
        repo_root="/repos/test",
        enabled=True,
        cli_tool="claude",
        worktree_base="/repos/test/.worktrees",
        config={"fix_cycle_max": 5},
    )


def _daemon_config() -> DaemonConfig:
    return DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5433/test",
        dashboard_host="0.0.0.0",  # noqa: S104
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=600,
        pid_file="/tmp/test-daemon.pid",  # noqa: S108
        archive_dir="/tmp/test-archive",  # noqa: S108
        archive_ttl=90,
        log_level="DEBUG",
        log_file="/tmp/test-daemon.log",  # noqa: S108
    )


def _make_item(db: Any, item_id: str = "CR-00001") -> WorkItem:
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.ChangeRequest,
        title="Test item",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db.add(item)
    db.flush()
    return item


def _make_step(
    db: Any,
    step_id: str,
    step_type: StepType,
    status: StepStatus,
    step_number: int | None = None,
    prompt_file: str | None = None,
    item_id: str = "CR-00001",
) -> WorkflowStep:
    if step_number is None:
        # Derive a step number from the step_id string (e.g. "S04" → 4)
        try:
            step_number = int(step_id.lstrip("S").lstrip("0") or "0")
        except ValueError:
            step_number = 0
    step = WorkflowStep(
        project_id="test-proj",
        work_item_id=item_id,
        step_number=step_number,
        step_id=step_id,
        agent_label=step_type.value,
        step_type=step_type,
        status=status,
        prompt_file=prompt_file,
    )
    db.add(step)
    db.flush()
    return step


def _make_fix_cycle(
    db: Any,
    step: WorkflowStep,
    cycle_number: int = 1,
    status: FixStatus = FixStatus.in_progress,
    fix_metadata: dict[str, Any] | None = None,
) -> FixCycle:
    fc = FixCycle(
        step_id=step.id,
        cycle_number=cycle_number,
        trigger_type=FixTrigger.browser_verification,
        status=status,
        fix_metadata=fix_metadata or {"pid": 99999, "timeout_secs": 2700},
    )
    db.add(fc)
    db.flush()
    return fc


def _cascade_event(db: Any) -> DaemonEvent | None:
    return (
        db.query(DaemonEvent)
        .filter_by(project_id="test-proj", event_type="cascaded_replay_after_fix")
        .first()
    )


def _review_replay_event(db: Any) -> DaemonEvent | None:
    return (
        db.query(DaemonEvent)
        .filter_by(project_id="test-proj", event_type="review_replay_after_fix")
        .first()
    )


# ---------------------------------------------------------------------------
# Change 1 — cascade-reset upstream QV gates
# ---------------------------------------------------------------------------


def test_browser_fix_completion_resets_all_upstream_qv_gates(
    db_session: Any,
    test_project: Project,
) -> None:
    """An S17 (browser_verification) fix resets completed upstream QV gates
    (S12, S15) but NOT code_review steps (S04)."""
    _make_item(db_session)

    s04 = _make_step(db_session, "S04", StepType.code_review, StepStatus.completed, step_number=4)
    s12 = _make_step(
        db_session, "S12", StepType.quality_validation, StepStatus.completed, step_number=12
    )
    s15 = _make_step(
        db_session, "S15", StepType.quality_validation, StepStatus.completed, step_number=15
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )
    fc = _make_fix_cycle(db_session, s17)

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    db_session.refresh(s04)
    db_session.refresh(s12)
    db_session.refresh(s15)
    db_session.refresh(s17)

    # S04 (code_review) stays completed — not a QV gate
    assert s04.status == StepStatus.completed

    # S12 and S15 reset to pending
    assert s12.status == StepStatus.pending
    assert s12.started_at is None
    assert s12.completed_at is None

    assert s15.status == StepStatus.pending
    assert s15.started_at is None
    assert s15.completed_at is None

    # S17 (the failing step) reset to pending by _complete_fix_cycle
    assert s17.status == StepStatus.pending

    # Daemon event emitted
    event = _cascade_event(db_session)
    assert event is not None
    assert "S12" in event.event_metadata["reset_step_ids"]
    assert "S15" in event.event_metadata["reset_step_ids"]
    assert event.event_metadata["trigger_step_id"] == "S17"
    assert event.event_metadata["reason"] == "code_changed_by_fix_cycle"


def test_unit_test_gate_fix_resets_only_lint_format_typecheck(
    db_session: Any,
    test_project: Project,
) -> None:
    """An S15 (qv_gate/unit-tests) fix resets S12, S13, S14 but NOT S16/S17."""
    _make_item(db_session)

    s12 = _make_step(
        db_session, "S12", StepType.quality_validation, StepStatus.completed, step_number=12
    )
    s13 = _make_step(
        db_session, "S13", StepType.quality_validation, StepStatus.completed, step_number=13
    )
    s14 = _make_step(
        db_session, "S14", StepType.quality_validation, StepStatus.completed, step_number=14
    )
    s15 = _make_step(
        db_session, "S15", StepType.quality_validation, StepStatus.needs_fix, step_number=15
    )
    s16 = _make_step(
        db_session, "S16", StepType.quality_validation, StepStatus.completed, step_number=16
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.pending, step_number=17
    )
    fc = _make_fix_cycle(db_session, s15, fix_metadata={"pid": 99999, "timeout_secs": 2700})

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    db_session.refresh(s12)
    db_session.refresh(s13)
    db_session.refresh(s14)
    db_session.refresh(s15)
    db_session.refresh(s16)
    db_session.refresh(s17)

    # Upstream gates reset
    assert s12.status == StepStatus.pending
    assert s13.status == StepStatus.pending
    assert s14.status == StepStatus.pending

    # Downstream gates untouched
    assert s16.status == StepStatus.completed
    assert s17.status == StepStatus.pending  # was already pending

    # Cascade event mentions S12, S13, S14 only
    event = _cascade_event(db_session)
    assert event is not None
    reset_ids = event.event_metadata["reset_step_ids"]
    assert "S12" in reset_ids
    assert "S13" in reset_ids
    assert "S14" in reset_ids
    assert "S16" not in reset_ids
    assert "S17" not in reset_ids


def test_non_qv_review_fix_does_not_cascade(
    db_session: Any,
    test_project: Project,
) -> None:
    """Failing step is S04 (code_review). No QV cascade fires even if there
    were earlier QV gates (unusual, but the guard must hold)."""
    _make_item(db_session)

    # Hypothetically early QV gate — should NOT be touched
    early_qv = _make_step(
        db_session, "S02", StepType.quality_validation, StepStatus.completed, step_number=2
    )
    s04 = _make_step(db_session, "S04", StepType.code_review, StepStatus.needs_fix, step_number=4)
    fc = _make_fix_cycle(db_session, s04, fix_metadata={"pid": 99999, "timeout_secs": 2700})
    fc.trigger_type = FixTrigger.code_review
    db_session.flush()

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    db_session.refresh(early_qv)

    # Early QV gate untouched — no cascade for code_review failing step
    assert early_qv.status == StepStatus.completed

    # No cascade event emitted
    event = _cascade_event(db_session)
    assert event is None


def test_cascade_skips_steps_already_pending_or_in_progress(
    db_session: Any,
    test_project: Project,
) -> None:
    """QV gates that are already pending or in_progress are left alone."""
    _make_item(db_session)

    s12_pending = _make_step(
        db_session, "S12", StepType.quality_validation, StepStatus.pending, step_number=12
    )
    s13_in_progress = _make_step(
        db_session, "S13", StepType.quality_validation, StepStatus.in_progress, step_number=13
    )
    s14_completed = _make_step(
        db_session, "S14", StepType.quality_validation, StepStatus.completed, step_number=14
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )
    fc = _make_fix_cycle(db_session, s17)

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    db_session.refresh(s12_pending)
    db_session.refresh(s13_in_progress)
    db_session.refresh(s14_completed)

    # Only the completed gate got reset
    assert s12_pending.status == StepStatus.pending  # unchanged
    assert s13_in_progress.status == StepStatus.in_progress  # unchanged
    assert s14_completed.status == StepStatus.pending  # reset

    # Event should list only S14
    event = _cascade_event(db_session)
    assert event is not None
    assert event.event_metadata["reset_step_ids"] == ["S14"]


def test_cascade_skips_steps_in_needs_fix_state(
    db_session: Any,
    test_project: Project,
) -> None:
    """A QV gate already in needs_fix state (its own fix cycle running)
    is left alone by the cascade."""
    _make_item(db_session)

    s12_needs_fix = _make_step(
        db_session, "S12", StepType.quality_validation, StepStatus.needs_fix, step_number=12
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )
    fc = _make_fix_cycle(db_session, s17)

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    db_session.refresh(s12_needs_fix)

    # S12 was needs_fix — cascade does not touch it
    assert s12_needs_fix.status == StepStatus.needs_fix

    # No cascade event (nothing was reset)
    event = _cascade_event(db_session)
    assert event is None


@patch("orch.daemon.fix_cycle._kill_pid")
@patch("orch.daemon.fix_cycle._is_pid_alive", return_value=True)
def test_failed_fix_cycle_does_not_cascade(
    mock_alive: Any,
    mock_kill: Any,
    db_session: Any,
    test_project: Project,
) -> None:
    """_fail_fix_cycle path (timeout) does not trigger any cascade.
    Earlier QV gates stay completed."""
    from datetime import timedelta

    _make_item(db_session)

    s12 = _make_step(
        db_session, "S12", StepType.quality_validation, StepStatus.completed, step_number=12
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )

    fc = FixCycle(
        step_id=s17.id,
        cycle_number=1,
        trigger_type=FixTrigger.browser_verification,
        status=FixStatus.in_progress,
        started_at=datetime.now(UTC) - timedelta(seconds=3000),
        fix_metadata={"pid": 99999, "timeout_secs": 2700},
    )
    db_session.add(fc)
    db_session.flush()

    # This triggers _fail_fix_cycle via timeout path
    check_active_fix_cycles(db_session, "test-proj", _project_config(), _daemon_config())

    db_session.refresh(s12)
    db_session.refresh(s17)

    # S12 still completed — no cascade on failure
    assert s12.status == StepStatus.completed

    # S17 was transitioned to failed by _fail_fix_cycle
    assert s17.status == StepStatus.failed

    # No cascade event
    event = _cascade_event(db_session)
    assert event is None


def test_spec_mismatch_escalation_does_not_cascade(
    db_session: Any,
    test_project: Project,
) -> None:
    """SPEC_MISMATCH failures do not go through fix-cycle creation at all.
    handle_spec_mismatch_escalation emits a different event type and leaves
    the step failed — no cascade fires."""
    from orch.daemon.fix_cycle import handle_spec_mismatch_escalation

    _make_item(db_session)

    s12 = _make_step(
        db_session, "S12", StepType.quality_validation, StepStatus.completed, step_number=12
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.failed, step_number=17
    )

    handle_spec_mismatch_escalation(
        db_session,
        s17,
        "test-proj",
        "SPEC_MISMATCH: the design doc excludes this flow",
    )

    db_session.refresh(s12)
    db_session.refresh(s17)

    # S12 untouched, S17 stays failed, no cascade event
    assert s12.status == StepStatus.completed
    assert s17.status == StepStatus.failed
    event = _cascade_event(db_session)
    assert event is None

    # The spec_mismatch_escalation event was emitted instead
    escalation_event = (
        db_session.query(DaemonEvent)
        .filter_by(project_id="test-proj", event_type="spec_mismatch_escalation")
        .first()
    )
    assert escalation_event is not None


def test_cascade_emits_single_daemon_event_with_step_list(
    db_session: Any,
    test_project: Project,
) -> None:
    """Exactly one cascaded_replay_after_fix event per cascade, with the
    correct reset_step_ids array."""
    _make_item(db_session)

    _make_step(db_session, "S12", StepType.quality_validation, StepStatus.completed, step_number=12)
    _make_step(db_session, "S14", StepType.quality_validation, StepStatus.completed, step_number=14)
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )
    fc = _make_fix_cycle(db_session, s17)

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    events = (
        db_session.query(DaemonEvent)
        .filter_by(project_id="test-proj", event_type="cascaded_replay_after_fix")
        .all()
    )
    assert len(events) == 1

    payload = events[0].event_metadata
    assert set(payload["reset_step_ids"]) == {"S12", "S14"}
    assert payload["trigger_step_id"] == "S17"
    assert payload["reason"] == "code_changed_by_fix_cycle"
    assert payload["cycle_id"] == fc.id


# ---------------------------------------------------------------------------
# Change 2 — re-invoke layer-specific code reviews
# ---------------------------------------------------------------------------


@patch("orch.daemon.fix_cycle._files_changed_by_fix_cycle")
def test_fix_changing_frontend_file_resets_frontend_review(
    mock_files: Any,
    db_session: Any,
    test_project: Project,
    tmp_path: Path,
) -> None:
    """Fix touches dashboard/templates/foo.html → S08 (frontend code-review) reset."""
    mock_files.return_value = ["dashboard/templates/foo.html"]
    _make_item(db_session)

    # S08: frontend code-review, completed, with prompt filename matching the convention
    s08 = _make_step(
        db_session,
        "S08",
        StepType.code_review,
        StepStatus.completed,
        step_number=8,
        prompt_file="prompts/CR-00001_S08_CodeReview_Frontend_prompt.md",
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )

    # Set up the review-mapping.toml in tmp_path
    config_dir = tmp_path / "ai-dev" / "iw-config"
    config_dir.mkdir(parents=True)
    (config_dir / "review-mapping.toml").write_text(
        '[[mapping]]\nreview_agent = "frontend-review"\nglob = ["dashboard/templates/**"]\n'
    )

    fc = _make_fix_cycle(
        db_session,
        s17,
        fix_metadata={"pid": 99999, "timeout_secs": 2700, "worktree_path": str(tmp_path)},
    )

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    db_session.refresh(s08)
    assert s08.status == StepStatus.pending
    assert s08.started_at is None

    event = _review_replay_event(db_session)
    assert event is not None
    assert "S08" in event.event_metadata["reset_step_ids"]


@patch("orch.daemon.fix_cycle._files_changed_by_fix_cycle")
def test_fix_changing_api_file_resets_api_review(
    mock_files: Any,
    db_session: Any,
    test_project: Project,
    tmp_path: Path,
) -> None:
    """Fix touches dashboard/routers/actions.py → S06 (api code-review) reset."""
    mock_files.return_value = ["dashboard/routers/actions.py"]
    _make_item(db_session)

    s06 = _make_step(
        db_session,
        "S06",
        StepType.code_review,
        StepStatus.completed,
        step_number=6,
        prompt_file="prompts/CR-00001_S06_CodeReview_API_prompt.md",
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )

    config_dir = tmp_path / "ai-dev" / "iw-config"
    config_dir.mkdir(parents=True)
    (config_dir / "review-mapping.toml").write_text(
        '[[mapping]]\nreview_agent = "api-review"\nglob = ["dashboard/routers/actions.py"]\n'
    )

    fc = _make_fix_cycle(
        db_session,
        s17,
        fix_metadata={"pid": 99999, "timeout_secs": 2700, "worktree_path": str(tmp_path)},
    )

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    db_session.refresh(s06)
    assert s06.status == StepStatus.pending

    event = _review_replay_event(db_session)
    assert event is not None
    assert "S06" in event.event_metadata["reset_step_ids"]


@patch("orch.daemon.fix_cycle._files_changed_by_fix_cycle")
def test_fix_changing_files_in_two_layers_resets_both_reviews(
    mock_files: Any,
    db_session: Any,
    test_project: Project,
    tmp_path: Path,
) -> None:
    """Fix touches both api and frontend files → S06 AND S08 reset."""
    mock_files.return_value = [
        "dashboard/routers/actions.py",
        "dashboard/templates/components/action_button.html",
    ]
    _make_item(db_session)

    s06 = _make_step(
        db_session,
        "S06",
        StepType.code_review,
        StepStatus.completed,
        step_number=6,
        prompt_file="prompts/CR-00001_S06_CodeReview_API_prompt.md",
    )
    s08 = _make_step(
        db_session,
        "S08",
        StepType.code_review,
        StepStatus.completed,
        step_number=8,
        prompt_file="prompts/CR-00001_S08_CodeReview_Frontend_prompt.md",
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )

    config_dir = tmp_path / "ai-dev" / "iw-config"
    config_dir.mkdir(parents=True)
    (config_dir / "review-mapping.toml").write_text(
        '[[mapping]]\nreview_agent = "api-review"\nglob = ["dashboard/routers/actions.py"]\n'
        "\n"
        '[[mapping]]\nreview_agent = "frontend-review"\nglob = ["dashboard/templates/**"]\n'
    )

    fc = _make_fix_cycle(
        db_session,
        s17,
        fix_metadata={"pid": 99999, "timeout_secs": 2700, "worktree_path": str(tmp_path)},
    )

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    db_session.refresh(s06)
    db_session.refresh(s08)
    assert s06.status == StepStatus.pending
    assert s08.status == StepStatus.pending

    event = _review_replay_event(db_session)
    assert event is not None
    assert set(event.event_metadata["reset_step_ids"]) == {"S06", "S08"}


@patch("orch.daemon.fix_cycle._files_changed_by_fix_cycle")
def test_fix_with_no_changed_files_resets_no_reviews(
    mock_files: Any,
    db_session: Any,
    test_project: Project,
    tmp_path: Path,
) -> None:
    """Empty diff → no review steps reset, no review_replay_after_fix event."""
    mock_files.return_value = []
    _make_item(db_session)

    s08 = _make_step(
        db_session,
        "S08",
        StepType.code_review,
        StepStatus.completed,
        step_number=8,
        prompt_file="prompts/CR-00001_S08_CodeReview_Frontend_prompt.md",
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )

    config_dir = tmp_path / "ai-dev" / "iw-config"
    config_dir.mkdir(parents=True)
    (config_dir / "review-mapping.toml").write_text(
        '[[mapping]]\nreview_agent = "frontend-review"\nglob = ["dashboard/templates/**"]\n'
    )

    fc = _make_fix_cycle(
        db_session,
        s17,
        fix_metadata={"pid": 99999, "timeout_secs": 2700, "worktree_path": str(tmp_path)},
    )

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    db_session.refresh(s08)
    # S08 should be untouched by Change 2 (no files changed)
    # (S17's own cascade may not have touched S08 since it's code_review not qv_gate)
    assert s08.status == StepStatus.completed

    event = _review_replay_event(db_session)
    assert event is None


@patch("orch.daemon.fix_cycle._files_changed_by_fix_cycle")
def test_review_mapping_missing_disables_change_2(
    mock_files: Any,
    db_session: Any,
    test_project: Project,
    tmp_path: Path,
) -> None:
    """No review-mapping.toml → Change 1 cascade still fires, but Change 2
    does not (no review_replay_after_fix event)."""
    mock_files.return_value = ["dashboard/templates/foo.html"]
    _make_item(db_session)

    s08 = _make_step(
        db_session,
        "S08",
        StepType.code_review,
        StepStatus.completed,
        step_number=8,
        prompt_file="prompts/CR-00001_S08_CodeReview_Frontend_prompt.md",
    )
    s12 = _make_step(
        db_session, "S12", StepType.quality_validation, StepStatus.completed, step_number=12
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )

    # tmp_path has no ai-dev/iw-config/review-mapping.toml
    fc = _make_fix_cycle(
        db_session,
        s17,
        fix_metadata={"pid": 99999, "timeout_secs": 2700, "worktree_path": str(tmp_path)},
    )

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    # Change 1 cascade still fires: S12 reset
    db_session.refresh(s12)
    assert s12.status == StepStatus.pending
    cascade_event = _cascade_event(db_session)
    assert cascade_event is not None

    # Change 2 does not fire: S08 untouched, no review_replay event
    db_session.refresh(s08)
    assert s08.status == StepStatus.completed
    review_event = _review_replay_event(db_session)
    assert review_event is None


@patch("orch.daemon.fix_cycle._files_changed_by_fix_cycle")
def test_change_2_only_resets_reviews_upstream_of_failing_step(
    mock_files: Any,
    db_session: Any,
    test_project: Project,
    tmp_path: Path,
) -> None:
    """Change 2 only resets code-review steps with step_id < failing step.
    The failing step itself is NOT reset by Change 2 (its own reset already
    handled it). A downstream review step (hypothetically) would also not reset."""
    mock_files.return_value = ["dashboard/templates/foo.html"]
    _make_item(db_session)

    # Upstream frontend review (step_id < S17)
    s08 = _make_step(
        db_session,
        "S08",
        StepType.code_review,
        StepStatus.completed,
        step_number=8,
        prompt_file="prompts/CR-00001_S08_CodeReview_Frontend_prompt.md",
    )
    # The failing step itself
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )
    # A hypothetical downstream review (step_id > S17 — should NOT be touched)
    s20 = _make_step(
        db_session,
        "S20",
        StepType.code_review,
        StepStatus.completed,
        step_number=20,
        prompt_file="prompts/CR-00001_S20_CodeReview_Frontend_prompt.md",
    )

    config_dir = tmp_path / "ai-dev" / "iw-config"
    config_dir.mkdir(parents=True)
    (config_dir / "review-mapping.toml").write_text(
        '[[mapping]]\nreview_agent = "frontend-review"\nglob = ["dashboard/templates/**"]\n'
    )

    fc = _make_fix_cycle(
        db_session,
        s17,
        fix_metadata={"pid": 99999, "timeout_secs": 2700, "worktree_path": str(tmp_path)},
    )

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    db_session.refresh(s08)
    db_session.refresh(s20)

    # Upstream review reset
    assert s08.status == StepStatus.pending

    # Downstream review left alone
    assert s20.status == StepStatus.completed


@patch("orch.daemon.fix_cycle._files_changed_by_fix_cycle")
def test_change_2_does_not_reset_implementation_steps_only_reviews(
    mock_files: Any,
    db_session: Any,
    test_project: Project,
    tmp_path: Path,
) -> None:
    """Even if a fix touches frontend files, implementation steps (S07) are
    NEVER reset by Change 2 — only code_review steps qualify."""
    mock_files.return_value = ["dashboard/templates/foo.html"]
    _make_item(db_session)

    # S07: frontend implementation (NOT code_review)
    s07 = _make_step(
        db_session,
        "S07",
        StepType.implementation,
        StepStatus.completed,
        step_number=7,
    )
    # S08: frontend code-review (eligible)
    s08 = _make_step(
        db_session,
        "S08",
        StepType.code_review,
        StepStatus.completed,
        step_number=8,
        prompt_file="prompts/CR-00001_S08_CodeReview_Frontend_prompt.md",
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )

    config_dir = tmp_path / "ai-dev" / "iw-config"
    config_dir.mkdir(parents=True)
    (config_dir / "review-mapping.toml").write_text(
        '[[mapping]]\nreview_agent = "frontend-review"\nglob = ["dashboard/templates/**"]\n'
    )

    fc = _make_fix_cycle(
        db_session,
        s17,
        fix_metadata={"pid": 99999, "timeout_secs": 2700, "worktree_path": str(tmp_path)},
    )

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    db_session.refresh(s07)
    db_session.refresh(s08)

    # S07 (implementation) — NEVER reset
    assert s07.status == StepStatus.completed

    # S08 (code_review) — reset
    assert s08.status == StepStatus.pending


@patch("orch.daemon.fix_cycle._files_changed_by_fix_cycle")
def test_change_2_skips_review_already_in_needs_fix(
    mock_files: Any,
    db_session: Any,
    test_project: Project,
    tmp_path: Path,
) -> None:
    """If S08 is already in needs_fix, Change 2 leaves it alone (only
    completed steps are eligible for reset)."""
    mock_files.return_value = ["dashboard/templates/foo.html"]
    _make_item(db_session)

    s08 = _make_step(
        db_session,
        "S08",
        StepType.code_review,
        StepStatus.needs_fix,  # already in needs_fix — its own fix cycle running
        step_number=8,
        prompt_file="prompts/CR-00001_S08_CodeReview_Frontend_prompt.md",
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )

    config_dir = tmp_path / "ai-dev" / "iw-config"
    config_dir.mkdir(parents=True)
    (config_dir / "review-mapping.toml").write_text(
        '[[mapping]]\nreview_agent = "frontend-review"\nglob = ["dashboard/templates/**"]\n'
    )

    fc = _make_fix_cycle(
        db_session,
        s17,
        fix_metadata={"pid": 99999, "timeout_secs": 2700, "worktree_path": str(tmp_path)},
    )

    _complete_fix_cycle(db_session, fc, "test-proj", datetime.now(UTC))
    db_session.flush()

    db_session.refresh(s08)
    # S08 was needs_fix → Change 2 leaves it alone
    assert s08.status == StepStatus.needs_fix

    # No review_replay event
    event = _review_replay_event(db_session)
    assert event is None


# ---------------------------------------------------------------------------
# _reset_review_steps_for_agents — direct unit
# ---------------------------------------------------------------------------


def test_reset_review_steps_for_agents_direct(
    db_session: Any,
    test_project: Project,
) -> None:
    """Direct test of _reset_review_steps_for_agents: only completed
    code_review steps with matching layer and upstream step_id are reset."""
    _make_item(db_session)

    s04 = _make_step(
        db_session,
        "S04",
        StepType.code_review,
        StepStatus.completed,
        step_number=4,
        prompt_file="prompts/CR-00001_S04_CodeReview_Backend_prompt.md",
    )
    s06 = _make_step(
        db_session,
        "S06",
        StepType.code_review,
        StepStatus.completed,
        step_number=6,
        prompt_file="prompts/CR-00001_S06_CodeReview_API_prompt.md",
    )
    s17 = _make_step(
        db_session, "S17", StepType.browser_verification, StepStatus.needs_fix, step_number=17
    )

    result = _reset_review_steps_for_agents(db_session, s17, {"backend-review"}, "test-proj")
    db_session.flush()

    db_session.refresh(s04)
    db_session.refresh(s06)

    assert "S04" in result
    assert "S06" not in result  # api-review not in agent_names
    assert s04.status == StepStatus.pending
    assert s06.status == StepStatus.completed  # untouched
