"""Unit tests for merge_queue — no DB, no subprocess.

All database interaction and subprocess calls are mocked.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from orch.daemon.merge_queue import _merge_item, process_merge_queue
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import BatchItem, BatchItemStatus, WorkItem, WorkItemStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_project_config() -> ProjectConfig:
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


def make_batch_item(
    work_item_id: str,
    status: BatchItemStatus = BatchItemStatus.completed,
    started_at: datetime | None = None,
    worktree_info: dict | None = None,
    batch_id: str | int | None = None,
) -> MagicMock:
    item = MagicMock(spec=BatchItem)
    item.work_item_id = work_item_id
    item.status = status
    item.started_at = started_at or datetime(2024, 1, 1, tzinfo=UTC)
    item.worktree_info = {"path": f"/wt/{work_item_id}"} if worktree_info is None else worktree_info
    item.id = abs(hash(work_item_id)) % 1000
    item.merge_info = None
    item.merged_at = None
    item.notes = None
    item.batch_id = batch_id  # None skips migration pipeline; set explicitly to test it
    item.worktree_compose_path = None
    return item


def make_db(
    ready_items: list[MagicMock] | None = None,
    merging_item: MagicMock | None = None,
) -> MagicMock:
    """Build a mock Session whose .query() returns configured results."""
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        filter_q = MagicMock()
        q.filter.return_value = filter_q

        if model is BatchItem:

            def filter_again(*args, **kwargs):
                inner_q = MagicMock()
                # Used to detect merging check vs. completed check via status kwarg
                # We rely on call order: first call = merging check, second = completed
                inner_q.first.return_value = merging_item
                inner_q.order_by.return_value.first.return_value = (
                    ready_items[0] if ready_items else None
                )
                return inner_q

            filter_q.first.return_value = merging_item
            filter_q.order_by.return_value.first.return_value = (
                ready_items[0] if ready_items else None
            )

        return q

    db.query.side_effect = query_side_effect
    return db


# ---------------------------------------------------------------------------
# process_merge_queue
# ---------------------------------------------------------------------------


class TestProcessMergeQueue:
    def test_no_merge_when_already_merging(self):  # noqa: assertion-scanner
        merging_item = make_batch_item("F-00001", status=BatchItemStatus.merging)
        db = MagicMock()

        # First filter call returns merging item (in-progress check)
        q = MagicMock()
        q.filter.return_value.first.return_value = merging_item
        q.filter.return_value.order_by.return_value.first.return_value = None
        db.query.return_value = q

        project_config = make_project_config()

        with patch("orch.daemon.merge_queue._merge_item") as mock_merge:
            process_merge_queue(db, "test-proj", project_config, MagicMock())

        # _merge_item should NOT be called while another merge is in progress
        mock_merge.assert_not_called()

    def test_no_merge_when_queue_empty(self):  # noqa: assertion-scanner
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.return_value = None  # no merging, no ready
        q.filter.return_value.order_by.return_value.first.return_value = None
        db.query.return_value = q

        with patch("orch.daemon.merge_queue._merge_item") as mock_merge:
            process_merge_queue(db, "test-proj", make_project_config(), MagicMock())

        mock_merge.assert_not_called()

    def test_merges_oldest_first(self):
        """process_merge_queue delegates ordering to the DB query (order_by started_at)."""
        older = make_batch_item("F-00001", started_at=datetime(2024, 1, 1, tzinfo=UTC))
        # newer item exists in DB; test verifies ordering picks the older one first
        make_batch_item("F-00002", started_at=datetime(2024, 1, 2, tzinfo=UTC))

        db = MagicMock()
        call_count = [0]

        def query_side(model):
            q = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # First query: check for merging (none)
                q.filter.return_value.first.return_value = None
            else:
                # Second query: find oldest completed
                q.filter.return_value.order_by.return_value.first.return_value = older
            return q

        db.query.side_effect = query_side

        merged_items: list[MagicMock] = []

        def fake_merge(db_, item, project_id, project_config):
            merged_items.append(item)

        with patch("orch.daemon.merge_queue._merge_item", side_effect=fake_merge):
            process_merge_queue(db, "test-proj", make_project_config(), MagicMock())

        assert len(merged_items) == 1
        assert merged_items[0].work_item_id == "F-00001"


# ---------------------------------------------------------------------------
# _merge_item
# ---------------------------------------------------------------------------


class TestMergeItem:
    def test_successful_merge_sets_merged(self):
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})

        with patch("orch.daemon.merge_queue.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="squash ok", stderr="")
            with patch("orch.daemon.merge_queue._cleanup_worktree"):
                _merge_item(db, item, "test-proj", make_project_config())

        assert item.status == BatchItemStatus.merged
        assert item.merged_at is not None
        assert item.merge_info is not None

    def test_failed_merge_marks_item_merge_failed(self):
        """CR-00028: merge failure sets merge_failed (not failed) so cascade is not triggered."""
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})

        with patch("orch.daemon.merge_queue.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="conflict on main.py")
            _merge_item(db, item, "test-proj", make_project_config())

        assert item.status == BatchItemStatus.merge_failed
        assert "conflict on main.py" in item.notes

    def test_timeout_marks_item_merge_failed(self):
        """CR-00028: merge timeout sets merge_failed (not failed) so cascade is not triggered."""
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})

        with patch(
            "orch.daemon.merge_queue.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="bash", timeout=120),
        ):
            _merge_item(db, item, "test-proj", make_project_config())

        assert item.status == BatchItemStatus.merge_failed
        assert item.notes is not None

    def test_missing_worktree_path_marks_failed_without_running_script(self):
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={})  # no "path" key

        with patch("orch.daemon.merge_queue.subprocess.run") as mock_run:
            _merge_item(db, item, "test-proj", make_project_config())

        mock_run.assert_not_called()
        assert item.status == BatchItemStatus.failed
        assert "No worktree path" in item.notes

    def test_merging_status_set_before_script_runs(self):
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        status_at_call: list[BatchItemStatus] = []

        def capture_status(*args, **kwargs):
            status_at_call.append(item.status)
            return MagicMock(returncode=0, stdout="ok", stderr="")

        with (
            patch("orch.daemon.merge_queue.subprocess.run", side_effect=capture_status),
            patch("orch.daemon.merge_queue._cleanup_worktree"),
        ):
            _merge_item(db, item, "test-proj", make_project_config())

        assert status_at_call[0] == BatchItemStatus.merging

    def test_merge_info_stdout_truncated_to_8000(self):
        """M2: merge_info stores up to 8000 chars of stdout (was 1000)."""
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        long_output = "x" * 10000

        with (
            patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout=long_output, stderr="")
            _merge_item(db, item, "test-proj", make_project_config())

        assert len(item.merge_info["stdout"]) == 8000
        assert item.merge_info["stdout_truncated"] is True

    def test_rebase_failure_sets_migration_rebase_failed_and_returns(self):
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        item.batch_id = 42

        from orch.daemon.migration_rebase import RebaseResult

        mock_rebase_result = RebaseResult(
            success=False,
            rebased=False,
            rewrites=[],
            worktree_base_sha="abc123",
            current_main_sha="def456",
            message="Rebase failed",
            error_message="boom",
        )

        with (
            patch("orch.daemon.merge_queue.run_pre_merge_rebase", return_value=mock_rebase_result),
            patch("orch.daemon.merge_queue.worktree_compose.down") as mock_down,
        ):
            _merge_item(db, item, "test-proj", make_project_config())

        assert item.status == BatchItemStatus.migration_rebase_failed
        assert "boom" in item.notes
        mock_down.assert_called_once()

    def test_rebase_success_continues_to_dry_run_with_worktree_path(self):
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        item.batch_id = 42

        from orch.daemon.migration_pipeline import PipelineResult
        from orch.daemon.migration_rebase import RebaseResult
        from orch.db.safe_migrate import DryRunResult

        mock_rebase_result = RebaseResult(
            success=True,
            rebased=True,
            rewrites=[],
            worktree_base_sha="abc123",
            current_main_sha="def456",
            message="Rebase ok",
            error_message=None,
        )

        mock_dry_result = DryRunResult(
            revisions_applied=["abc123"],
            success=True,
            duration_ms=500,
            stdout_tail="",
            stderr_tail="",
            error_message=None,
        )

        mock_apply_result = PipelineResult(
            phase="apply",
            success=True,
            final_batch_state="merged",
            frozen=False,
            message="Applied successfully (0ms)",
        )

        with (
            patch("orch.daemon.merge_queue.run_pre_merge_rebase", return_value=mock_rebase_result),
            patch(
                "orch.daemon.merge_queue.run_pre_merge_dry_run", return_value=mock_dry_result
            ) as mock_dry,
            patch("orch.daemon.merge_queue.run_post_merge_apply", return_value=mock_apply_result),
            patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            _merge_item(db, item, "test-proj", make_project_config())

        mock_dry.assert_called_once()
        call_kwargs = mock_dry.call_args[1]
        assert call_kwargs["worktree_path"] == "/wt/F-00001"


# ---------------------------------------------------------------------------
# C4: WorkItem status revert on merge failure
# ---------------------------------------------------------------------------


def make_work_item_mock(status: WorkItemStatus = WorkItemStatus.completed) -> MagicMock:
    """Build a mock WorkItem with the given status and completed_at set."""
    wi = MagicMock(spec=WorkItem)
    wi.status = status
    wi.completed_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    return wi


def make_db_with_work_item(work_item: MagicMock | None) -> MagicMock:
    """Build a mock Session returning work_item from query(WorkItem).filter_by().one_or_none()."""
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model is WorkItem:
            q.filter_by.return_value.one_or_none.return_value = work_item
        return q

    db.query.side_effect = query_side_effect
    return db


class TestMergeItemC4WorkItemRevert:
    """C4: WorkItem.status must be reverted to failed on all merge failure paths."""

    def _make_db_for_failure(self, work_item: MagicMock | None) -> MagicMock:
        return make_db_with_work_item(work_item)

    def test_merge_error_reverts_work_item_status(self):
        """MergeError path: WorkItem.status reverted to failed, completed_at cleared.
        CR-00028: batch_item.status is now merge_failed (not failed)."""
        wi = make_work_item_mock(WorkItemStatus.completed)
        db = make_db_with_work_item(wi)
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        item.project_id = "test-proj"

        with patch("orch.daemon.merge_queue.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="conflict")
            _merge_item(db, item, "test-proj", make_project_config())

        assert item.status == BatchItemStatus.merge_failed
        assert wi.status == WorkItemStatus.failed
        assert wi.completed_at is None

    def test_timeout_reverts_work_item_status(self):
        """TimeoutExpired path: WorkItem.status reverted to failed, completed_at cleared.
        CR-00028: batch_item.status is now merge_failed (not failed)."""
        wi = make_work_item_mock(WorkItemStatus.completed)
        db = make_db_with_work_item(wi)
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        item.project_id = "test-proj"

        with patch(
            "orch.daemon.merge_queue.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="bash", timeout=120),
        ):
            _merge_item(db, item, "test-proj", make_project_config())

        assert item.status == BatchItemStatus.merge_failed
        assert wi.status == WorkItemStatus.failed
        assert wi.completed_at is None

    def test_merge_error_does_not_revert_if_work_item_not_completed(self):
        """If WorkItem is already failed/other, do not touch it.
        CR-00028: batch_item.status is now merge_failed (not failed)."""
        wi = make_work_item_mock(WorkItemStatus.failed)
        db = make_db_with_work_item(wi)
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        item.project_id = "test-proj"
        original_completed_at = wi.completed_at

        with patch("orch.daemon.merge_queue.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="conflict")
            _merge_item(db, item, "test-proj", make_project_config())

        # status was already failed; completed_at should not have been touched
        assert item.status == BatchItemStatus.merge_failed
        assert wi.status == WorkItemStatus.failed
        assert wi.completed_at == original_completed_at

    def test_merge_error_handles_missing_work_item_gracefully(self):
        """If WorkItem row not found, batch_item still marked merge_failed, no crash.
        CR-00028: changed from failed to merge_failed."""
        db = make_db_with_work_item(None)
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        item.project_id = "test-proj"

        with patch("orch.daemon.merge_queue.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="conflict")
            _merge_item(db, item, "test-proj", make_project_config())

        assert item.status == BatchItemStatus.merge_failed

    def test_rebase_failure_reverts_work_item_status(self):
        """migration_rebase_failed path: WorkItem.status reverted to failed."""
        wi = make_work_item_mock(WorkItemStatus.completed)
        db = make_db_with_work_item(wi)
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        item.batch_id = 42
        item.project_id = "test-proj"

        from orch.daemon.migration_rebase import RebaseResult

        mock_rebase_result = RebaseResult(
            success=False,
            rebased=False,
            rewrites=[],
            worktree_base_sha="abc123",
            current_main_sha="def456",
            message="Rebase failed",
            error_message="boom",
        )

        with (
            patch("orch.daemon.merge_queue.run_pre_merge_rebase", return_value=mock_rebase_result),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            _merge_item(db, item, "test-proj", make_project_config())

        assert item.status == BatchItemStatus.migration_rebase_failed
        assert wi.status == WorkItemStatus.failed
        assert wi.completed_at is None

    def test_migration_invalid_reverts_work_item_status(self):
        """migration_invalid path: WorkItem.status reverted to failed."""
        wi = make_work_item_mock(WorkItemStatus.completed)
        db = make_db_with_work_item(wi)
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        item.batch_id = 42
        item.project_id = "test-proj"

        from orch.daemon.migration_pipeline import PipelineResult
        from orch.daemon.migration_rebase import RebaseResult

        mock_rebase_result = RebaseResult(
            success=True,
            rebased=False,
            rewrites=[],
            worktree_base_sha="abc123",
            current_main_sha="abc123",
            message="No rebase needed",
            error_message=None,
        )

        # run_pre_merge_dry_run returns PipelineResult, not DryRunResult
        mock_dry_result = PipelineResult(
            phase="dry_run",
            success=False,
            final_batch_state="MIGRATION_INVALID",
            frozen=False,
            message="dry run failed: migration error",
        )

        with (
            patch("orch.daemon.merge_queue.run_pre_merge_rebase", return_value=mock_rebase_result),
            patch("orch.daemon.merge_queue.run_pre_merge_dry_run", return_value=mock_dry_result),
            patch("orch.daemon.merge_queue.worktree_compose.down"),
        ):
            _merge_item(db, item, "test-proj", make_project_config())

        assert item.status == BatchItemStatus.migration_invalid
        assert wi.status == WorkItemStatus.failed
        assert wi.completed_at is None

    def test_successful_merge_does_not_revert_work_item(self):
        """Control: successful merge keeps WorkItem as completed with completed_at set."""
        wi = make_work_item_mock(WorkItemStatus.completed)
        db = make_db_with_work_item(wi)
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        item.project_id = "test-proj"

        with (
            patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="squash ok", stderr="")
            _merge_item(db, item, "test-proj", make_project_config())

        assert item.status == BatchItemStatus.merged
        # WorkItem status untouched by merge_queue (batch_manager owns that transition)
        assert wi.status == WorkItemStatus.completed


# ---------------------------------------------------------------------------
# M2: merge_info stdout limit raised to 8000 with truncation flag
# ---------------------------------------------------------------------------


class TestMergeInfoM2:
    def test_stdout_over_8000_truncated_to_8000_with_flag(self):
        """stdout > 8000 chars: stored as 8000 chars, stdout_truncated=True."""
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        long_output = "y" * 10000

        with (
            patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout=long_output, stderr="")
            _merge_item(db, item, "test-proj", make_project_config())

        assert len(item.merge_info["stdout"]) == 8000
        assert item.merge_info["stdout_truncated"] is True

    def test_stdout_under_8000_stored_in_full_with_flag_false(self):
        """stdout < 8000 chars: stored completely, stdout_truncated=False."""
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        short_output = "z" * 500

        with (
            patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout=short_output, stderr="")
            _merge_item(db, item, "test-proj", make_project_config())

        assert item.merge_info["stdout"] == short_output
        assert item.merge_info["stdout_truncated"] is False

    def test_stdout_exactly_8000_stored_in_full_with_flag_false(self):
        """stdout exactly 8000 chars: stored in full, stdout_truncated=False."""
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        exact_output = "a" * 8000

        with (
            patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout=exact_output, stderr="")
            _merge_item(db, item, "test-proj", make_project_config())

        assert len(item.merge_info["stdout"]) == 8000
        assert item.merge_info["stdout_truncated"] is False
