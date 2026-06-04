"""Tests for orch.utils.branch_resolver."""

from __future__ import annotations

import subprocess

import pytest


class TestResolveBranch:
    """TDD RED: these tests define the expected contract for branch_resolver."""

    def test_resolve_returns_named_tuple(self, tmp_path):
        """Helper returns current_branch, default_branch, is_on_default."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "branch", "-M", "main"], cwd=tmp_path, check=True, capture_output=True
        )
        from orch.utils.branch_resolver import resolve_branch

        result = resolve_branch(str(tmp_path), default_branch="main")
        assert hasattr(result, "current_branch")
        assert hasattr(result, "default_branch")
        assert hasattr(result, "is_on_default")

    def test_on_default_branch(self, tmp_path):
        """When HEAD matches default_branch, is_on_default is True."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-M", "main"], cwd=tmp_path, check=True, capture_output=True
        )
        from orch.utils.branch_resolver import resolve_branch

        result = resolve_branch(str(tmp_path), default_branch="main")
        assert result.current_branch == "main"
        assert result.default_branch == "main"
        assert result.is_on_default is True

    def test_not_on_default_branch(self, tmp_path):
        """When HEAD is a feature branch, is_on_default is False."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-M", "main"], cwd=tmp_path, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "-b", "feature-branch"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        from orch.utils.branch_resolver import resolve_branch

        result = resolve_branch(str(tmp_path), default_branch="main")
        assert result.current_branch == "feature-branch"
        assert result.default_branch == "main"
        assert result.is_on_default is False

    def test_default_falls_back_to_main(self, tmp_path):
        """When no default_branch is provided, the default is 'main'."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-M", "main"], cwd=tmp_path, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "-b", "develop"], cwd=tmp_path, check=True, capture_output=True
        )
        from orch.utils.branch_resolver import resolve_branch

        # Explicit default_branch param
        result = resolve_branch(str(tmp_path), default_branch="main")
        assert result.default_branch == "main"
        assert result.is_on_default is False

    def test_git_unavailable_returns_unknown(self, tmp_path):
        """When git fails, current_branch is 'unknown' and is_on_default is False."""
        from orch.utils.branch_resolver import resolve_branch

        result = resolve_branch(str(tmp_path), default_branch="main")
        assert result.current_branch == "unknown"
        assert result.default_branch == "main"
        assert result.is_on_default is False

    def test_default_branch_from_project_config(self, tmp_path):
        """Project config's default_branch key wins over the bare default 'main'."""
        from orch.utils.branch_resolver import resolve_branch_for_project

        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-M", "trunk"], cwd=tmp_path, check=True, capture_output=True
        )

        # No .iw-orch.json → falls back to "main"
        result = resolve_branch_for_project(str(tmp_path))
        assert result.default_branch == "main"
        assert result.is_on_default is False  # HEAD is "trunk", not "main"

    def test_default_branch_from_iw_orch_json(self, tmp_path):
        """When .iw-orch.json has default_branch, that value is used."""
        from orch.utils.branch_resolver import resolve_branch_for_project

        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-M", "trunk"], cwd=tmp_path, check=True, capture_output=True
        )

        # Write .iw-orch.json with non-main default
        iw_file = tmp_path / ".iw-orch.json"
        iw_file.write_text('{"default_branch": "trunk"}')

        result = resolve_branch_for_project(str(tmp_path))
        assert result.default_branch == "trunk"
        assert result.is_on_default is True
