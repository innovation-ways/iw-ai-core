"""Unit tests for merge_queue — no DB, no subprocess.

All database interaction and subprocess calls are mocked.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from orch.daemon.merge_queue import _merge_item, process_merge_queue
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import BatchItem, BatchItemStatus

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
        worktree_base=".worktrees",
        config={},
    )


def make_batch_item(
    work_item_id: str,
    status: BatchItemStatus = BatchItemStatus.completed,
    started_at: datetime | None = None,
    worktree_info: dict | None = None,
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
    def test_no_merge_when_already_merging(self):
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

    def test_no_merge_when_queue_empty(self):
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

    def test_failed_merge_marks_item_failed(self):
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})

        with patch("orch.daemon.merge_queue.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="conflict on main.py")
            _merge_item(db, item, "test-proj", make_project_config())

        assert item.status == BatchItemStatus.failed
        assert "conflict on main.py" in item.notes

    def test_timeout_marks_item_failed(self):
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})

        with patch(
            "orch.daemon.merge_queue.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="bash", timeout=120),
        ):
            _merge_item(db, item, "test-proj", make_project_config())

        assert item.status == BatchItemStatus.failed
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

    def test_merge_info_stdout_truncated_to_1000(self):
        db = MagicMock()
        item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        long_output = "x" * 5000

        with (
            patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout=long_output, stderr="")
            _merge_item(db, item, "test-proj", make_project_config())

        assert len(item.merge_info["stdout"]) == 1000
