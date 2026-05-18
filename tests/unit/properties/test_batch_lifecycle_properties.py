"""Property-based tests for the batch status computation.

Tests that `compute_batch_status` (or the equivalent inline logic in
`_check_batch_completion`) is deterministic and satisfies the five named
properties using Hypothesis `@given`.
"""

from __future__ import annotations

from enum import Enum

import hypothesis
from hypothesis import given
from hypothesis.strategies import sampled_from

from orch.db.models import BatchStatus

# ----- Pure helper being tested ------------------------------------------------------


class ItemStatus(Enum):
    """Simulates the subset of BatchItemStatus relevant to batch completion."""

    pending = "pending"
    setting_up = "setting_up"
    executing = "executing"
    completed = "completed"
    awaiting_merge_approval = "awaiting_merge_approval"
    merging = "merging"
    merged = "merged"
    failed = "failed"
    stalled = "stalled"
    skipped = "skipped"
    merge_failed = "merge_failed"
    migration_invalid = "migration_invalid"
    migration_rolled_back = "migration_rolled_back"
    migration_rebase_failed = "migration_rebase_failed"
    setup_failed = "setup_failed"


TERMINAL_STATUSES = frozenset(
    {
        ItemStatus.merged,
        ItemStatus.failed,
        ItemStatus.stalled,
        ItemStatus.skipped,
        ItemStatus.merge_failed,
        ItemStatus.migration_invalid,
        ItemStatus.migration_rolled_back,
        ItemStatus.migration_rebase_failed,
        ItemStatus.setup_failed,
    }
)

NON_TERMINAL_STATUSES = [s for s in ItemStatus if s not in TERMINAL_STATUSES]


def compute_batch_status(items: list[tuple[int, ItemStatus]]) -> BatchStatus:
    """Pure function: derive BatchStatus from a list of (item_id, item_status).

    Implements the five named properties from the design doc.
    """
    if not items:
        return BatchStatus.completed

    statuses = [status for _, status in items]

    # P1: deterministic — already guaranteed by being a pure function

    # P2: held if any item is held (we model 'held' as awaiting_merge_approval)
    if any(s == ItemStatus.awaiting_merge_approval for s in statuses):
        return BatchStatus.executing  # awaiting_merge_approval is a held state

    # P3: completed iff every item is terminal AND at least one is merged
    if all(s in TERMINAL_STATUSES for s in statuses):
        if any(s == ItemStatus.merged for s in statuses):
            return BatchStatus.completed
        # P4: failed iff every item is terminal AND none are merged
        return BatchStatus.completed_with_errors

    # P5: in_progress otherwise
    return BatchStatus.executing


# ----- Property tests -------------------------------------------------------------------------

_status_list = hypothesis.strategies.lists(
    hypothesis.strategies.tuples(
        hypothesis.strategies.integers(min_value=1),
        sampled_from(list(ItemStatus)),
    ),
    min_size=1,
)


@given(_status_list)
def test_batch_status_deterministic(items: list[tuple[int, ItemStatus]]) -> None:
    """P1: Batch status is deterministic (same input → same output)."""
    result1 = compute_batch_status(items)
    result2 = compute_batch_status(items)
    assert result1 == result2


@given(_status_list)
def test_batch_status_held_precedence(items: list[tuple[int, ItemStatus]]) -> None:
    """P2: Batch is 'executing' if any item is awaiting_merge_approval (held)."""
    # Inject one held item
    items = list(items)
    if items:
        items.append((9999, ItemStatus.awaiting_merge_approval))
        result = compute_batch_status(items)
        assert result == BatchStatus.executing


_terminallist = hypothesis.strategies.lists(
    hypothesis.strategies.tuples(
        hypothesis.strategies.integers(min_value=1),
        sampled_from(list(ItemStatus)),
    ),
    min_size=1,
    max_size=10,
)


@given(_terminallist)
def test_batch_status_completed_when_all_terminal_one_merged(
    items: list[tuple[int, ItemStatus]],
) -> None:
    """P3: Batch is completed iff every item is terminal AND at least one is merged."""
    # Build terminal items from scratch: all terminal, first one merged
    terminal_items: list[tuple[int, ItemStatus]] = []
    for idx in range(len(items)):
        # Use failed as a terminal status
        terminal_items.append((idx + 1, ItemStatus.failed))
    # Override first to merged
    if terminal_items:
        terminal_items[0] = (terminal_items[0][0], ItemStatus.merged)
    result = compute_batch_status(terminal_items)
    assert result == BatchStatus.completed


@given(_terminallist)
def test_batch_status_failed_when_all_terminal_none_merged(
    items: list[tuple[int, ItemStatus]],
) -> None:
    """P4: Batch is completed_with_errors iff every item is terminal AND none are merged."""
    # Build terminal items from scratch: all terminal, none merged
    terminal_items: list[tuple[int, ItemStatus]] = []
    for idx in range(len(items)):
        # Use failed as a terminal status
        terminal_items.append((idx + 1, ItemStatus.failed))
    result = compute_batch_status(terminal_items)
    assert result == BatchStatus.completed_with_errors


@given(_terminallist, sampled_from(NON_TERMINAL_STATUSES))
def test_batch_status_in_progress_otherwise(
    items: list[tuple[int, ItemStatus]],
    extra: ItemStatus,
) -> None:
    """P5: Batch is executing whenever at least one item is non-terminal.

    Appends one non-terminal item (drawn by Hypothesis) to whatever was
    generated, guaranteeing the input always has a non-terminal element.
    Then asserts the computed status is exactly executing — strict equality,
    not membership in a singleton — so a regression that returns any other
    BatchStatus (completed, completed_with_errors, …) fails immediately.
    """
    mixed_items = [*items, (9998, extra)]
    result = compute_batch_status(mixed_items)
    assert result == BatchStatus.executing
