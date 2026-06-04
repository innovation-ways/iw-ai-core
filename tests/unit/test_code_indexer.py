"""Unit tests for CodeIndexer, MapGenerator, and CodeIndexJobRunner.

RED phase — tests are written BEFORE implementation and must FAIL initially.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from orch.rag.config import CodeUnderstandingConfig


class TestComputeSha:
    """Tests for ComputeSha scenarios."""

    def test_compute_sha_consistent(self, tmp_path: Path) -> None:
        """Verifies that compute sha consistent."""
        from orch.rag.indexer import CodeIndexer

        config = CodeUnderstandingConfig()
        indexer = CodeIndexer(
            project_id="test-project",
            config=config,
            index_path=str(tmp_path),
        )
        file_path = tmp_path / "file.py"
        file_path.write_text("hello world")

        sha1 = indexer._compute_sha(file_path)
        sha2 = indexer._compute_sha(file_path)

        assert sha1 == sha2
        assert len(sha1) == 64

    def test_compute_sha_differs(self, tmp_path: Path) -> None:
        """Verifies that compute sha differs."""
        from orch.rag.indexer import CodeIndexer

        config = CodeUnderstandingConfig()
        indexer = CodeIndexer(
            project_id="test-project",
            config=config,
            index_path=str(tmp_path),
        )
        file_a = tmp_path / "a.py"
        file_b = tmp_path / "b.py"
        file_a.write_text("hello world")
        file_b.write_text("goodbye world")

        sha_a = indexer._compute_sha(file_a)
        sha_b = indexer._compute_sha(file_b)

        assert sha_a != sha_b


class TestManifest:
    """Tests for Manifest scenarios."""

    def test_manifest_roundtrip(self, tmp_path: Path) -> None:
        """Verifies that manifest roundtrip."""
        from orch.rag.indexer import CodeIndexer

        config = CodeUnderstandingConfig()
        indexer = CodeIndexer(
            project_id="test-project",
            config=config,
            index_path=str(tmp_path),
        )
        original = {
            "src/main.py": "abc123",
            "src/utils.py": "def456",
        }
        indexer._save_manifest(original)
        loaded = indexer._load_manifest()

        assert loaded == original

    def test_manifest_missing_returns_empty(self, tmp_path: Path) -> None:
        """Verifies that manifest missing returns empty."""
        from orch.rag.indexer import CodeIndexer

        config = CodeUnderstandingConfig()
        indexer = CodeIndexer(
            project_id="test-project",
            config=config,
            index_path=str(tmp_path),
        )
        manifest = indexer._load_manifest()

        assert manifest == {}


class TestGetChangedFiles:
    """Tests for GetChangedFiles scenarios."""

    def test_get_changed_files_all_changed(self, tmp_path: Path) -> None:
        """Verifies that get changed files all changed."""
        from orch.rag.indexer import CodeIndexer

        config = CodeUnderstandingConfig()
        indexer = CodeIndexer(
            project_id="test-project",
            config=config,
            index_path=str(tmp_path),
        )
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")
        (tmp_path / "src" / "utils.py").write_text("def foo(): pass")

        changed = indexer._get_changed_files(str(tmp_path / "src"), {})

        assert len(changed) == 2
        assert all(isinstance(p, Path) for p in changed)

    def test_get_changed_files_no_change(self, tmp_path: Path) -> None:
        """Verifies that get changed files no change."""
        from orch.rag.indexer import CodeIndexer

        config = CodeUnderstandingConfig()
        indexer = CodeIndexer(
            project_id="test-project",
            config=config,
            index_path=str(tmp_path),
        )
        (tmp_path / "src").mkdir()
        py_file = tmp_path / "src" / "main.py"
        py_file.write_text("print('hello')")

        current_sha = indexer._compute_sha(py_file)
        manifest = {str(py_file): current_sha}

        changed = indexer._get_changed_files(str(tmp_path / "src"), manifest)

        assert changed == []

    def test_get_changed_files_partial(self, tmp_path: Path) -> None:
        """Verifies that get changed files partial."""
        from orch.rag.indexer import CodeIndexer

        config = CodeUnderstandingConfig()
        indexer = CodeIndexer(
            project_id="test-project",
            config=config,
            index_path=str(tmp_path),
        )
        (tmp_path / "src").mkdir()
        main = tmp_path / "src" / "main.py"
        utils = tmp_path / "src" / "utils.py"
        main.write_text("print('hello')")
        utils.write_text("def foo(): pass")

        old_sha = indexer._compute_sha(main)
        manifest = {str(main): old_sha}

        changed = indexer._get_changed_files(str(tmp_path / "src"), manifest)

        assert len(changed) == 1
        assert changed[0].name == "utils.py"


class TestMermaid:
    """Tests for Mermaid scenarios."""

    def test_build_mermaid_contains_graph_td(self, tmp_path: Path) -> None:
        """Verifies that build mermaid contains graph td."""
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.mapgen import MapGenerator

        mock_response = MagicMock()
        mock_response.text = "```mermaid\ngraph TD\n  A[main.py] --> B[utils.py]\n```"

        with patch("orch.rag.mapgen.Ollama") as mock_ollama_class:
            mock_llm = MagicMock()
            mock_llm.complete.return_value = mock_response
            mock_ollama_class.return_value = mock_llm

            gen = MapGenerator()
            dsl, _purpose = gen._build_mermaid(
                "main.py -> utils.py -> database", CodeUnderstandingConfig()
            )

        assert "graph TD" in dsl


class TestAssembleMarkdown:
    """Tests for AssembleMarkdown scenarios."""

    def test_assemble_markdown_contains_all_sections(self, tmp_path: Path) -> None:
        """Verifies that assemble markdown contains all sections."""
        from orch.rag.mapgen import MapGenerator

        gen = MapGenerator()
        answers = {
            "purpose": "A web server.",
            "components": "Router, Handler.",
            "entry_points": "main.py.",
            "databases": "PostgreSQL.",
            "external_services": "None.",
            "background_jobs": "None.",
            "architecture_style": "Layered.",
            "key_patterns": "MVC.",
        }
        mermaid = "graph TD\n  A[System]"
        purpose = "Test purpose."
        md = gen._assemble_markdown(answers, mermaid, purpose)

        for key in answers:
            assert f"## {key.replace('_', ' ').title()}" in md or f"## {key}" in md


class TestIndexResult:
    """Tests for IndexResult scenarios."""

    def test_index_result_dataclass(self) -> None:
        """Verifies that index result dataclass."""
        from orch.rag.indexer import IndexResult

        result = IndexResult(
            files_indexed=5,
            chunks_created=20,
            files_skipped=0,
            errors=[],
        )

        assert result.files_indexed == 5
        assert result.chunks_created == 20
        assert result.files_skipped == 0
        assert result.errors == []

    def test_index_result_defaults_for_new_fields(self) -> None:
        """Verifies that index result defaults for new fields."""
        from orch.rag.indexer import IndexResult

        result = IndexResult(
            files_indexed=5,
            chunks_created=20,
            files_skipped=0,
        )

        assert result.files_discovered == 0
        assert result.languages_detected == []
        assert result.errors == []

    def test_index_result_accepts_discovery_and_languages(self) -> None:
        """Verifies that index result accepts discovery and languages."""
        from orch.rag.indexer import IndexResult

        result = IndexResult(
            files_indexed=10,
            chunks_created=40,
            files_skipped=2,
            files_discovered=12,
            languages_detected=["python", "cpp"],
            errors=["some error"],
        )

        assert result.files_discovered == 12
        assert result.languages_detected == ["python", "cpp"]
        assert result.errors == ["some error"]
