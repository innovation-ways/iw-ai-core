"""CR-00096: Verify setup_failed is not in _BLOCKING_TERMINAL_STATUSES.

AC1: setup_failed does not cascade to downstream execution groups.
The unit anchor: setup_failed must be in the exclusion set, not the blocking set.
"""

from __future__ import annotations

from orch.daemon.batch_manager import _BLOCKING_TERMINAL_STATUSES
from orch.db.models import BatchItemStatus


def test_setup_failed_not_in_blocking_statuses() -> None:
    """CR-00096 AC1: setup_failed is excluded from _BLOCKING_TERMINAL_STATUSES.

    setup_failed is an infrastructure failure (worktree setup, DB migration
    mismatch, port conflict) — not an implementation failure. The worktree
    never started so no implementation output was produced; downstream items
    cannot have a code dependency on it. The item is retryable via iw item-retry.
    """
    assert BatchItemStatus.setup_failed not in _BLOCKING_TERMINAL_STATUSES, (
        "setup_failed must be excluded from _BLOCKING_TERMINAL_STATUSES "
        "(CR-00096). Downstream items should not be permanently blocked by a "
        "transient infrastructure failure."
    )
