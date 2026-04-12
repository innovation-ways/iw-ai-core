"""Unit tests for artifact browser helpers.

Tests _detect_file_type, _resolve_artifact_root, and _build_artifact_tree.
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


class TestBuildArtifactTree:
    """Tests for _build_artifact_tree."""

    def test_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        """Empty artifact directory returns []."""
        from dashboard.routers.items import _build_artifact_tree

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        result = _build_artifact_tree(subdir, subdir)
        assert result == []

    def test_flat_files_only(self, tmp_path: Path) -> None:
        """Flat list of files — correct names, sizes, types, no children."""
        from dashboard.routers.items import _build_artifact_tree

        root = tmp_path / "root"
        root.mkdir()
        (root / "a.txt").write_text("hello")
        (root / "b.md").write_text("# Title")
        (root / "c.png").write_bytes(b"\x89PNG")

        result = _build_artifact_tree(root, root)

        assert len(result) == 3
        names = [n.name for n in result]
        assert names == ["a.txt", "b.md", "c.png"]
        # Files sorted alphabetically
        assert result[0].name == "a.txt"
        assert result[1].name == "b.md"
        assert result[2].name == "c.png"
        for node in result:
            assert node.is_dir is False
            assert node.children == []
            assert node.file_type != "directory"

    def test_directories_first_then_files(self, tmp_path: Path) -> None:
        """Dirs sorted first, then files — both alphabetical within group."""
        from dashboard.routers.items import _build_artifact_tree

        root = tmp_path / "root"
        root.mkdir()
        (root / "zebra.txt").write_text("z")
        (root / "apple.txt").write_text("a")
        (root / "beta").mkdir()
        (root / "alpha").mkdir()

        result = _build_artifact_tree(root, root)

        assert len(result) == 4
        names = [n.name for n in result]
        # Dirs first (alpha, beta), then files (apple, zebra)
        assert names == ["alpha", "beta", "apple.txt", "zebra.txt"]
        assert result[0].is_dir is True
        assert result[1].is_dir is True
        assert result[2].is_dir is False
        assert result[3].is_dir is False

    def test_nested_subdirectories(self, tmp_path: Path) -> None:
        """Recursive tree — subdirs have children, correct rel_path values."""
        from dashboard.routers.items import _build_artifact_tree

        root = tmp_path / "root"
        root.mkdir()
        (root / "prompts").mkdir()
        (root / "prompts" / "feature.md").write_text("# Feature")
        (root / "reports").mkdir()
        (root / "reports" / "summary.txt").write_text("summary")

        result = _build_artifact_tree(root, root)

        assert len(result) == 2
        # prompts and reports dirs
        assert result[0].name == "prompts"
        assert result[0].is_dir is True
        assert result[0].file_type == "directory"
        assert len(result[0].children) == 1
        assert result[0].children[0].name == "feature.md"
        assert result[0].children[0].rel_path == "prompts/feature.md"

        assert result[1].name == "reports"
        assert result[1].is_dir is True
        assert len(result[1].children) == 1
        assert result[1].children[0].name == "summary.txt"
        assert result[1].children[0].rel_path == "reports/summary.txt"

    def test_rel_path_correct_for_deeply_nested(self, tmp_path: Path) -> None:
        """rel_path is correct for deeply nested files."""
        from dashboard.routers.items import _build_artifact_tree

        root = tmp_path / "root"
        root.mkdir()
        (root / "a").mkdir()
        (root / "a" / "b").mkdir()
        (root / "a" / "b" / "c").mkdir()
        (root / "a" / "b" / "c" / "deep.md").write_text("# Deep")

        result = _build_artifact_tree(root, root)

        # Walk the tree to verify deep nesting
        node = result[0]  # 'a'
        assert node.name == "a"
        assert node.rel_path == "a"
        node = node.children[0]  # 'b'
        assert node.name == "b"
        assert node.rel_path == "a/b"
        node = node.children[0]  # 'c'
        assert node.name == "c"
        assert node.rel_path == "a/b/c"
        node = node.children[0]  # 'deep.md'
        assert node.name == "deep.md"
        assert node.rel_path == "a/b/c/deep.md"
        assert node.file_type == "markdown"

    def test_file_type_detection(self, tmp_path: Path) -> None:
        """Correct file_type on leaf nodes."""
        from dashboard.routers.items import _build_artifact_tree

        root = tmp_path / "root"
        root.mkdir()
        (root / "readme.md").write_text("# Title")
        (root / "image.png").write_bytes(b"\x89PNG")
        (root / "data.json").write_text("{}")
        (root / "archive.zip").write_bytes(b"PK")

        result = _build_artifact_tree(root, root)

        types = {n.name: n.file_type for n in result}
        assert types["readme.md"] == "markdown"
        assert types["image.png"] == "image"
        assert types["data.json"] == "text"
        assert types["archive.zip"] == "binary"

    def test_size_bytes_set(self, tmp_path: Path) -> None:
        """Leaf nodes have correct size_bytes."""
        from dashboard.routers.items import _build_artifact_tree

        root = tmp_path / "root"
        root.mkdir()
        (root / "small.txt").write_text("hi")
        (root / "large.txt").write_text("hello world")

        result = _build_artifact_tree(root, root)

        sizes = {n.name: n.size_bytes for n in result}
        assert sizes["small.txt"] == 2
        assert sizes["large.txt"] == 11

    def test_directory_size_bytes_zero(self, tmp_path: Path) -> None:
        """Directory nodes have size_bytes = 0."""
        from dashboard.routers.items import _build_artifact_tree

        root = tmp_path / "root"
        root.mkdir()
        (root / "subdir").mkdir()
        (root / "file.txt").write_text("x")

        result = _build_artifact_tree(root, root)

        for node in result:
            if node.is_dir:
                assert node.size_bytes == 0

    def test_abs_path_is_absolute(self, tmp_path: Path) -> None:
        """abs_path is the absolute path on disk."""
        from dashboard.routers.items import _build_artifact_tree

        root = tmp_path / "root"
        root.mkdir()
        (root / "file.md").write_text("# Title")

        result = _build_artifact_tree(root, root)

        assert result[0].abs_path == str(root / "file.md")
        assert Path(result[0].abs_path).is_absolute()
