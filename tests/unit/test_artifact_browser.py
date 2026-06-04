"""Unit tests for artifact browser helpers.

Tests _detect_file_type and _resolve_artifact_root.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

# ---------------------------------------------------------------------------
# Helpers under test
# ---------------------------------------------------------------------------


class TestDetectFileType:
    """Tests for _detect_file_type."""

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            # Markdown
            ("readme.md", "markdown"),
            ("CHANGELOG.MD", "markdown"),
            ("doc.Md", "markdown"),
            # Images
            ("screenshot.png", "image"),
            ("photo.JPG", "image"),
            ("diagram.jpeg", "image"),
            ("animation.gif", "image"),
            ("icon.webp", "image"),
            ("logo.svg", "image"),
            # Text / code
            ("output.txt", "text"),
            ("debug.log", "text"),
            ("config.json", "text"),
            ("data.yaml", "text"),
            ("settings.yml", "text"),
            ("build.sh", "text"),
            ("script.py", "text"),
            ("pyproject.toml", "text"),
            ("params.cfg", "text"),
            ("settings.ini", "text"),
            ("schema.sql", "text"),
            ("index.html", "text"),
            ("style.css", "text"),
            ("main.js", "text"),
            ("types.ts", "text"),
            ("feed.xml", "text"),
            (".env", "text"),
            # Binary — anything else
            ("archive.zip", "binary"),
            ("backup.tar", "binary"),
            ("backup.tar.gz", "binary"),
            ("document.pdf", "binary"),
            ("image.bmp", "binary"),
            ("data.csv", "binary"),
            ("no-extension", "binary"),
            ("COMPRESSED.ZST", "binary"),
            ("archive.7z", "binary"),
            ("", "binary"),
        ],
    )
    def test_detect_file_type(self, filename: str, expected: str) -> None:
        """Verifies that detect file type."""
        from dashboard.routers.items import _detect_file_type

        assert _detect_file_type(filename) == expected


class TestResolveArtifactRoot:
    """Tests for _resolve_artifact_root."""

    def test_returns_worktree_when_exists(self, tmp_path: Path) -> None:
        """Worktree path is preferred when it exists."""
        from dashboard.routers.items import _resolve_artifact_root

        # _resolve_artifact_root looks for: worktree_path / rel_dir
        # where rel_dir = Path(design_doc_path).parent = ai-dev/design/active/F-00010
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        # The full artifact root dir must exist for the function to find it
        artifact_root = worktree / "ai-dev" / "design" / "active" / "F-00010"
        artifact_root.mkdir(parents=True)

        item = SimpleNamespace(design_doc_path="ai-dev/design/active/F-00010/design.md")
        project = SimpleNamespace(repo_root=str(repo_root))
        result = _resolve_artifact_root(item, project, str(worktree))
        assert result == artifact_root

    def test_falls_back_to_repo_root(self, tmp_path: Path) -> None:
        """When worktree does NOT exist, falls back to repo_root."""
        from dashboard.routers.items import _resolve_artifact_root

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        artifact_root = repo_root / "ai-dev" / "design" / "active" / "F-00010"
        artifact_root.mkdir(parents=True)

        item = SimpleNamespace(design_doc_path="ai-dev/design/active/F-00010/design.md")
        project = SimpleNamespace(repo_root=str(repo_root))
        result = _resolve_artifact_root(item, project, None)
        assert result == artifact_root

    def test_returns_none_when_design_doc_path_is_none(self, tmp_path: Path) -> None:
        """When design_doc_path is None, returns None (no artifact root)."""
        from dashboard.routers.items import _resolve_artifact_root

        item = SimpleNamespace(design_doc_path=None)
        project = SimpleNamespace(repo_root=str(tmp_path))
        result = _resolve_artifact_root(item, project, None)
        assert result is None

    def test_returns_none_when_neither_exists(self, tmp_path: Path) -> None:
        """When neither worktree nor repo_root exists, returns None."""
        from dashboard.routers.items import _resolve_artifact_root

        item = SimpleNamespace(design_doc_path="ai-dev/design/active/F-00010/design.md")
        project = SimpleNamespace(repo_root=str(tmp_path / "nonexistent"))
        result = _resolve_artifact_root(item, project, None)
        assert result is None

    def test_worktree_preferred_over_repo_root(self, tmp_path: Path) -> None:
        """When BOTH exist, worktree is preferred."""
        from dashboard.routers.items import _resolve_artifact_root

        worktree = tmp_path / "worktree"
        worktree.mkdir()
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        worktree_root = worktree / "ai-dev" / "design" / "active" / "F-00010"
        worktree_root.mkdir(parents=True)
        repo_root_dir = repo_root / "ai-dev" / "design" / "active" / "F-00010"
        repo_root_dir.mkdir(parents=True)

        item = SimpleNamespace(design_doc_path="ai-dev/design/active/F-00010/design.md")
        project = SimpleNamespace(repo_root=str(repo_root))
        result = _resolve_artifact_root(item, project, str(worktree))
        assert result == worktree_root
