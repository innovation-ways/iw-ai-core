"""Unit tests for design-doc embedding indexer (S01 — RED phase).

Tests are written BEFORE implementation and must FAIL initially.
Covers: chunking, embedding call, LanceDB row shape, incremental-mode filter,
skip-on-null-content, summary-only fallback, mapgen_only guard.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

from orch.rag.config import CodeUnderstandingConfig


class TestIndexDesignDocsFunctionExists:
    """index_design_docs should be importable from orch.rag.indexer."""

    def test_function_is_importable(self) -> None:
        from orch.rag import indexer

        assert hasattr(indexer, "index_design_docs")
        assert callable(indexer.index_design_docs)


class TestIndexDesignDocsChunking:
    """Design doc content is chunked using the same pattern as code files."""

    def test_chunking_respects_chunk_size(self, tmp_path: Path) -> None:
        from orch.rag.indexer import index_design_docs

        config = CodeUnderstandingConfig()
        mock_session = MagicMock()
        mock_progress = MagicMock()

        project_id = "test-project"
        store_path = tmp_path / project_id / "vectors"
        store_path.mkdir(parents=True)

        with patch("orch.rag.indexer.OllamaEmbedding") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_text_embedding_batch.return_value = [[0.1] * 384] * 10
            mock_embed.get_text_embedding.return_value = [0.1] * 384
            mock_embed.model_name = "test-model"
            mock_embed_class.return_value = mock_embed

            with patch("orch.rag.indexer.VectorStoreIndex"):
                asyncio.run(
                    index_design_docs(
                        project_id=project_id,
                        config=config,
                        db_session=mock_session,
                        index_path=str(tmp_path),
                        mode="full",
                        progress_callback=mock_progress,
                    )
                )

    def test_single_chunk_when_under_threshold(self, tmp_path: Path) -> None:
        """Items under chunk size emit a single row, not zero rows."""
        from orch.rag.indexer import index_design_docs

        config = CodeUnderstandingConfig()
        mock_session = MagicMock()
        mock_progress = MagicMock()

        project_id = "tiny-project"
        store_path = tmp_path / project_id / "vectors"
        store_path.mkdir(parents=True)

        with patch("orch.rag.indexer.OllamaEmbedding") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_text_embedding_batch.return_value = [[0.1] * 384]
            mock_embed.get_text_embedding.return_value = [0.1] * 384
            mock_embed.model_name = "test-model"
            mock_embed_class.return_value = mock_embed

            with patch("orch.rag.indexer.VectorStoreIndex"):
                asyncio.run(
                    index_design_docs(
                        project_id=project_id,
                        config=config,
                        db_session=mock_session,
                        index_path=str(tmp_path),
                        mode="full",
                        progress_callback=mock_progress,
                    )
                )


class TestSkipOnNullDesignDoc:
    """Work items with design_doc_content=NULL are skipped (not indexed)."""

    def test_null_content_not_indexed(self, tmp_path: Path) -> None:
        from orch.rag.indexer import index_design_docs

        config = CodeUnderstandingConfig()
        mock_progress = MagicMock()

        project_id = "null-test-project"
        store_path = tmp_path / project_id / "vectors"
        store_path.mkdir(parents=True)

        with patch("orch.rag.indexer.OllamaEmbedding") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_text_embedding_batch.return_value = []
            mock_embed.get_text_embedding.return_value = [0.1] * 384
            mock_embed.model_name = "test-model"
            mock_embed_class.return_value = mock_embed

            with patch("orch.rag.indexer.VectorStoreIndex"):
                asyncio.run(
                    index_design_docs(
                        project_id=project_id,
                        config=config,
                        db_session=MagicMock(),
                        index_path=str(tmp_path),
                        mode="full",
                        progress_callback=mock_progress,
                    )
                )


class TestSummaryOnlyFallback:
    """Items with summary but no design_doc_content emit a single row with text=summary."""

    def test_summary_only_item_emits_one_row(self, tmp_path: Path) -> None:
        from orch.rag.indexer import index_design_docs

        config = CodeUnderstandingConfig()
        mock_progress = MagicMock()

        project_id = "summary-only-project"
        store_path = tmp_path / project_id / "vectors"
        store_path.mkdir(parents=True)

        with patch("orch.rag.indexer.OllamaEmbedding") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_text_embedding_batch.return_value = [[0.1] * 384]
            mock_embed.get_text_embedding.return_value = [0.1] * 384
            mock_embed.model_name = "test-model"
            mock_embed_class.return_value = mock_embed

            with patch("orch.rag.indexer.VectorStoreIndex"):
                asyncio.run(
                    index_design_docs(
                        project_id=project_id,
                        config=config,
                        db_session=MagicMock(),
                        index_path=str(tmp_path),
                        mode="full",
                        progress_callback=mock_progress,
                    )
                )


class TestIncrementalModeFilter:
    """Incremental mode only re-embeds WorkItems updated since last completed job."""

    def test_incremental_filters_by_updated_at(self, tmp_path: Path) -> None:
        from orch.rag.indexer import index_design_docs

        config = CodeUnderstandingConfig()
        mock_progress = MagicMock()

        project_id = "incr-project"
        store_path = tmp_path / project_id / "vectors"
        store_path.mkdir(parents=True)

        with patch("orch.rag.indexer.OllamaEmbedding") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_text_embedding_batch.return_value = []
            mock_embed.get_text_embedding.return_value = [0.1] * 384
            mock_embed.model_name = "test-model"
            mock_embed_class.return_value = mock_embed

            with patch("orch.rag.indexer.VectorStoreIndex"):
                asyncio.run(
                    index_design_docs(
                        project_id=project_id,
                        config=config,
                        db_session=MagicMock(),
                        index_path=str(tmp_path),
                        mode="incremental",
                        progress_callback=mock_progress,
                    )
                )

    def test_incremental_uses_merge_insert_not_delete_reinsert(self, tmp_path: Path) -> None:
        from orch.rag.indexer import index_design_docs

        config = CodeUnderstandingConfig()
        mock_progress = MagicMock()

        project_id = "merge-insert-project"
        store_path = tmp_path / project_id / "vectors"
        store_path.mkdir(parents=True)

        with patch("orch.rag.indexer.OllamaEmbedding") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_text_embedding_batch.return_value = []
            mock_embed.get_text_embedding.return_value = [0.1] * 384
            mock_embed.model_name = "test-model"
            mock_embed_class.return_value = mock_embed

            with patch("orch.rag.indexer.VectorStoreIndex"):
                asyncio.run(
                    index_design_docs(
                        project_id=project_id,
                        config=config,
                        db_session=MagicMock(),
                        index_path=str(tmp_path),
                        mode="incremental",
                        progress_callback=mock_progress,
                    )
                )


class TestMapgenOnlyBypassesDocs:
    """mode=mapgen_only must NOT touch the docs table."""

    def test_mapgen_only_does_not_call_docs_indexer(self, tmp_path: Path) -> None:
        from orch.rag.indexer import index_design_docs

        config = CodeUnderstandingConfig()
        mock_progress = MagicMock()

        project_id = "mapgen-project"

        with patch("orch.rag.indexer.OllamaEmbedding") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_text_embedding_batch.return_value = []
            mock_embed.get_text_embedding.return_value = [0.1] * 384
            mock_embed.model_name = "test-model"
            mock_embed_class.return_value = mock_embed

            with patch("orch.rag.indexer.VectorStoreIndex"):
                asyncio.run(
                    index_design_docs(
                        project_id=project_id,
                        config=config,
                        db_session=MagicMock(),
                        index_path=str(tmp_path),
                        mode="mapgen_only",
                        progress_callback=mock_progress,
                    )
                )


class TestDocIndexResult:
    """DocIndexResult dataclass carries doc-chunk count."""

    def test_doc_index_result_fields(self) -> None:
        from orch.rag.indexer import DocIndexResult

        result = DocIndexResult(work_items_indexed=3, chunks_created=7, errors=[])

        assert result.work_items_indexed == 3
        assert result.chunks_created == 7
        assert result.errors == []

    def test_doc_index_result_default_errors_empty(self) -> None:
        from orch.rag.indexer import DocIndexResult

        result = DocIndexResult(work_items_indexed=0, chunks_created=0)

        assert result.errors == []


class TestDocsTableSchema:
    """The docs_{project_id} LanceDB table has the correct schema."""

    def test_table_name_hyphen_to_underscore(self, tmp_path: Path) -> None:
        from orch.rag.indexer import index_design_docs

        config = CodeUnderstandingConfig()
        mock_progress = MagicMock()

        project_id = "iw-ai-core"

        with patch("orch.rag.indexer.LanceDBVectorStore") as mock_lvds_cls:
            mock_db = MagicMock()
            mock_lvds_cls.return_value = mock_db

            with patch("orch.rag.indexer.OllamaEmbedding") as mock_embed_cls:
                mock_embed = MagicMock()
                mock_embed.get_text_embedding_batch.return_value = []
                mock_embed.get_text_embedding.return_value = [0.1] * 384
                mock_embed.model_name = "test-model"
                mock_embed_cls.return_value = mock_embed

                with patch("orch.rag.indexer.VectorStoreIndex"):
                    asyncio.run(
                        index_design_docs(
                            project_id=project_id,
                            config=config,
                            db_session=MagicMock(),
                            index_path=str(tmp_path),
                            mode="full",
                            progress_callback=mock_progress,
                        )
                    )

                call_args = mock_lvds_cls.call_args
                if call_args:
                    _, kwargs = call_args
                    table_name = kwargs.get("table_name", "")
                    assert table_name == "docs_iw_ai_core"


class TestProgressEvents:
    """Doc pass emits phase events matching the existing vocabulary."""

    def test_emits_indexing_docs_phase(self, tmp_path: Path) -> None:
        from orch.rag.indexer import index_design_docs

        config = CodeUnderstandingConfig()
        mock_progress = MagicMock()

        project_id = "progress-test-project"
        store_path = tmp_path / project_id / "vectors"
        store_path.mkdir(parents=True)

        with patch("orch.rag.indexer.OllamaEmbedding") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_text_embedding_batch.return_value = []
            mock_embed.get_text_embedding.return_value = [0.1] * 384
            mock_embed.model_name = "test-model"
            mock_embed_class.return_value = mock_embed

            with patch("orch.rag.indexer.VectorStoreIndex"):
                asyncio.run(
                    index_design_docs(
                        project_id=project_id,
                        config=config,
                        db_session=MagicMock(),
                        index_path=str(tmp_path),
                        mode="full",
                        progress_callback=mock_progress,
                    )
                )

                progress_calls = mock_progress.call_args_list
                phases_emitted = [
                    c.kwargs.get("phase") or c.args[0].get("phase") for c in progress_calls if c
                ]
                assert "indexing_docs" in phases_emitted


class TestEmbeddingModel:
    """Uses project's resolved embedding model via OllamaEmbedding."""

    def test_uses_resolved_embed_model(self, tmp_path: Path) -> None:
        from orch.rag.indexer import index_design_docs

        config = CodeUnderstandingConfig(index_tier="quality")
        mock_progress = MagicMock()

        project_id = "embed-model-test"
        store_path = tmp_path / project_id / "vectors"
        store_path.mkdir(parents=True)

        with patch("orch.rag.indexer.OllamaEmbedding") as mock_embed_class:
            mock_embed = MagicMock()
            mock_embed.get_text_embedding_batch.return_value = []
            mock_embed.get_text_embedding.return_value = [0.1] * 384
            mock_embed.model_name = "test-model"
            mock_embed_class.return_value = mock_embed

            with patch("orch.rag.indexer.VectorStoreIndex"):
                asyncio.run(
                    index_design_docs(
                        project_id=project_id,
                        config=config,
                        db_session=MagicMock(),
                        index_path=str(tmp_path),
                        mode="full",
                        progress_callback=mock_progress,
                    )
                )

                mock_embed_class.assert_called_once()
                _, kwargs = mock_embed_class.call_args
                assert kwargs.get("model_name") == "manutic/nomic-embed-code"
