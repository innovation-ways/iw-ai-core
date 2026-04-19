"""Unit tests for the state machine transition validation.

Tests every valid transition (should pass) and a representative set of
invalid transitions (should raise InvalidTransition) for all 6 entity types.
"""

from __future__ import annotations

import pytest

from orch.daemon.state_machine import (
    InvalidTransition,
    can_transition_batch_item_status,
    can_transition_batch_status,
    can_transition_run_status,
    can_transition_step_status,
    can_transition_work_item_phase,
    can_transition_work_item_status,
    validate_batch_item_status,
    validate_batch_status,
    validate_run_status,
    validate_step_status,
    validate_work_item_phase,
    validate_work_item_status,
)
from orch.db.models import (
    BatchItemStatus,
    BatchStatus,
    RunStatus,
    StepStatus,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

# ---------------------------------------------------------------------------
# WorkItemStatus
# ---------------------------------------------------------------------------

_VALID_WORK_ITEM_STATUS = [
    (WorkItemStatus.draft, WorkItemStatus.approved),
    (WorkItemStatus.approved, WorkItemStatus.draft),
    (WorkItemStatus.approved, WorkItemStatus.in_progress),
    (WorkItemStatus.in_progress, WorkItemStatus.completed),
    (WorkItemStatus.in_progress, WorkItemStatus.failed),
    (WorkItemStatus.in_progress, WorkItemStatus.paused),
    (WorkItemStatus.paused, WorkItemStatus.in_progress),
    (WorkItemStatus.failed, WorkItemStatus.in_progress),
]

_INVALID_WORK_ITEM_STATUS = [
    # Same-status (never valid)
    (WorkItemStatus.draft, WorkItemStatus.draft),
    (WorkItemStatus.in_progress, WorkItemStatus.in_progress),
    (WorkItemStatus.completed, WorkItemStatus.completed),
    # Skipping steps
    (WorkItemStatus.draft, WorkItemStatus.in_progress),
    (WorkItemStatus.draft, WorkItemStatus.completed),
    (WorkItemStatus.draft, WorkItemStatus.failed),
    # No going back from terminal
    (WorkItemStatus.completed, WorkItemStatus.draft),
    (WorkItemStatus.completed, WorkItemStatus.approved),
    (WorkItemStatus.completed, WorkItemStatus.in_progress),
    # paused can't go to approved/completed directly
    (WorkItemStatus.paused, WorkItemStatus.completed),
    (WorkItemStatus.paused, WorkItemStatus.approved),
]


@pytest.mark.parametrize(("from_s", "to_s"), _VALID_WORK_ITEM_STATUS)
def test_work_item_status_valid(from_s: WorkItemStatus, to_s: WorkItemStatus) -> None:
    assert can_transition_work_item_status(from_s, to_s)
    validate_work_item_status(from_s, to_s)  # no exception


@pytest.mark.parametrize(("from_s", "to_s"), _INVALID_WORK_ITEM_STATUS)
def test_work_item_status_invalid(from_s: WorkItemStatus, to_s: WorkItemStatus) -> None:
    assert not can_transition_work_item_status(from_s, to_s)
    with pytest.raises(InvalidTransition, match="WorkItemStatus"):
        validate_work_item_status(from_s, to_s)


# ---------------------------------------------------------------------------
# WorkItemPhase
# ---------------------------------------------------------------------------

_VALID_WORK_ITEM_PHASE = [
    (WorkItemPhase.active, WorkItemPhase.work),
    (WorkItemPhase.work, WorkItemPhase.done),
]

_INVALID_WORK_ITEM_PHASE = [
    (WorkItemPhase.active, WorkItemPhase.active),
    (WorkItemPhase.active, WorkItemPhase.done),  # skip 'work'
    (WorkItemPhase.work, WorkItemPhase.active),  # no going back
    (WorkItemPhase.done, WorkItemPhase.active),  # terminal
    (WorkItemPhase.done, WorkItemPhase.work),
    (WorkItemPhase.done, WorkItemPhase.done),
]


@pytest.mark.parametrize(("from_s", "to_s"), _VALID_WORK_ITEM_PHASE)
def test_work_item_phase_valid(from_s: WorkItemPhase, to_s: WorkItemPhase) -> None:
    assert can_transition_work_item_phase(from_s, to_s)
    validate_work_item_phase(from_s, to_s)


@pytest.mark.parametrize(("from_s", "to_s"), _INVALID_WORK_ITEM_PHASE)
def test_work_item_phase_invalid(from_s: WorkItemPhase, to_s: WorkItemPhase) -> None:
    assert not can_transition_work_item_phase(from_s, to_s)
    with pytest.raises(InvalidTransition, match="WorkItemPhase"):
        validate_work_item_phase(from_s, to_s)


# ---------------------------------------------------------------------------
# StepStatus
# ---------------------------------------------------------------------------

_VALID_STEP_STATUS = [
    (StepStatus.pending, StepStatus.in_progress),
    (StepStatus.in_progress, StepStatus.completed),
    (StepStatus.in_progress, StepStatus.failed),
    (StepStatus.in_progress, StepStatus.needs_fix),
    (StepStatus.needs_fix, StepStatus.in_progress),
    (StepStatus.needs_fix, StepStatus.failed),
    (StepStatus.failed, StepStatus.pending),
    (StepStatus.failed, StepStatus.skipped),
]

_INVALID_STEP_STATUS = [
    # Same-status
    (StepStatus.pending, StepStatus.pending),
    (StepStatus.in_progress, StepStatus.in_progress),
    (StepStatus.completed, StepStatus.completed),
    # Terminal states can't transition
    (StepStatus.completed, StepStatus.pending),
    (StepStatus.completed, StepStatus.in_progress),
    (StepStatus.completed, StepStatus.failed),
    (StepStatus.skipped, StepStatus.pending),
    (StepStatus.skipped, StepStatus.in_progress),
    # Invalid forward jumps
    (StepStatus.pending, StepStatus.completed),
    (StepStatus.pending, StepStatus.failed),
    (StepStatus.pending, StepStatus.needs_fix),
    (StepStatus.needs_fix, StepStatus.completed),
    (StepStatus.needs_fix, StepStatus.skipped),
]


@pytest.mark.parametrize(("from_s", "to_s"), _VALID_STEP_STATUS)
def test_step_status_valid(from_s: StepStatus, to_s: StepStatus) -> None:
    assert can_transition_step_status(from_s, to_s)
    validate_step_status(from_s, to_s)


@pytest.mark.parametrize(("from_s", "to_s"), _INVALID_STEP_STATUS)
def test_step_status_invalid(from_s: StepStatus, to_s: StepStatus) -> None:
    assert not can_transition_step_status(from_s, to_s)
    with pytest.raises(InvalidTransition, match="StepStatus"):
        validate_step_status(from_s, to_s)


# ---------------------------------------------------------------------------
# RunStatus
# ---------------------------------------------------------------------------

_VALID_RUN_STATUS = [
    (RunStatus.pending, RunStatus.running),
    (RunStatus.running, RunStatus.completed),
    (RunStatus.running, RunStatus.failed),
    (RunStatus.running, RunStatus.timeout),
    (RunStatus.running, RunStatus.killed),
    (RunStatus.running, RunStatus.stalled),
]

_INVALID_RUN_STATUS = [
    # Same-status
    (RunStatus.pending, RunStatus.pending),
    (RunStatus.running, RunStatus.running),
    (RunStatus.completed, RunStatus.completed),
    # Terminal → anything
    (RunStatus.completed, RunStatus.pending),
    (RunStatus.completed, RunStatus.running),
    (RunStatus.failed, RunStatus.running),
    (RunStatus.timeout, RunStatus.running),
    (RunStatus.killed, RunStatus.running),
    (RunStatus.stalled, RunStatus.running),
    # Skipping running
    (RunStatus.pending, RunStatus.completed),
    (RunStatus.pending, RunStatus.failed),
    (RunStatus.pending, RunStatus.timeout),
]


@pytest.mark.parametrize(("from_s", "to_s"), _VALID_RUN_STATUS)
def test_run_status_valid(from_s: RunStatus, to_s: RunStatus) -> None:
    assert can_transition_run_status(from_s, to_s)
    validate_run_status(from_s, to_s)


@pytest.mark.parametrize(("from_s", "to_s"), _INVALID_RUN_STATUS)
def test_run_status_invalid(from_s: RunStatus, to_s: RunStatus) -> None:
    assert not can_transition_run_status(from_s, to_s)
    with pytest.raises(InvalidTransition, match="RunStatus"):
        validate_run_status(from_s, to_s)


# ---------------------------------------------------------------------------
# BatchStatus
# ---------------------------------------------------------------------------

_VALID_BATCH_STATUS = [
    (BatchStatus.planning, BatchStatus.approved),
    (BatchStatus.planning, BatchStatus.archived),
    (BatchStatus.approved, BatchStatus.executing),
    (BatchStatus.approved, BatchStatus.archived),
    (BatchStatus.executing, BatchStatus.paused),
    (BatchStatus.executing, BatchStatus.completed),
    (BatchStatus.executing, BatchStatus.completed_with_errors),
    (BatchStatus.paused, BatchStatus.executing),
    (BatchStatus.paused, BatchStatus.archived),
    (BatchStatus.completed, BatchStatus.publishing),
    (BatchStatus.completed, BatchStatus.archived),
    (BatchStatus.completed_with_errors, BatchStatus.archived),
    (BatchStatus.publishing, BatchStatus.published),
    (BatchStatus.publishing, BatchStatus.publish_failed),
    (BatchStatus.published, BatchStatus.archived),
    (BatchStatus.publish_failed, BatchStatus.archived),
    (BatchStatus.blocked, BatchStatus.archived),
]

_INVALID_BATCH_STATUS = [
    # Same-status
    (BatchStatus.planning, BatchStatus.planning),
    (BatchStatus.executing, BatchStatus.executing),
    (BatchStatus.archived, BatchStatus.archived),
    # Terminal archived → anything
    (BatchStatus.archived, BatchStatus.planning),
    (BatchStatus.archived, BatchStatus.approved),
    # Invalid skips
    (BatchStatus.planning, BatchStatus.executing),
    (BatchStatus.planning, BatchStatus.completed),
    (BatchStatus.approved, BatchStatus.completed),
    (BatchStatus.executing, BatchStatus.published),
    (BatchStatus.completed, BatchStatus.executing),
    (BatchStatus.published, BatchStatus.publishing),
]


@pytest.mark.parametrize(("from_s", "to_s"), _VALID_BATCH_STATUS)
def test_batch_status_valid(from_s: BatchStatus, to_s: BatchStatus) -> None:
    assert can_transition_batch_status(from_s, to_s)
    validate_batch_status(from_s, to_s)


@pytest.mark.parametrize(("from_s", "to_s"), _INVALID_BATCH_STATUS)
def test_batch_status_invalid(from_s: BatchStatus, to_s: BatchStatus) -> None:
    assert not can_transition_batch_status(from_s, to_s)
    with pytest.raises(InvalidTransition, match="BatchStatus"):
        validate_batch_status(from_s, to_s)


# ---------------------------------------------------------------------------
# BatchItemStatus
# ---------------------------------------------------------------------------

_VALID_BATCH_ITEM_STATUS = [
    (BatchItemStatus.pending, BatchItemStatus.setting_up),
    (BatchItemStatus.setting_up, BatchItemStatus.executing),
    (BatchItemStatus.setting_up, BatchItemStatus.failed),
    (BatchItemStatus.executing, BatchItemStatus.completed),
    (BatchItemStatus.executing, BatchItemStatus.failed),
    (BatchItemStatus.executing, BatchItemStatus.stalled),
    (BatchItemStatus.completed, BatchItemStatus.merged),
    (BatchItemStatus.failed, BatchItemStatus.pending),
    (BatchItemStatus.stalled, BatchItemStatus.pending),
]

_INVALID_BATCH_ITEM_STATUS = [
    # Same-status
    (BatchItemStatus.pending, BatchItemStatus.pending),
    (BatchItemStatus.executing, BatchItemStatus.executing),
    (BatchItemStatus.merged, BatchItemStatus.merged),
    # Terminal states
    (BatchItemStatus.merged, BatchItemStatus.pending),
    (BatchItemStatus.merged, BatchItemStatus.executing),
    (BatchItemStatus.skipped, BatchItemStatus.pending),
    (BatchItemStatus.skipped, BatchItemStatus.executing),
    # Invalid skips
    (BatchItemStatus.pending, BatchItemStatus.executing),
    (BatchItemStatus.pending, BatchItemStatus.completed),
    (BatchItemStatus.setting_up, BatchItemStatus.completed),
    (BatchItemStatus.setting_up, BatchItemStatus.merged),
    (BatchItemStatus.executing, BatchItemStatus.merged),  # must complete first
    (BatchItemStatus.completed, BatchItemStatus.pending),
    (BatchItemStatus.completed, BatchItemStatus.executing),
]


@pytest.mark.parametrize(("from_s", "to_s"), _VALID_BATCH_ITEM_STATUS)
def test_batch_item_status_valid(from_s: BatchItemStatus, to_s: BatchItemStatus) -> None:
    assert can_transition_batch_item_status(from_s, to_s)
    validate_batch_item_status(from_s, to_s)


@pytest.mark.parametrize(("from_s", "to_s"), _INVALID_BATCH_ITEM_STATUS)
def test_batch_item_status_invalid(from_s: BatchItemStatus, to_s: BatchItemStatus) -> None:
    assert not can_transition_batch_item_status(from_s, to_s)
    with pytest.raises(InvalidTransition, match="BatchItemStatus"):
        validate_batch_item_status(from_s, to_s)


# ---------------------------------------------------------------------------
# Edge: InvalidTransition message must mention the status values
# ---------------------------------------------------------------------------


def test_invalid_transition_message_includes_values() -> None:
    """The error message should identify both states for easy debugging."""
    with pytest.raises(InvalidTransition) as exc_info:
        validate_work_item_status(WorkItemStatus.completed, WorkItemStatus.draft)
    msg = str(exc_info.value)
    assert "completed" in msg
    assert "draft" in msg


def test_invalid_transition_message_includes_entity_type() -> None:
    """The error message should name the entity type."""
    with pytest.raises(InvalidTransition) as exc_info:
        validate_step_status(StepStatus.completed, StepStatus.pending)
    assert "StepStatus" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Research work-item type-aware transitions (AC7)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("from_s", "to_s", "item_type", "expected"),
    [
        # Research: only draft → completed is valid
        (WorkItemStatus.draft, WorkItemStatus.completed, WorkItemType.Research, True),
        (WorkItemStatus.draft, WorkItemStatus.approved, WorkItemType.Research, False),
        (WorkItemStatus.draft, WorkItemStatus.in_progress, WorkItemType.Research, False),
        (WorkItemStatus.draft, WorkItemStatus.failed, WorkItemType.Research, False),
        (WorkItemStatus.draft, WorkItemStatus.paused, WorkItemType.Research, False),
        (WorkItemStatus.completed, WorkItemStatus.draft, WorkItemType.Research, False),
        (WorkItemStatus.completed, WorkItemStatus.approved, WorkItemType.Research, False),
        (WorkItemStatus.completed, WorkItemStatus.in_progress, WorkItemType.Research, False),
        # Non-research: existing table unchanged
        (WorkItemStatus.draft, WorkItemStatus.approved, WorkItemType.Feature, True),
        (WorkItemStatus.draft, WorkItemStatus.completed, WorkItemType.Feature, False),
        (WorkItemStatus.draft, WorkItemStatus.in_progress, WorkItemType.Feature, False),
        (WorkItemStatus.approved, WorkItemStatus.in_progress, WorkItemType.ChangeRequest, True),
        (WorkItemStatus.approved, WorkItemStatus.draft, WorkItemType.Issue, True),
        (WorkItemStatus.in_progress, WorkItemStatus.completed, WorkItemType.Feature, True),
        # Backward compat: item_type=None routes to the generic table
        (WorkItemStatus.draft, WorkItemStatus.approved, None, True),
        (WorkItemStatus.draft, WorkItemStatus.completed, None, False),
        (WorkItemStatus.draft, WorkItemStatus.in_progress, None, False),
    ],
)
def test_work_item_status_transitions_type_aware(
    from_s: WorkItemStatus, to_s: WorkItemStatus, item_type: WorkItemType | None, expected: bool
) -> None:
    assert can_transition_work_item_status(from_s, to_s, item_type) is expected


