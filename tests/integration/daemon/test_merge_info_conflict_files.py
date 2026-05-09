"""Integration tests for F-00076 merge_info conflict_files capture.

Verifies that BatchItem.merge_info["conflict_files"] is correctly populated
after a rebase with auto-resolved conflicts, and stays empty after a clean rebase.

These tests mock subprocess.run to feed controlled stdout from worktree_commit.sh
since exercising the full bash script requires a real git repository with
branch history. They call _merge_item directly (the internal function that
runs worktree_commit.sh) rather than the full process_merge_queue flow.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from orch.daemon.merge_queue import _merge_item
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    Project,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _unique_id(prefix: str = "F-00076") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _make_mock_result(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> MagicMock:
    """Build a mock subprocess.CompletedProcess."""
    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


class TestMergeInfoConflictFiles:
    """Tests for BatchItem.merge_info["conflict_files"]."""

    @pytest.fixture
    def project_id(self) -> str:
        return "test-proj-merge-conflict"

    def test_rebase_with_auto_resolved_conflict_captures_conflict_files(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Rebase with auto-resolved uv.lock conflict → conflict_files == ["uv.lock"].

        The worktree_commit.sh stdout contains:
            [worktree_commit] CONFLICT_FILES ["uv.lock"]
        and exits 0 (rebase succeeded).
        """
        item_id = _unique_id()
        worktree_path = f"/tmp/fake_wt_{uuid.uuid4().hex[:8]}"

        # Create WorkItem and BatchItem with a fake worktree path
        wi = WorkItem(
            project_id=test_project.id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Test Feature {item_id}",
            status=WorkItemStatus.completed,
            impacted_paths=["uv.lock"],
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(wi)
        db_session.flush()

        # Create the Batch first (BatchItem has FK to Batch)
        batch_id = _unique_id()
        batch = Batch(
            id=batch_id,
            project_id=test_project.id,
            status=BatchStatus.executing,
            max_parallel=1,
        )
        db_session.add(batch)
        db_session.flush()

        bi = BatchItem(
            project_id=test_project.id,
            batch_id=batch_id,
            work_item_id=item_id,
            execution_group=0,
            status=BatchItemStatus.merging,
        )
        # Set worktree_info so _merge_item doesn't skip with "no worktree path"
        bi.worktree_info = {
            "path": worktree_path,
            "branch": f"agent/{item_id}",
            "created_at": "now",
        }
        db_session.add(bi)
        db_session.flush()

        # Mock stdout from worktree_commit.sh with CONFLICT_FILES marker
        mock_stdout = (
            "[worktree_commit] INFO: Rebasing feature-00001 onto main (abc123...def456)\n"
            '[worktree_commit] CONFLICT_FILES ["uv.lock"]\n'
            "[worktree_commit] OK: Rebased feature-00001 (auto-resolved conflicts): "
            "abc123 → def456\n"
        )
        mock_result = _make_mock_result(stdout=mock_stdout, stderr="", returncode=0)

        from orch.daemon.project_registry import ProjectConfig

        project_config = ProjectConfig(
            id=test_project.id,
            display_name=test_project.display_name,
            repo_root="/repos/test",
            enabled=True,
            cli_tool="iw",
            model="minimax",
            worktree_base="/tmp/worktrees",
            config={},
        )

        # Mock the bash script and migration helpers that _merge_item calls
        with (
            patch("subprocess.run", return_value=mock_result),
            patch("orch.daemon.merge_queue.run_pre_merge_rebase") as mock_rebase,
            patch("orch.daemon.merge_queue.run_pre_merge_dry_run") as mock_dry,
            patch("orch.daemon.merge_queue.worktree_compose") as mock_compose,
            patch("orch.daemon.merge_queue.run_post_merge_apply") as mock_apply,
            patch("orch.daemon.merge_queue.run_rollback") as mock_rollback,
            patch("orch.daemon.batch_merge_hooks.trigger_doc_regeneration_on_merge"),
        ):
            mock_rebase.return_value = MagicMock(success=True)
            mock_dry.return_value = MagicMock(success=True)
            mock_compose.down = MagicMock()
            mock_apply.return_value = MagicMock(success=True)
            mock_rollback.return_value = MagicMock(success=True, frozen=False, message="ok")

            _merge_item(db_session, bi, test_project.id, project_config)

        db_session.refresh(bi)
        assert bi.merge_info is not None
        assert "conflict_files" in bi.merge_info
        assert bi.merge_info["conflict_files"] == ["uv.lock"]

    def test_clean_rebase_no_conflicts_conflict_files_empty(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Clean rebase (no conflicts) → conflict_files == [].

        worktree_commit.sh exits 0 with no CONFLICT_FILES marker.
        """
        item_id = _unique_id()
        worktree_path = f"/tmp/fake_wt_{uuid.uuid4().hex[:8]}"

        wi = WorkItem(
            project_id=test_project.id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Test Feature {item_id}",
            status=WorkItemStatus.completed,
            impacted_paths=["src/app/main.py"],
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(wi)
        db_session.flush()

        batch_id = _unique_id()
        batch = Batch(
            id=batch_id,
            project_id=test_project.id,
            status=BatchStatus.executing,
            max_parallel=1,
        )
        db_session.add(batch)
        db_session.flush()

        bi = BatchItem(
            project_id=test_project.id,
            batch_id=batch_id,
            work_item_id=item_id,
            execution_group=0,
            status=BatchItemStatus.merging,
        )
        bi.worktree_info = {
            "path": worktree_path,
            "branch": f"agent/{item_id}",
            "created_at": "now",
        }
        db_session.add(bi)
        db_session.flush()

        # Clean rebase: no conflicts, no CONFLICT_FILES marker
        mock_stdout = (
            "[worktree_commit] INFO: Branch already contains main tip (abc123) — no rebase needed\n"
            "[worktree_commit] OK: Branch up to date\n"
        )
        mock_result = _make_mock_result(stdout=mock_stdout, stderr="", returncode=0)

        from orch.daemon.project_registry import ProjectConfig

        project_config = ProjectConfig(
            id=test_project.id,
            display_name=test_project.display_name,
            repo_root="/repos/test",
            enabled=True,
            cli_tool="iw",
            model="minimax",
            worktree_base="/tmp/worktrees",
            config={},
        )

        with (
            patch("subprocess.run", return_value=mock_result),
            patch("orch.daemon.merge_queue.run_pre_merge_rebase") as mock_rebase,
            patch("orch.daemon.merge_queue.run_pre_merge_dry_run") as mock_dry,
            patch("orch.daemon.merge_queue.worktree_compose") as mock_compose,
            patch("orch.daemon.merge_queue.run_post_merge_apply") as mock_apply,
            patch("orch.daemon.merge_queue.run_rollback") as mock_rollback,
            patch("orch.daemon.batch_merge_hooks.trigger_doc_regeneration_on_merge"),
        ):
            mock_rebase.return_value = MagicMock(success=True)
            mock_dry.return_value = MagicMock(success=True)
            mock_compose.down = MagicMock()
            mock_apply.return_value = MagicMock(success=True)
            mock_rollback.return_value = MagicMock(success=True, frozen=False, message="ok")

            _merge_item(db_session, bi, test_project.id, project_config)

        db_session.refresh(bi)
        assert bi.merge_info is not None
        assert "conflict_files" in bi.merge_info
        assert bi.merge_info["conflict_files"] == []

    def test_rebase_failure_with_conflict_files_still_captured(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Rebase exits non-zero but emitted CONFLICT_FILES before failing → still captured.

        The script emits CONFLICT_FILES before exit 1, and the error path
        in _merge_item parses stdout+stderr for the marker.
        """
        item_id = _unique_id()
        worktree_path = f"/tmp/fake_wt_{uuid.uuid4().hex[:8]}"

        wi = WorkItem(
            project_id=test_project.id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Test Feature {item_id}",
            status=WorkItemStatus.completed,
            impacted_paths=["src/app/main.py"],
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(wi)
        db_session.flush()

        batch_id = _unique_id()
        batch = Batch(
            id=batch_id,
            project_id=test_project.id,
            status=BatchStatus.executing,
            max_parallel=1,
        )
        db_session.add(batch)
        db_session.flush()

        bi = BatchItem(
            project_id=test_project.id,
            batch_id=batch_id,
            work_item_id=item_id,
            execution_group=0,
            status=BatchItemStatus.merging,
        )
        bi.worktree_info = {
            "path": worktree_path,
            "branch": f"agent/{item_id}",
            "created_at": "now",
        }
        db_session.add(bi)
        db_session.flush()

        # Script emitted CONFLICT_FILES before hitting blocking conflict and exiting 1
        mock_stdout = (
            "[worktree_commit] INFO: Rebasing feature-00001 onto main\n"
            '[worktree_commit] CONFLICT_FILES ["src/app/main.py", "src/app/config.py"]\n'
            "[worktree_commit] ERROR: Rebase conflict in implementation files\n"
        )
        mock_result = _make_mock_result(
            stdout=mock_stdout,
            stderr="exit code 1",
            returncode=1,
        )

        from orch.daemon.project_registry import ProjectConfig

        project_config = ProjectConfig(
            id=test_project.id,
            display_name=test_project.display_name,
            repo_root="/repos/test",
            enabled=True,
            cli_tool="iw",
            model="minimax",
            worktree_base="/tmp/worktrees",
            config={},
        )

        with (
            patch("subprocess.run", return_value=mock_result),
            patch("orch.daemon.merge_queue.run_pre_merge_rebase") as mock_rebase,
            patch("orch.daemon.merge_queue.run_pre_merge_dry_run") as mock_dry,
            patch("orch.daemon.merge_queue.worktree_compose") as mock_compose,
            patch("orch.daemon.merge_queue.run_post_merge_apply") as mock_apply,
            patch("orch.daemon.merge_queue.run_rollback") as mock_rollback,
            patch("orch.daemon.batch_merge_hooks.trigger_doc_regeneration_on_merge"),
        ):
            mock_rebase.return_value = MagicMock(success=True)
            mock_dry.return_value = MagicMock(success=True)
            mock_compose.down = MagicMock()
            mock_apply.return_value = MagicMock(success=True)
            mock_rollback.return_value = MagicMock(success=True, frozen=False, message="ok")

            _merge_item(db_session, bi, test_project.id, project_config)

        db_session.refresh(bi)
        # merge_failed status with conflict_files captured
        assert bi.status == BatchItemStatus.merge_failed
        assert bi.merge_info is not None
        assert "conflict_files" in bi.merge_info
        assert set(bi.merge_info["conflict_files"]) == {"src/app/main.py", "src/app/config.py"}

    def test_multiple_conflict_files_captured(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Multiple auto-resolved conflicts are all captured as a JSON array."""
        item_id = _unique_id()
        worktree_path = f"/tmp/fake_wt_{uuid.uuid4().hex[:8]}"

        wi = WorkItem(
            project_id=test_project.id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Test Feature {item_id}",
            status=WorkItemStatus.completed,
            impacted_paths=["pyproject.toml", "src/app/main.py", "src/app/config.py"],
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(wi)
        db_session.flush()

        batch_id = _unique_id()
        batch = Batch(
            id=batch_id,
            project_id=test_project.id,
            status=BatchStatus.executing,
            max_parallel=1,
        )
        db_session.add(batch)
        db_session.flush()

        bi = BatchItem(
            project_id=test_project.id,
            batch_id=batch_id,
            work_item_id=item_id,
            execution_group=0,
            status=BatchItemStatus.merging,
        )
        bi.worktree_info = {
            "path": worktree_path,
            "branch": f"agent/{item_id}",
            "created_at": "now",
        }
        db_session.add(bi)
        db_session.flush()

        # JSON array with multiple files
        mock_stdout = (
            "[worktree_commit] INFO: Rebasing\n"
            "[worktree_commit] CONFLICT_FILES "
            '["pyproject.toml","src/app/main.py","src/app/config.py"]\n'
            "[worktree_commit] OK: Rebased\n"
        )
        mock_result = _make_mock_result(stdout=mock_stdout, stderr="", returncode=0)

        from orch.daemon.project_registry import ProjectConfig

        project_config = ProjectConfig(
            id=test_project.id,
            display_name=test_project.display_name,
            repo_root="/repos/test",
            enabled=True,
            cli_tool="iw",
            model="minimax",
            worktree_base="/tmp/worktrees",
            config={},
        )

        with (
            patch("subprocess.run", return_value=mock_result),
            patch("orch.daemon.merge_queue.run_pre_merge_rebase") as mock_rebase,
            patch("orch.daemon.merge_queue.run_pre_merge_dry_run") as mock_dry,
            patch("orch.daemon.merge_queue.worktree_compose") as mock_compose,
            patch("orch.daemon.merge_queue.run_post_merge_apply") as mock_apply,
            patch("orch.daemon.merge_queue.run_rollback") as mock_rollback,
            patch("orch.daemon.batch_merge_hooks.trigger_doc_regeneration_on_merge"),
        ):
            mock_rebase.return_value = MagicMock(success=True)
            mock_dry.return_value = MagicMock(success=True)
            mock_compose.down = MagicMock()
            mock_apply.return_value = MagicMock(success=True)
            mock_rollback.return_value = MagicMock(success=True, frozen=False, message="ok")

            _merge_item(db_session, bi, test_project.id, project_config)

        db_session.refresh(bi)
        assert bi.merge_info is not None
        assert set(bi.merge_info["conflict_files"]) == {
            "pyproject.toml",
            "src/app/main.py",
            "src/app/config.py",
        }
