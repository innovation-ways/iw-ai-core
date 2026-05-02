"""AC2 unit: _BLOCKING_TERMINAL_STATUSES membership invariant.

CR-00028: merge_failed, migration_invalid, and migration_rebase_failed are
operator-recoverable — excluded from _BLOCKING_TERMINAL_STATUSES so the cascade
does not fire for these statuses. Legacy hard failures (failed, setup_failed,
stalled, skipped, migration_rolled_back) remain blocking.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from orch.daemon.batch_manager import (
    _BLOCKING_TERMINAL_STATUSES,
    _current_execution_group,
)
from orch.db.models import BatchItem, BatchItemStatus


def _mock_batch_item(
    work_item_id: str,
    execution_group: int = 0,
    status: BatchItemStatus = BatchItemStatus.pending,
) -> MagicMock:
    """Build a mock BatchItem with the attributes _current_execution_group accesses."""
    bi = MagicMock(spec=BatchItem)
    bi.work_item_id = work_item_id
    bi.execution_group = execution_group
    bi.status = status
    bi.started_at = datetime(2024, 1, 1, tzinfo=UTC)
    return bi


class TestBlockingTerminalMembership:
    """CR-00028: membership invariant for _BLOCKING_TERMINAL_STATUSES."""

    def test_blocking_terminal_excludes_recoverable_statuses(self) -> None:
        """merge_failed, migration_invalid, migration_rebase_failed are NOT blocking.

        These three are operator-recoverable — the operator can retry or abandon.
        They must NOT appear in _BLOCKING_TERMINAL_STATUSES so the cascade skips them.
        """
        excluded = {
            BatchItemStatus.merge_failed,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rebase_failed,
        }
        for status in excluded:
            assert status not in _BLOCKING_TERMINAL_STATUSES, (
                f"{status.value} must NOT be in _BLOCKING_TERMINAL_STATUSES "
                f"(CR-00028: operator-recoverable, non-cascading)"
            )

    def test_blocking_terminal_includes_legacy_failed(self) -> None:
        """failed, setup_failed, stalled, skipped, migration_rolled_back ARE blocking.

        These represent hard failures — dependents in later groups MUST cascade-fail.
        """
        blocking = {
            BatchItemStatus.failed,
            BatchItemStatus.setup_failed,
            BatchItemStatus.stalled,
            BatchItemStatus.skipped,
            BatchItemStatus.migration_rolled_back,
        }
        for status in blocking:
            assert status in _BLOCKING_TERMINAL_STATUSES, (
                f"{status.value} MUST be in _BLOCKING_TERMINAL_STATUSES "
                f"(hard failure, cascade must fire)"
            )

    def test_merged_not_blocking(self) -> None:
        """merged is success — never blocking (baseline invariant)."""
        assert BatchItemStatus.merged not in _BLOCKING_TERMINAL_STATUSES


class TestCurrentExecutionGroupRecoverableStatuses:
    """AC2: _current_execution_group returns the group with recoverable statuses."""

    @pytest.mark.parametrize(
        "recoverable_status",
        [
            BatchItemStatus.merge_failed,
            BatchItemStatus.migration_invalid,
            BatchItemStatus.migration_rebase_failed,
        ],
    )
    def test_current_execution_group_treats_recoverable_as_open(
        self, recoverable_status: BatchItemStatus
    ) -> None:
        """Group with recoverable status stays open — next group NOT returned.

        CR-00028 AC2: dependents in later groups stay pending.
        """
        items = [
            _mock_batch_item("F-00001", execution_group=0, status=recoverable_status),
            _mock_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending),
        ]
        # Must return 0 (the group with the recoverable item), NOT 1
        assert _current_execution_group(items) == 0

    def test_current_execution_group_skips_legacy_failed(self) -> None:
        """Group with legacy `failed` is treated as terminal — advances to next group.

        The cascade-fail logic (separate code path in _process_batch) handles the
        actual cascade. _current_execution_group only determines "which group is open".
        """
        items = [
            _mock_batch_item("F-00001", execution_group=0, status=BatchItemStatus.failed),
            _mock_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending),
        ]
        # legacy failed IS terminal → group 0 skipped → returns 1
        assert _current_execution_group(items) == 1

    def test_current_execution_group_merged_advances(self) -> None:
        """merged group advances to next (baseline invariant — no regression)."""
        items = [
            _mock_batch_item("F-00001", execution_group=0, status=BatchItemStatus.merged),
            _mock_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending),
        ]
        assert _current_execution_group(items) == 1