@pytest.mark.parametrize(
    ("from_s", "to_s", "item_type", "expected"),
    [
        # True cases — should not raise
        (WorkItemStatus.draft, WorkItemStatus.completed, WorkItemType.Research, True),
        (WorkItemStatus.draft, WorkItemStatus.approved, WorkItemType.Feature, True),
        (WorkItemStatus.approved, WorkItemStatus.in_progress, WorkItemType.ChangeRequest, True),
        (WorkItemStatus.draft, WorkItemStatus.approved, None, True),
        # False cases — should raise InvalidTransition
        (WorkItemStatus.draft, WorkItemStatus.approved, WorkItemType.Research, False),
        (WorkItemStatus.draft, WorkItemStatus.in_progress, WorkItemType.Research, False),
        (WorkItemStatus.completed, WorkItemStatus.draft, WorkItemType.Research, False),
        (WorkItemStatus.draft, WorkItemStatus.completed, WorkItemType.Feature, False),
        (WorkItemStatus.draft, WorkItemStatus.in_progress, None, False),
    ],
)
def test_validate_work_item_status_type_aware(
    from_s: WorkItemStatus, to_s: WorkItemStatus, item_type: WorkItemType | None, expected: bool
) -> None:
    if expected:
        validate_work_item_status(from_s, to_s, item_type)
    else:
        with pytest.raises(InvalidTransition):
            validate_work_item_status(from_s, to_s, item_type)
