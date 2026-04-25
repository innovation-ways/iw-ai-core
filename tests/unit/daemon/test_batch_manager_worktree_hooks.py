"""Unit tests for batch_manager worktree lifecycle hooks.

Tests the compose up/down lifecycle integration in _launch_item:
  - test_setup_calls_compose_up_when_iw_config_present
  - test_setup_skips_compose_when_iw_config_absent_legacy_mode
  - test_setup_failure_transitions_to_setup_failed_status
  - test_terminal_transition_calls_compose_down
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from orch.daemon.batch_manager import BatchManager, WorktreeSetupError
from orch.db.models import BatchItem, BatchItemStatus, WorkItemStatus


class TestWorktreeLifecycleHooks:
    """Tests for worktree compose lifecycle integration in _launch_item."""

    def _make_batch_item(self, work_item_id: str = "F-00001") -> MagicMock:
        item = MagicMock(spec=BatchItem)
        item.work_item_id = work_item_id
        item.id = 123
        item.status = BatchItemStatus.pending
        item.started_at = None
        item.worktree_info = None
        item.worktree_db_port = None
        item.worktree_app_port = None
        item.worktree_compose_path = None
        return item

    def _make_work_item(self) -> MagicMock:
        wi = MagicMock()
        wi.status = WorkItemStatus.approved
        return wi

    def _make_project_config(self, tmp_path: Path) -> MagicMock:
        from orch.daemon.project_registry import ProjectConfig

        cfg = MagicMock(spec=ProjectConfig)
        cfg.id = "test-proj"
        cfg.project_id = "test-proj"
        cfg.working_dir = str(tmp_path / "repo")
        cfg.worktree_base = ".worktrees"
        cfg.cli_tool = "opencode"
        return cfg

    def _make_manager(self, tmp_path: Path, db: MagicMock) -> BatchManager:
        from orch.config import DaemonConfig

        config = MagicMock(spec=DaemonConfig)
        config.baseline_qv_enabled = False
        cfg = self._make_project_config(tmp_path)
        return BatchManager("test-proj", cfg, lambda: db, config)

    def test_setup_calls_compose_up_when_iw_config_present(self, tmp_path: Path) -> None:
        db = MagicMock()
        batch_item = self._make_batch_item()
        work_item = self._make_work_item()
        db.query.return_value.filter_by.return_value.one.return_value = work_item

        worktree_path = tmp_path / ".worktrees" / "F-00001"
        worktree_path.mkdir(parents=True)
        iw_config = worktree_path / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)
        (iw_config / "worktree-compose.template.yml").write_text(
            "services:\n  db:\n    image: postgres"
        )
        (worktree_path / ".gitignore").write_text(".env\n.iw/\n")
        (worktree_path / ".env").write_text("FOO=bar\n")

        fake_info = {"path": str(worktree_path), "branch": "agent/F-00001", "created_at": "now"}

        manager = self._make_manager(tmp_path, db)

        up_result = MagicMock()
        up_result.success = True
        up_result.discovered_ports = {"IW_CORE_DB_PORT": 54321}
        up_result.error_message = None
        up_result.seed_stderr_tail = None

        with (
            patch.object(manager, "_setup_worktree", return_value=fake_info),
            patch("orch.daemon.batch_manager.worktree_compose.has_iw_config", return_value=True),
            patch("orch.daemon.batch_manager.worktree_compose.load_config"),
            patch(
                "orch.daemon.batch_manager.worktree_compose.up", return_value=up_result
            ) as mock_up,
        ):
            manager._launch_item(db, batch_item)

        mock_up.assert_called_once()
        assert batch_item.status == BatchItemStatus.executing
        assert batch_item.worktree_compose_path is not None
        assert batch_item.worktree_db_port == 54321

    def test_setup_skips_compose_when_iw_config_absent_legacy_mode(self, tmp_path: Path) -> None:
        db = MagicMock()
        batch_item = self._make_batch_item()
        work_item = self._make_work_item()
        db.query.return_value.filter_by.return_value.one.return_value = work_item

        worktree_path = tmp_path / ".worktrees" / "F-00001"
        worktree_path.mkdir(parents=True)
        (worktree_path / ".gitignore").write_text(".env\n.iw/\n")

        fake_info = {"path": str(worktree_path), "branch": "agent/F-00001", "created_at": "now"}

        manager = self._make_manager(tmp_path, db)

        with (
            patch.object(manager, "_setup_worktree", return_value=fake_info),
            patch("orch.daemon.batch_manager.worktree_compose.has_iw_config", return_value=False),
        ):
            manager._launch_item(db, batch_item)

        assert batch_item.status == BatchItemStatus.executing
        assert batch_item.worktree_compose_path is None
        assert batch_item.worktree_db_port is None
        assert batch_item.worktree_app_port is None

    def test_setup_failure_transitions_to_setup_failed_status(self, tmp_path: Path) -> None:
        db = MagicMock()
        batch_item = self._make_batch_item()
        work_item = self._make_work_item()
        db.query.return_value.filter_by.return_value.one.return_value = work_item

        manager = self._make_manager(tmp_path, db)

        with patch.object(manager, "_setup_worktree", side_effect=WorktreeSetupError("disk full")):
            manager._launch_item(db, batch_item)

        assert batch_item.status == BatchItemStatus.setup_failed
        assert "disk full" in batch_item.notes
        assert work_item.status == WorkItemStatus.failed

    def test_compose_up_failure_transitions_to_setup_failed(self, tmp_path: Path) -> None:
        db = MagicMock()
        batch_item = self._make_batch_item()
        work_item = self._make_work_item()
        db.query.return_value.filter_by.return_value.one.return_value = work_item

        worktree_path = tmp_path / ".worktrees" / "F-00001"
        worktree_path.mkdir(parents=True)
        iw_config = worktree_path / "ai-dev" / "iw-config"
        iw_config.mkdir(parents=True)
        (iw_config / "worktree-compose.template.yml").write_text(
            "services:\n  db:\n    image: postgres"
        )
        (worktree_path / ".gitignore").write_text(".env\n.iw/\n")
        (worktree_path / ".env").write_text("FOO=bar\n")

        fake_info = {"path": str(worktree_path), "branch": "agent/F-00001", "created_at": "now"}

        manager = self._make_manager(tmp_path, db)

        up_result = MagicMock()
        up_result.success = False
        up_result.error_message = "port conflict"
        up_result.seed_stderr_tail = "some seed error"

        mock_cfg = MagicMock()
        mock_cfg.rendered_compose_path = Path(worktree_path / ".iw" / "docker-compose-123.yml")

        with (
            patch.object(manager, "_setup_worktree", return_value=fake_info),
            patch("orch.daemon.batch_manager.worktree_compose.has_iw_config", return_value=True),
            patch("orch.daemon.batch_manager.worktree_compose.load_config", return_value=mock_cfg),
            patch("orch.daemon.batch_manager.worktree_compose.up", return_value=up_result),
            patch("orch.daemon.batch_manager.worktree_compose.down"),
        ):
            manager._launch_item(db, batch_item)

        assert batch_item.status == BatchItemStatus.setup_failed
        assert "Compose up failed" in batch_item.notes
        assert batch_item.worktree_compose_path is None


class TestTerminalTransitionComposeDown:
    """Tests that compose down is called on terminal state transitions."""

    def test_terminal_transition_calls_compose_down(self, tmp_path: Path) -> None:
        from orch.daemon.merge_queue import _merge_item
        from orch.daemon.project_registry import ProjectConfig

        db = MagicMock()
        item = MagicMock()
        item.work_item_id = "F-00001"
        item.status = BatchItemStatus.completed
        item.started_at = datetime(2024, 1, 1, tzinfo=UTC)
        item.worktree_info = {"path": str(tmp_path / "wt")}
        item.worktree_compose_path = str(tmp_path / "wt" / ".iw" / "docker-compose-123.yml")
        item.id = 123
        item.batch_id = 42
        item.notes = None
        item.merge_info = None
        item.merged_at = None

        project_cfg = MagicMock(spec=ProjectConfig)
        project_cfg.id = "test-proj"
        project_cfg.working_dir = str(tmp_path)

        with (
            patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
            patch("orch.daemon.merge_queue.worktree_compose.down") as mock_down,
            patch("orch.daemon.merge_queue._cleanup_worktree"),
            patch("orch.daemon.merge_queue.run_pre_merge_rebase") as mock_rebase,
            patch("orch.daemon.merge_queue.run_pre_merge_dry_run") as mock_dry_run,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            mock_rebase.return_value = MagicMock(success=True)
            mock_dry_run.return_value = MagicMock(success=True)
            _merge_item(db, item, "test-proj", project_cfg)

        assert item.status == BatchItemStatus.merged
        mock_down.assert_called_once()
