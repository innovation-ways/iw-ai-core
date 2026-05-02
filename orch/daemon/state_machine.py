"""State machine transition validation for all IW AI Core entity types.

Each entity type has a transition table mapping every valid "from" state to the
set of valid "to" states. Use the can_transition_* functions for boolean checks
and validate_* functions when you want an exception on invalid transitions.
"""

from __future__ import annotations

from orch.db.models import (
    BatchItemStatus,
    BatchStatus,
    RunStatus,
    StepStatus,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)


class InvalidTransition(Exception):  # noqa: N818
    """Raised when an invalid state transition is attempted."""


# ---------------------------------------------------------------------------
# Transition tables — {from_state: frozenset of valid to_states}
# ---------------------------------------------------------------------------

_WORK_ITEM_STATUS: dict[WorkItemStatus, frozenset[WorkItemStatus]] = {
    WorkItemStatus.draft: frozenset({WorkItemStatus.approved}),
    WorkItemStatus.approved: frozenset({WorkItemStatus.draft, WorkItemStatus.in_progress}),
    WorkItemStatus.in_progress: frozenset(
        {WorkItemStatus.completed, WorkItemStatus.failed, WorkItemStatus.paused}
    ),
    WorkItemStatus.paused: frozenset({WorkItemStatus.in_progress}),
    WorkItemStatus.failed: frozenset({WorkItemStatus.in_progress}),
    WorkItemStatus.completed: frozenset(),
}

_RESEARCH_WORK_ITEM_STATUS: dict[WorkItemStatus, frozenset[WorkItemStatus]] = {
    WorkItemStatus.draft: frozenset({WorkItemStatus.completed}),
    WorkItemStatus.completed: frozenset(),
}

_WORK_ITEM_PHASE: dict[WorkItemPhase, frozenset[WorkItemPhase]] = {
    WorkItemPhase.active: frozenset({WorkItemPhase.work}),
    WorkItemPhase.work: frozenset({WorkItemPhase.done}),
    WorkItemPhase.done: frozenset(),
}

_STEP_STATUS: dict[StepStatus, frozenset[StepStatus]] = {
    StepStatus.pending: frozenset({StepStatus.in_progress, StepStatus.skipped}),
    StepStatus.in_progress: frozenset(
        {StepStatus.completed, StepStatus.failed, StepStatus.needs_fix}
    ),
    StepStatus.needs_fix: frozenset({StepStatus.in_progress, StepStatus.failed}),
    StepStatus.failed: frozenset({StepStatus.pending, StepStatus.skipped}),
    StepStatus.completed: frozenset(),
    StepStatus.skipped: frozenset(),
}

_RUN_STATUS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.pending: frozenset({RunStatus.running}),
    RunStatus.running: frozenset(
        {
            RunStatus.completed,
            RunStatus.failed,
            RunStatus.timeout,
            RunStatus.killed,
            RunStatus.stalled,
        }
    ),
    RunStatus.completed: frozenset(),
    RunStatus.failed: frozenset(),
    RunStatus.timeout: frozenset(),
    RunStatus.killed: frozenset(),
    RunStatus.stalled: frozenset(),
}

# "Any terminal → archived" from the schema doc means all non-archived states
# can transition to archived when a user explicitly archives a batch.
_BATCH_STATUS: dict[BatchStatus, frozenset[BatchStatus]] = {
    BatchStatus.planning: frozenset({BatchStatus.approved, BatchStatus.archived}),
    BatchStatus.approved: frozenset({BatchStatus.executing, BatchStatus.archived}),
    BatchStatus.executing: frozenset(
        {BatchStatus.paused, BatchStatus.completed, BatchStatus.completed_with_errors}
    ),
    BatchStatus.paused: frozenset({BatchStatus.executing, BatchStatus.archived}),
    BatchStatus.completed: frozenset({BatchStatus.publishing, BatchStatus.archived}),
    BatchStatus.completed_with_errors: frozenset({BatchStatus.archived}),
    BatchStatus.publishing: frozenset({BatchStatus.published, BatchStatus.publish_failed}),
    BatchStatus.published: frozenset({BatchStatus.archived}),
    BatchStatus.publish_failed: frozenset({BatchStatus.archived}),
    BatchStatus.blocked: frozenset({BatchStatus.archived}),
    BatchStatus.archived: frozenset(),
}

