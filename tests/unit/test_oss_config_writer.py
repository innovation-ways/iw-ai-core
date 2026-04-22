"""Tests for orch.oss.config_writer."""

from __future__ import annotations

from pathlib import Path

import pytest


class MockProject:
    def __init__(self, project_id: str, display_name: str, repo_root: str) -> None:
        self.id = project_id
        self.display_name = display_name
        self.repo_root = repo_root


class TestWriteProjectConfig:
    def test_writes_config_when_absent(self, tmp_path: Path) -> None:
        from orch.oss.config_writer import write_project_config

        proj = MockProject(project_id="test", display_name="Test Project", repo_root=str(tmp_path))
        result = write_project_config(proj)

        assert result == tmp_path / ".iw" / "oss-publish.toml"
        assert result.exists()

    def test_idempotent_when_identical_content(self, tmp_path: Path) -> None:
        from orch.oss.config_writer import write_project_config

        proj = MockProject(project_id="test", display_name="Test Project", repo_root=str(tmp_path))
        path1 = write_project_config(proj)
        path2 = write_project_config(proj)

        assert path1 == path2
        assert path1.exists()

    def test_raises_when_file_differs_and_not_forced(self, tmp_path: Path) -> None:
        from orch.oss.config_writer import ConfigFileExistsError, write_project_config

        proj = MockProject(project_id="test", display_name="Test Project", repo_root=str(tmp_path))
        (tmp_path / ".iw").mkdir()
        (tmp_path / ".iw" / "oss-publish.toml").write_text("# user edited content\n")

        with pytest.raises(ConfigFileExistsError):
            write_project_config(proj)

    def test_overwrites_when_forced(self, tmp_path: Path) -> None:
        from orch.oss.config_writer import write_project_config

        proj = MockProject(project_id="test", display_name="Test Project", repo_root=str(tmp_path))
        (tmp_path / ".iw").mkdir()
        (tmp_path / ".iw" / "oss-publish.toml").write_text("# user edited content\n")

        result = write_project_config(proj, force=True)
        assert result.exists()

    def test_creates_iw_directory(self, tmp_path: Path) -> None:
        from orch.oss.config_writer import write_project_config

        proj = MockProject(project_id="test", display_name="Test Project", repo_root=str(tmp_path))
        assert not (tmp_path / ".iw").exists()

        write_project_config(proj)

        assert (tmp_path / ".iw").exists()
        assert (tmp_path / ".iw" / "oss-publish.toml").exists()
