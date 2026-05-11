"""Unit tests for the migration-pipeline bug fix in merge_queue.

Before the fix, `_merge_item` had three guards:

    if batch_item.batch_id is not None and isinstance(batch_item.batch_id, int):

Because `BatchItem.batch_id` is always a string like "BATCH-00060", all three
pipeline phases (rebase, dry-run, post-merge apply) were silently skipped for
every real batch.  The fix removed the `isinstance` check, leaving only:

    if batch_item.batch_id is not None:

Tests here:
1. `_to_int_batch_id` helper — parametrised over all documented input shapes.
2. `_merge_item` calls all three pipeline functions for a string batch_id
   (regression test — before the fix, none were called).
3. `_merge_item` skips all three pipeline functions when batch_id is None.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from orch.db.safe_migrate import _to_int_batch_id

# ---------------------------------------------------------------------------
# 1. _to_int_batch_id helper
# ---------------------------------------------------------------------------


class TestToIntBatchId:
    """_to_int_batch_id converts mixed batch-id types to int or None."""

    def test_none_input_returns_none(self) -> None:
        assert _to_int_batch_id(None) is None

    def test_int_input_returned_unchanged(self) -> None:
        assert _to_int_batch_id(42) == 42

    def test_int_zero_returned_unchanged(self) -> None:
        assert _to_int_batch_id(0) == 0

    def test_string_batch_id_extracts_trailing_digits(self) -> None:
        assert _to_int_batch_id("BATCH-00060") == 60

    def test_string_batch_id_single_digit(self) -> None:
        assert _to_int_batch_id("BATCH-00001") == 1

    def test_string_without_trailing_digits_returns_none(self) -> None:
        assert _to_int_batch_id("no-digits") is None

    def test_empty_string_returns_none(self) -> None:
        assert _to_int_batch_id("") is None

    @pytest.mark.parametrize(
        ("batch_id", "expected"),
        [
            ("BATCH-00060", 60),
            ("BATCH-00001", 1),
            ("BATCH-00100", 100),
            (42, 42),
            (0, 0),
            (None, None),
            ("no-digits", None),
            ("", None),
        ],
    )
    def test_parametrised_conversions(
        self, batch_id: str | int | None, expected: int | None
    ) -> None:
        assert _to_int_batch_id(batch_id) == expected


# ---------------------------------------------------------------------------
# Shared helpers for _merge_item tests
# ---------------------------------------------------------------------------


def _make_project_config() -> MagicMock:
    from orch.daemon.project_registry import ProjectConfig

    return ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        enabled=True,
        cli_tool="opencode",
        model="minimax",
        worktree_base=".worktrees",
        config={},
    )


def _make_batch_item(
    batch_id: str | int | None,
    status_value: str = "completed",
    item_id: int = 110,
    work_item_id: str = "F-00060",
    worktree_path: str = "/wt/F-00060",
) -> MagicMock:
    """Build a minimal BatchItem mock with the fields _merge_item accesses."""
    from orch.db.models import BatchItem, BatchItemStatus

    item = MagicMock(spec=BatchItem)
    item.id = item_id
    item.batch_id = batch_id
    item.work_item_id = work_item_id
    item.status = BatchItemStatus.completed
    item.started_at = datetime(2024, 1, 1, tzinfo=UTC)
    item.worktree_info = {"path": worktree_path}
    item.worktree_compose_path = None
    item.merge_info = None
    item.merged_at = None
    item.notes = None
    item.project_id = "test-proj"
    return item


def _make_successful_rebase_result() -> MagicMock:
    """A RebaseResult that indicates no rebase was needed (always passes)."""
    from orch.daemon.migration_rebase import RebaseResult

    return RebaseResult(
        success=True,
        rebased=False,
        rewrites=[],
        worktree_base_sha="abc123",
        current_main_sha="abc123",
        message="No rebase needed",
        error_message=None,
    )


def _make_successful_dry_run_result() -> MagicMock:
    """A PipelineResult returned by run_pre_merge_dry_run on success."""
    from orch.daemon.migration_pipeline import PipelineResult

    return PipelineResult(
        phase="dry_run",
        success=True,
        final_batch_state="proceed_to_merge",
        frozen=False,
        message="Dry-run succeeded (100ms)",
    )


def _make_successful_apply_result() -> MagicMock:
    """A PipelineResult returned by run_post_merge_apply on success."""
    from orch.daemon.migration_pipeline import PipelineResult

    return PipelineResult(
        phase="apply",
        success=True,
        final_batch_state="merged",
        frozen=False,
        message="Applied successfully (50ms)",
    )


# ---------------------------------------------------------------------------
# 2. Regression: string batch_id must invoke all three pipeline phases
# ---------------------------------------------------------------------------


class TestMergeItemStringBatchIdInvokesPipeline:
    """Regression tests for the isinstance(batch_id, int) bug.

    Before the fix, all three pipeline phases were bypassed for string batch IDs
    (e.g. "BATCH-00060").  Each test below asserts that the corrected code calls
    the phase in question when batch_id is a non-None string.
    """

    def _run_merge_item(
        self,
        batch_item: MagicMock,
        *,
        mock_rebase_result: MagicMock | None = None,
        mock_dry_result: MagicMock | None = None,
        mock_apply_result: MagicMock | None = None,
    ) -> dict[str, MagicMock]:
        """Run _merge_item with all external side-effects mocked out.

        Returns a dict of the three pipeline mocks so callers can assert on them.
        """
        from orch.daemon.merge_queue import _merge_item

        rebase_result = mock_rebase_result or _make_successful_rebase_result()
        dry_result = mock_dry_result or _make_successful_dry_run_result()
        apply_result = mock_apply_result or _make_successful_apply_result()

        db = MagicMock()
        project_config = _make_project_config()

        with (
            patch(
                "orch.daemon.merge_queue.run_pre_merge_rebase",
                return_value=rebase_result,
            ) as mock_rebase,
            patch(
                "orch.daemon.merge_queue.run_pre_merge_dry_run",
                return_value=dry_result,
            ) as mock_dry,
            patch(
                "orch.daemon.merge_queue.run_post_merge_apply",
                return_value=apply_result,
            ) as mock_apply,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_subproc.return_value = MagicMock(returncode=0, stdout="squash ok", stderr="")
            _merge_item(db, batch_item, "test-proj", project_config)

        return {
            "rebase": mock_rebase,
            "dry_run": mock_dry,
            "apply": mock_apply,
        }

    def test_rebase_called_for_string_batch_id(self) -> None:
        """run_pre_merge_rebase must be invoked when batch_id is a non-None string."""
        item = _make_batch_item(batch_id="BATCH-00060")
        mocks = self._run_merge_item(item)
        mocks["rebase"].assert_called_once()

    def test_dry_run_called_for_string_batch_id(self) -> None:
        """run_pre_merge_dry_run must be invoked when batch_id is a non-None string."""
        item = _make_batch_item(batch_id="BATCH-00060")
        mocks = self._run_merge_item(item)
        mocks["dry_run"].assert_called_once()

    def test_post_merge_apply_called_for_string_batch_id(self) -> None:
        """run_post_merge_apply must be invoked when batch_id is a non-None string."""
        item = _make_batch_item(batch_id="BATCH-00060")
        mocks = self._run_merge_item(item)
        mocks["apply"].assert_called_once()

    def test_all_three_phases_called_together_for_string_batch_id(self) -> None:
        """All three phases run together for a real string batch ID."""
        item = _make_batch_item(batch_id="BATCH-00060")
        mocks = self._run_merge_item(item)
        mocks["rebase"].assert_called_once()
        mocks["dry_run"].assert_called_once()
        mocks["apply"].assert_called_once()

    def test_rebase_called_with_correct_batch_id_and_paths(self) -> None:
        """run_pre_merge_rebase receives the string batch_id, worktree path, and working_dir."""
        item = _make_batch_item(batch_id="BATCH-00060", worktree_path="/wt/F-00060")
        mocks = self._run_merge_item(item)
        call_args = mocks["rebase"].call_args
        assert call_args[0][0] == "BATCH-00060"
        assert call_args[0][1] == "/wt/F-00060"

    def test_dry_run_called_with_correct_worktree_path(self) -> None:
        """run_pre_merge_dry_run receives the worktree_path keyword argument."""
        item = _make_batch_item(batch_id="BATCH-00060", worktree_path="/wt/F-00060")
        mocks = self._run_merge_item(item)
        call_kwargs = mocks["dry_run"].call_args[1]
        assert call_kwargs["worktree_path"] == "/wt/F-00060"

    def test_post_merge_apply_called_with_string_batch_id(self) -> None:
        """run_post_merge_apply receives the string batch_id."""
        item = _make_batch_item(batch_id="BATCH-00060")
        mocks = self._run_merge_item(item)
        call_args = mocks["apply"].call_args
        assert call_args[0][0] == "BATCH-00060"

    def test_zero_padded_batch_id_also_triggers_pipeline(self) -> None:
        """Batch IDs with zero-padded numbers (e.g. "BATCH-00001") also pass the guard."""
        item = _make_batch_item(batch_id="BATCH-00001")
        mocks = self._run_merge_item(item)
        mocks["rebase"].assert_called_once()
        mocks["dry_run"].assert_called_once()
        mocks["apply"].assert_called_once()


# ---------------------------------------------------------------------------
# 3. batch_id=None skips all three pipeline phases
# ---------------------------------------------------------------------------


class TestMergeItemNoneBatchIdSkipsPipeline:
    """When batch_id is None, the pipeline must NOT be invoked.

    This was already the intended behaviour before the fix (the old guard
    `batch_item.batch_id is not None` still gated it for None).  The tests
    here document that the fix preserves this semantics.
    """

    def test_rebase_not_called_when_batch_id_is_none(self) -> None:
        item = _make_batch_item(batch_id=None)
        db = MagicMock()

        with (
            patch("orch.daemon.merge_queue.run_pre_merge_rebase") as mock_rebase,
            patch(
                "orch.daemon.merge_queue.run_pre_merge_dry_run",
                return_value=_make_successful_dry_run_result(),
            ),
            patch(
                "orch.daemon.merge_queue.run_post_merge_apply",
                return_value=_make_successful_apply_result(),
            ),
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_subproc.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            from orch.daemon.merge_queue import _merge_item

            _merge_item(db, item, "test-proj", _make_project_config())

        mock_rebase.assert_not_called()

    def test_dry_run_not_called_when_batch_id_is_none(self) -> None:
        item = _make_batch_item(batch_id=None)
        db = MagicMock()

        with (
            patch(
                "orch.daemon.merge_queue.run_pre_merge_rebase",
                return_value=_make_successful_rebase_result(),
            ),
            patch("orch.daemon.merge_queue.run_pre_merge_dry_run") as mock_dry,
            patch(
                "orch.daemon.merge_queue.run_post_merge_apply",
                return_value=_make_successful_apply_result(),
            ),
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_subproc.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            from orch.daemon.merge_queue import _merge_item

            _merge_item(db, item, "test-proj", _make_project_config())

        mock_dry.assert_not_called()

    def test_post_merge_apply_not_called_when_batch_id_is_none(self) -> None:
        item = _make_batch_item(batch_id=None)
        db = MagicMock()

        with (
            patch(
                "orch.daemon.merge_queue.run_pre_merge_rebase",
                return_value=_make_successful_rebase_result(),
            ),
            patch(
                "orch.daemon.merge_queue.run_pre_merge_dry_run",
                return_value=_make_successful_dry_run_result(),
            ),
            patch("orch.daemon.merge_queue.run_post_merge_apply") as mock_apply,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_subproc.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            from orch.daemon.merge_queue import _merge_item

            _merge_item(db, item, "test-proj", _make_project_config())

        mock_apply.assert_not_called()

    def test_merge_succeeds_without_pipeline_when_batch_id_is_none(self) -> None:
        """With batch_id=None the merge still completes successfully (no regressions)."""
        from orch.db.models import BatchItemStatus

        item = _make_batch_item(batch_id=None)
        db = MagicMock()

        with (
            patch(
                "orch.daemon.merge_queue.run_pre_merge_rebase",
                return_value=_make_successful_rebase_result(),
            ),
            patch(
                "orch.daemon.merge_queue.run_pre_merge_dry_run",
                return_value=_make_successful_dry_run_result(),
            ),
            patch(
                "orch.daemon.merge_queue.run_post_merge_apply",
                return_value=_make_successful_apply_result(),
            ),
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_subproc.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            from orch.daemon.merge_queue import _merge_item

            _merge_item(db, item, "test-proj", _make_project_config())

        assert item.status == BatchItemStatus.merged


# ---------------------------------------------------------------------------
# 4. Phase 3 rollback only when Phase 2 actually applied a revision
# ---------------------------------------------------------------------------


def _make_failed_apply_result(*, revisions_applied: list[str]) -> MagicMock:
    """A PipelineResult for a Phase-2 apply that failed.

    revisions_applied non-empty → apply advanced the DB and then died
    (rollback warranted). Empty → apply tripped a pre-flight check
    (SelfBlockerError / lock timeout) before touching the DB (no rollback).
    """
    from orch.daemon.migration_pipeline import PipelineResult

    if revisions_applied:
        return PipelineResult(
            phase="apply",
            success=False,
            final_batch_state="rollback_triggered",
            frozen=False,
            message="Apply failed after applying revisions",
            revisions_applied=list(revisions_applied),
        )
    return PipelineResult(
        phase="apply",
        success=False,
        final_batch_state="apply_deferred",
        frozen=False,
        message="Phase 2 apply would self-deadlock: ... See I-00063 for context.",
        revisions_applied=[],
    )


def _make_rollback_result() -> MagicMock:
    from orch.daemon.migration_pipeline import PipelineResult

    return PipelineResult(
        phase="rollback",
        success=True,
        final_batch_state="MIGRATION_ROLLED_BACK",
        frozen=False,
        message="Rollback succeeded (10ms)",
    )


class TestMergeItemRollbackGuard:
    """`_merge_item` must only run Phase 3 rollback when Phase 2 advanced the DB.

    Regression: a transient SelfBlockerError pre-flight failure (zero revisions
    applied) used to trigger `alembic downgrade -1`, which rolled back a
    previously-applied migration and left the orch DB behind head with writes
    disabled in the dashboard (observed after the BATCH-00089 merge, 2026-05-11).
    """

    def _run_merge_item(self, apply_result: MagicMock) -> dict[str, MagicMock]:
        from orch.daemon.merge_queue import _merge_item

        db = MagicMock()
        item = _make_batch_item(batch_id="BATCH-00089")

        with (
            patch(
                "orch.daemon.merge_queue.run_pre_merge_rebase",
                return_value=_make_successful_rebase_result(),
            ),
            patch(
                "orch.daemon.merge_queue.run_pre_merge_dry_run",
                return_value=_make_successful_dry_run_result(),
            ),
            patch(
                "orch.daemon.merge_queue.run_post_merge_apply",
                return_value=apply_result,
            ),
            patch(
                "orch.daemon.merge_queue.run_rollback", return_value=_make_rollback_result()
            ) as mock_rollback,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_subproc,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            mock_subproc.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            _merge_item(db, item, "test-proj", _make_project_config())

        return {"rollback": mock_rollback, "item": item}

    def test_no_rollback_when_apply_failed_with_zero_revisions(self) -> None:
        result = self._run_merge_item(_make_failed_apply_result(revisions_applied=[]))
        result["rollback"].assert_not_called()
        # The git squash-merge already happened — the item stays merged.
        from orch.db.models import BatchItemStatus

        assert result["item"].status == BatchItemStatus.merged

    def test_rollback_when_apply_failed_after_applying_a_revision(self) -> None:
        result = self._run_merge_item(_make_failed_apply_result(revisions_applied=["abc123"]))
        result["rollback"].assert_called_once()

    def test_no_rollback_on_successful_apply(self) -> None:
        result = self._run_merge_item(_make_successful_apply_result())
        result["rollback"].assert_not_called()
