"""Unit tests for git_log_resolver module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestParseWorkItemIdFromCommitLine:
    """Tests for parse_work_item_id_from_commit_line function."""

    def test_parses_feature_merge(self) -> None:
        """Merge F-NNNNN: pattern is parsed correctly."""
        from orch.rag.git_log_resolver import parse_work_item_id_from_commit_line

        line = "Merge F-00042: Add new feature"
        result = parse_work_item_id_from_commit_line(line)
        assert result == "F-00042"

    def test_parses_change_request_merge(self) -> None:
        """Merge CR-NNNNN: pattern is parsed correctly."""
        from orch.rag.git_log_resolver import parse_work_item_id_from_commit_line

        line = "Merge CR-00123: Refactor module X"
        result = parse_work_item_id_from_commit_line(line)
        assert result == "CR-00123"

    def test_parses_incident_merge(self) -> None:
        """Merge I-NNNNN: pattern is parsed correctly."""
        from orch.rag.git_log_resolver import parse_work_item_id_from_commit_line

        line = "Merge I-00555: Fix critical bug"
        result = parse_work_item_id_from_commit_line(line)
        assert result == "I-00555"

    def test_returns_none_for_non_matching_line(self) -> None:
        """Non-matching commit lines return None."""
        from orch.rag.git_log_resolver import parse_work_item_id_from_commit_line

        line = "abc123def Add some feature"
        result = parse_work_item_id_from_commit_line(line)
        assert result is None

    def test_returns_none_for_merge_without_id(self) -> None:
        """Merge without work-item ID returns None."""
        from orch.rag.git_log_resolver import parse_work_item_id_from_commit_line

        line = "Merge branch 'main' into feature"
        result = parse_work_item_id_from_commit_line(line)
        assert result is None

    def test_handles_line_pre_dating_convention(self) -> None:
        """Lines from before the convention (no ID) return None."""
        from orch.rag.git_log_resolver import parse_work_item_id_from_commit_line

        lines = [
            "Initial commit",
            "Add README",
            "Fix typo in docs",
        ]
        for line in lines:
            result = parse_work_item_id_from_commit_line(line)
            assert result is None, f"Expected None for '{line}'"


class TestResolveWorkItemsForFiles:
    """Tests for resolve_work_items_for_files function."""

    def test_empty_file_list(self) -> None:
        """Empty file list returns empty dict."""
        from orch.rag.git_log_resolver import resolve_work_items_for_files

        result = resolve_work_items_for_files([], repo_root=Path("/fake/repo"))
        assert result == {}

    @patch("subprocess.run")
    def test_single_file_with_merge_commits(self, mock_run: MagicMock) -> None:
        """Single file with merge commits returns deduped IDs."""
        from orch.rag.git_log_resolver import resolve_work_items_for_files

        mock_run.return_value = MagicMock(
            stdout="Merge F-00001: Add feature A\nMerge CR-00002: Refactor\nabc123def Fix typo",
            stderr="",
            returncode=0,
        )

        result = resolve_work_items_for_files(
            ["path/to/file.py"],
            repo_root=Path("/fake/repo"),
        )

        assert result["path/to/file.py"] == ["F-00001", "CR-00002"]

    @patch("subprocess.run")
    def test_deduplicates_ids(self, mock_run: MagicMock) -> None:
        """Same ID appearing in multiple commits is deduplicated."""
        from orch.rag.git_log_resolver import resolve_work_items_for_files

        mock_run.return_value = MagicMock(
            stdout="Merge F-00001: Add feature\nMerge F-00001: Update feature",
            stderr="",
            returncode=0,
        )

        result = resolve_work_items_for_files(
            ["path/to/file.py"],
            repo_root=Path("/fake/repo"),
        )

        assert result["path/to/file.py"] == ["F-00001"]

    @patch("subprocess.run")
    def test_multiple_files(self, mock_run: MagicMock) -> None:
        """Multiple files each get their own list of IDs."""
        from orch.rag.git_log_resolver import resolve_work_items_for_files

        def side_effect(*args, **kwargs):
            """Return side effect."""
            cmd = args[0]
            file_arg = cmd[cmd.index("--") + 1] if "--" in cmd else ""
            if "file1" in file_arg:
                return MagicMock(stdout="Merge F-00001: Add\n", stderr="", returncode=0)
            return MagicMock(stdout="Merge CR-00002: Change\n", stderr="", returncode=0)

        mock_run.side_effect = side_effect

        result = resolve_work_items_for_files(
            ["path/to/file1.py", "path/to/file2.py"],
            repo_root=Path("/fake/repo"),
        )

        assert len(result) == 2

    @patch("subprocess.run")
    def test_subprocess_timeout(self, mock_run: MagicMock) -> None:
        """Subprocess timeout returns empty list for that file."""
        from orch.rag.git_log_resolver import resolve_work_items_for_files

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git log", timeout=10)

        result = resolve_work_items_for_files(
            ["path/to/file.py"],
            repo_root=Path("/fake/repo"),
        )

        assert result["path/to/file.py"] == []

    @patch("subprocess.run")
    def test_subprocess_error(self, mock_run: MagicMock) -> None:
        """Subprocess error returns empty list for that file."""
        from orch.rag.git_log_resolver import resolve_work_items_for_files

        mock_run.side_effect = OSError("git not found")

        result = resolve_work_items_for_files(
            ["path/to/file.py"],
            repo_root=Path("/fake/repo"),
        )

        assert result["path/to/file.py"] == []

    @patch("subprocess.run")
    def test_preserves_order_of_first_seen(self, mock_run: MagicMock) -> None:
        """IDs are returned in order of first appearance."""
        from orch.rag.git_log_resolver import resolve_work_items_for_files

        mock_run.return_value = MagicMock(
            stdout="Merge F-00003: Third\nMerge F-00001: First\nMerge F-00002: Second",
            stderr="",
            returncode=0,
        )

        result = resolve_work_items_for_files(
            ["path/to/file.py"],
            repo_root=Path("/fake/repo"),
        )

        assert result["path/to/file.py"] == ["F-00003", "F-00001", "F-00002"]

    @patch("subprocess.run")
    def test_uses_shell_false(self, mock_run: MagicMock) -> None:
        """subprocess.run is called with shell=False for security."""
        from orch.rag.git_log_resolver import resolve_work_items_for_files

        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        resolve_work_items_for_files(["file.py"], repo_root=Path("/repo"))

        call_args = mock_run.call_args
        assert call_args[1].get("shell", True) is False, (
            "shell should be False to prevent injection"
        )
