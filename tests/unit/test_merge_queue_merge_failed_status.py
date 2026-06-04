"""AC1 + AC4: merge_failed status semantics.

AC1: MergeError (scope-gate, conflict, transient git) → merge_failed (not failed).
     WorkItem reverts to failed. merge_conflict daemon_event emitted.

AC4: No worktree path (data integrity issue) → failed (NOT merge_failed).
     This unrecoverable branch still cascades.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

from orch.daemon.merge_queue import _merge_item
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import BatchItem, BatchItemStatus, WorkItem, WorkItemStatus


def _project_config() -> ProjectConfig:
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


def _batch_item(
    work_item_id: str,
    worktree_info: dict[str, Any] | None = None,
) -> MagicMock:
    """Minimal mock BatchItem with the fields _merge_item accesses.

    worktree_info MUST be explicitly provided (not defaulted) to avoid
    MagicMock returning a truthy mock value that bypasses the no-path guard.
    """
    bi = MagicMock(spec=BatchItem)
    bi.work_item_id = work_item_id
    bi.status = BatchItemStatus.completed
    bi.started_at = datetime(2024, 1, 1, tzinfo=UTC)
    # Explicitly set worktree_info (never leave it to auto-mock)
    bi.worktree_info = worktree_info
    bi.id = abs(hash(work_item_id)) % 1000
    bi.merge_info = None
    bi.notes = None
    bi.batch_id = None  # None → migration pipeline skipped
    bi.worktree_compose_path = None
    return bi


def _branch_info_mock() -> MagicMock:
    """A mock BranchInfo that passes the I-00126 default-branch guard."""
    m = MagicMock()
    m.current_branch = "main"
    m.default_branch = "main"
    m.is_on_default = True
    return m


# ---------------------------------------------------------------------------
# AC1: MergeError → merge_failed (not failed)
# ---------------------------------------------------------------------------


class TestMergeErrorWritesMergeFailed:
    """Tests for MergeErrorWritesMergeFailed scenarios."""

    def test_merge_error_writes_merge_failed_not_failed(self) -> None:
        """MergeError from worktree_commit.sh → merge_failed (CR-00028 AC1)."""
        db = MagicMock()
        item = _batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})

        with (
            patch("orch.daemon.merge_queue.resolve_branch_for_project") as mock_resolve,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
        ):
            mock_resolve.return_value = _branch_info_mock()
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="scope gate failed")
            _merge_item(db, item, "test-proj", _project_config())

        # CR-00028: must be merge_failed, not failed — so cascade does NOT fire
        assert item.status == BatchItemStatus.merge_failed
        assert "scope gate failed" in item.notes

    def test_timeout_writes_merge_failed(self) -> None:
        """subprocess.TimeoutExpired → merge_failed (CR-00028 AC1)."""
        db = MagicMock()
        item = _batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})

        with (
            patch("orch.daemon.merge_queue.resolve_branch_for_project") as mock_resolve,
            patch(
                "orch.daemon.merge_queue.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="bash", timeout=120),
            ),
        ):
            mock_resolve.return_value = _branch_info_mock()
            _merge_item(db, item, "test-proj", _project_config())

        assert item.status == BatchItemStatus.merge_failed

    def test_workitem_reverts_to_failed_on_merge_error(self) -> None:
        """C4 revert: WorkItem.status becomes failed (CR-00028 AC1)."""
        db = MagicMock()
        item = _batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        item.work_item_id = "F-00001"

        work_item = MagicMock()
        work_item.status = WorkItemStatus.completed

        work_item_query = MagicMock()
        work_item_query.filter_by.return_value.one_or_none.return_value = work_item

        def fake_query(model: type[Any]) -> MagicMock:
            """Return fake query."""
            if model is WorkItem:
                return work_item_query
            return MagicMock()

        db.query.side_effect = fake_query

        with (
            patch("orch.daemon.merge_queue.resolve_branch_for_project") as mock_resolve,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
        ):
            mock_resolve.return_value = _branch_info_mock()
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="conflict")
            _merge_item(db, item, "test-proj", _project_config())

        # C4: WorkItem reverts to failed so it is not orphaned as completed
        assert work_item.status == WorkItemStatus.failed

    def test_merge_conflict_event_emitted_on_merge_failed(self) -> None:
        """merge_conflict daemon_event is emitted (CR-00028 AC1 — existing behaviour preserved)."""
        db = MagicMock()
        item = _batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
        emitted_events: list[dict[str, Any]] = []

        def capture_emit(
            db_: Any,
            project_id: str,
            event_type: str,
            entity_id: str | None,
            entity_type: str | None,
            message: str,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            """Return capture emit."""
            emitted_events.append(
                {
                    "event_type": event_type,
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                }
            )

        with (
            patch("orch.daemon.merge_queue.resolve_branch_for_project") as mock_resolve,
            patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
            patch("orch.daemon.merge_queue._emit_event", side_effect=capture_emit),
        ):
            mock_resolve.return_value = _branch_info_mock()
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="merge conflict")
            _merge_item(db, item, "test-proj", _project_config())

        # merge_conflict event must be emitted so the SSE feed toasts it
        assert any(e["event_type"] == "merge_conflict" for e in emitted_events)


# ---------------------------------------------------------------------------
# AC4: no worktree path → failed (NOT merge_failed)
# ---------------------------------------------------------------------------


class TestNoWorktreePathStillWritesFailed:
    """Tests for NoWorktreePathStillWritesFailed scenarios."""

    def test_no_worktree_info_writes_failed(self) -> None:
        """worktree_info=None → failed (NOT merge_failed) — unrecoverable cascade fires."""
        db = MagicMock()
        item = _batch_item("F-00001", worktree_info=None)

        with patch("orch.daemon.merge_queue.subprocess.run") as mock_run:
            _merge_item(db, item, "test-proj", _project_config())

        # subprocess never called — this is a data integrity issue
        mock_run.assert_not_called()
        # AC4: must be `failed` so the cascade fires
        assert item.status == BatchItemStatus.failed
        assert "No worktree path" in item.notes

    def test_empty_worktree_info_writes_failed(self) -> None:
        """worktree_info={} (no "path" key) → failed (CR-00028 AC4)."""
        db = MagicMock()
        item = _batch_item("F-00001", worktree_info={})

        with patch("orch.daemon.merge_queue.subprocess.run") as mock_run:
            _merge_item(db, item, "test-proj", _project_config())

        mock_run.assert_not_called()
        assert item.status == BatchItemStatus.failed

    def test_no_worktree_path_still_cascades(self) -> None:
        """The no-path branch must NOT set merge_failed — dependents must still cascade."""
        db = MagicMock()
        item = _batch_item("F-00001", worktree_info={})

        with patch("orch.daemon.merge_queue.subprocess.run") as _mock_run:
            _merge_item(db, item, "test-proj", _project_config())

        # This is the key AC4 invariant: the branch explicitly writes `failed`,
        # not `merge_failed`, so the existing cascade logic fires.
        assert item.status == BatchItemStatus.failed
        # Notes mention the cascade intent
        assert "No worktree path" in item.notes
