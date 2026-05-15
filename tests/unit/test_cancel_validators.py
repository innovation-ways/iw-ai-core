"""Pure validator tests for batch/item cancellation transitions.

These exercise the rules without a DB so a regression in the allowed-from
sets is caught at unit-test speed.
"""

from __future__ import annotations

import pytest

from orch.cancel import (
    CANCELLABLE_BATCH_STATUSES,
    CANCELLABLE_WORK_ITEM_STATUSES,
    validate_batch_cancel_transition,
    validate_item_cancel_transition,
)
from orch.db.models import BatchStatus, WorkItemStatus

# ---------------------------------------------------------------------------
# Batch cancel
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [
        BatchStatus.planning,
        BatchStatus.approved,
        BatchStatus.executing,
        BatchStatus.paused,
        BatchStatus.blocked,
        BatchStatus.publish_failed,
    ],
)
def test_batch_cancel_allowed_from_pre_terminal(status: BatchStatus) -> None:
    """Any pre-terminal status must accept a cancel."""
    assert validate_batch_cancel_transition(status) is None


@pytest.mark.parametrize(
    "status",
    [
        BatchStatus.completed,
        BatchStatus.completed_with_errors,
        BatchStatus.publishing,
        BatchStatus.published,
        BatchStatus.archived,
        BatchStatus.cancelled,
    ],
)
def test_batch_cancel_rejected_from_terminal(status: BatchStatus) -> None:
    """Terminal / published / publishing / archived states refuse re-cancellation."""
    error = validate_batch_cancel_transition(status)
    # Lock the *exact* operator-facing message — any drift (capitalisation,
    # quoting, wording) is a public-contract change that should fail the test.
    assert error == f"Cannot cancel batch: current status is '{status.value}'"


def test_batch_cancel_set_matches_published_doc() -> None:
    """Allowed set is exactly the documented pre-terminal statuses.

    Locks the public contract: tests fail if someone silently expands or
    shrinks the cancellable surface without updating both the constant and
    these tests.
    """
    assert (
        frozenset(
            {
                BatchStatus.planning,
                BatchStatus.approved,
                BatchStatus.executing,
                BatchStatus.paused,
                BatchStatus.blocked,
                BatchStatus.publish_failed,
            }
        )
        == CANCELLABLE_BATCH_STATUSES
    )


# ---------------------------------------------------------------------------
# Work item cancel
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [
        WorkItemStatus.approved,
        WorkItemStatus.in_progress,
        WorkItemStatus.failed,
        WorkItemStatus.paused,
    ],
)
def test_item_cancel_allowed_from_post_draft(status: WorkItemStatus) -> None:
    assert validate_item_cancel_transition(status, active_batch_id=None) is None


@pytest.mark.parametrize(
    "status",
    [WorkItemStatus.draft, WorkItemStatus.completed, WorkItemStatus.cancelled],
)
def test_item_cancel_rejected_from_non_cancellable(status: WorkItemStatus) -> None:
    error = validate_item_cancel_transition(status, active_batch_id=None)
    # Lock the full error message — both the prefix and the quoted status.
    assert error == f"Cannot cancel work item: current status is '{status.value}'"


def test_item_cancel_rejected_when_in_active_batch() -> None:
    """The hint must name the batch and tell the operator to use batch-cancel."""
    error = validate_item_cancel_transition(
        WorkItemStatus.in_progress,
        active_batch_id="BATCH-00099",
    )
    # Lock the full operator-facing message — the batch ID appears twice
    # (once in the diagnosis, once in the suggested command), and the
    # "Use 'iw batch-cancel ...' instead." hint is part of the CLI contract.
    assert error == (
        "Cannot cancel work item: belongs to active batch BATCH-00099. "
        "Use 'iw batch-cancel BATCH-00099' instead."
    )


def test_item_cancel_status_check_runs_before_batch_check() -> None:
    """Status validation precedes batch-membership validation.

    A 'draft' item in an active batch should still report the status
    error first — the batch-membership rule exists only to protect a
    valid cancel from leaving the batch inconsistent.
    """
    error = validate_item_cancel_transition(WorkItemStatus.draft, active_batch_id="BATCH-00099")
    assert error is not None
    # The wording differs between the two errors; the status one mentions
    # the current_status value, the batch one mentions the batch ID.
    assert "draft" in error
    assert "BATCH-00099" not in error


def test_item_cancel_set_matches_published_doc() -> None:
    assert (
        frozenset(
            {
                WorkItemStatus.approved,
                WorkItemStatus.in_progress,
                WorkItemStatus.failed,
                WorkItemStatus.paused,
            }
        )
        == CANCELLABLE_WORK_ITEM_STATUSES
    )