_BATCH_ITEM_STATUS: dict[BatchItemStatus, frozenset[BatchItemStatus]] = {
    BatchItemStatus.pending: frozenset({BatchItemStatus.setting_up}),
    BatchItemStatus.setting_up: frozenset({BatchItemStatus.executing, BatchItemStatus.failed}),
    BatchItemStatus.executing: frozenset(
        {BatchItemStatus.completed, BatchItemStatus.failed, BatchItemStatus.stalled}
    ),
    BatchItemStatus.completed: frozenset({BatchItemStatus.merged}),
    BatchItemStatus.merging: frozenset(
        {
            BatchItemStatus.merged,
            BatchItemStatus.failed,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rolled_back,
        }
    ),
    BatchItemStatus.failed: frozenset({BatchItemStatus.pending}),
    BatchItemStatus.stalled: frozenset({BatchItemStatus.pending}),
    BatchItemStatus.merged: frozenset(),
    BatchItemStatus.skipped: frozenset(),
    BatchItemStatus.migration_invalid: frozenset(),
    BatchItemStatus.migration_rolled_back: frozenset(),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _can(table: dict[object, frozenset[object]], from_s: object, to_s: object) -> bool:
    return to_s in table.get(from_s, frozenset())


def _validate(
    entity: str, table: dict[object, frozenset[object]], from_s: object, to_s: object
) -> None:
    if not _can(table, from_s, to_s):
        raise InvalidTransition(f"Invalid {entity} transition: {from_s!r} \u2192 {to_s!r}")


# ---------------------------------------------------------------------------
# Public API — one can_transition_* / validate_* pair per entity type
# ---------------------------------------------------------------------------


def can_transition_work_item_status(
    from_s: WorkItemStatus, to_s: WorkItemStatus, item_type: WorkItemType | None = None
) -> bool:
    """Return True if the work item status transition is valid."""
    table = _RESEARCH_WORK_ITEM_STATUS if item_type == WorkItemType.Research else _WORK_ITEM_STATUS
    return _can(table, from_s, to_s)  # type: ignore[arg-type]


def validate_work_item_status(
    from_s: WorkItemStatus, to_s: WorkItemStatus, item_type: WorkItemType | None = None
) -> None:
    """Raise InvalidTransition if the work item status transition is invalid."""
    table = _RESEARCH_WORK_ITEM_STATUS if item_type == WorkItemType.Research else _WORK_ITEM_STATUS
    _validate("WorkItemStatus", table, from_s, to_s)  # type: ignore[arg-type]


def can_transition_work_item_phase(from_s: WorkItemPhase, to_s: WorkItemPhase) -> bool:
    """Return True if the work item phase transition is valid."""
    return _can(_WORK_ITEM_PHASE, from_s, to_s)  # type: ignore[arg-type]


def validate_work_item_phase(from_s: WorkItemPhase, to_s: WorkItemPhase) -> None:
    """Raise InvalidTransition if the work item phase transition is invalid."""
    _validate("WorkItemPhase", _WORK_ITEM_PHASE, from_s, to_s)  # type: ignore[arg-type]


def can_transition_step_status(from_s: StepStatus, to_s: StepStatus) -> bool:
    """Return True if the step status transition is valid."""
    return _can(_STEP_STATUS, from_s, to_s)  # type: ignore[arg-type]


def validate_step_status(from_s: StepStatus, to_s: StepStatus) -> None:
    """Raise InvalidTransition if the step status transition is invalid."""
    _validate("StepStatus", _STEP_STATUS, from_s, to_s)  # type: ignore[arg-type]


def can_transition_run_status(from_s: RunStatus, to_s: RunStatus) -> bool:
    """Return True if the step run status transition is valid."""
    return _can(_RUN_STATUS, from_s, to_s)  # type: ignore[arg-type]


def validate_run_status(from_s: RunStatus, to_s: RunStatus) -> None:
    """Raise InvalidTransition if the step run status transition is invalid."""
    _validate("RunStatus", _RUN_STATUS, from_s, to_s)  # type: ignore[arg-type]


def can_transition_batch_status(from_s: BatchStatus, to_s: BatchStatus) -> bool:
    """Return True if the batch status transition is valid."""
    return _can(_BATCH_STATUS, from_s, to_s)  # type: ignore[arg-type]


def validate_batch_status(from_s: BatchStatus, to_s: BatchStatus) -> None:
    """Raise InvalidTransition if the batch status transition is invalid."""
    _validate("BatchStatus", _BATCH_STATUS, from_s, to_s)  # type: ignore[arg-type]


def can_transition_batch_item_status(from_s: BatchItemStatus, to_s: BatchItemStatus) -> bool:
    """Return True if the batch item status transition is valid."""
    return _can(_BATCH_ITEM_STATUS, from_s, to_s)  # type: ignore[arg-type]


def validate_batch_item_status(from_s: BatchItemStatus, to_s: BatchItemStatus) -> None:
    """Raise InvalidTransition if the batch item status transition is invalid."""
    _validate("BatchItemStatus", _BATCH_ITEM_STATUS, from_s, to_s)  # type: ignore[arg-type]
