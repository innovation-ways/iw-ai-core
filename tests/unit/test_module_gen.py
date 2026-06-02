"""Unit tests for ModuleGenerator.

RED phase — tests are written BEFORE implementation and must FAIL initially.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orch.db.models import DocTier, DocType, EditorialCategory, ProjectDoc
from orch.rag.config import CodeUnderstandingConfig


@pytest.fixture
def config():
    """Provide config for tests."""
    return CodeUnderstandingConfig()


@pytest.fixture
def mock_session():
    """Provide mock session for tests."""
    return MagicMock()


class TestModuleGeneratorMakeSlug:
    """Tests for ModuleGeneratorMakeSlug scenarios."""

    def test_make_slug_simple(self):
        """Verifies that make slug simple."""
        from orch.rag.module_gen import ModuleGenerator

        gen = ModuleGenerator()
        assert gen._make_slug("my-project", "engine/") == "my-project-module-engine"

    def test_make_slug_nested(self):
        """Verifies that make slug nested."""
        from orch.rag.module_gen import ModuleGenerator

        gen = ModuleGenerator()
        assert (
            gen._make_slug("my-project", "src/engine/core/") == "my-project-module-src-engine-core"
        )


class TestModuleGeneratorGetOrGenerate:
    """Tests for ModuleGeneratorGetOrGenerate scenarios."""

    @pytest.mark.asyncio
    async def test_get_or_generate_cache_hit(self, config, mock_session):
        """When ProjectDoc exists, get_or_generate returns it with was_cached=True"""
        from orch.rag.module_gen import ModuleGenerator

        mock_doc = MagicMock(spec=ProjectDoc)
        mock_doc.slug = "proj-module-engine"

        gen = ModuleGenerator()
        with patch.object(gen, "_get_by_slug", return_value=mock_doc):
            doc, was_cached = await gen.get_or_generate(
                "proj", "engine/", "Engine", config, mock_session
            )

            assert was_cached is True
            assert doc is mock_doc

    @pytest.mark.asyncio
    async def test_get_or_generate_cache_miss_calls_generate(self, config, mock_session):
        """When ProjectDoc does not exist, get_or_generate calls generate_level2"""
        from orch.rag.module_gen import ModuleGenerator

        gen = ModuleGenerator()
        with (
            patch.object(gen, "_get_by_slug", return_value=None),
            patch.object(gen, "generate_level2", new_callable=AsyncMock) as mock_generate,
        ):
            mock_doc = MagicMock(spec=ProjectDoc)
            mock_generate.return_value = mock_doc

            doc, was_cached = await gen.get_or_generate(
                "proj", "engine/", "Engine", config, mock_session
            )

            assert was_cached is False
            mock_generate.assert_called_once()


class TestModuleGeneratorGenerateLevel2:
    """Tests for ModuleGeneratorGenerateLevel2 scenarios."""

    @pytest.mark.asyncio
    async def test_generate_level2_assembles_markdown(self, config, mock_session):
        """generate_level2 assembles markdown from 5 question answers"""
        from orch.rag.module_gen import ModuleGenerator

        gen = ModuleGenerator()

        with (
            patch("orch.rag.module_gen.lancedb.connect") as mock_lancedb_connect,
            patch("orch.rag.module_gen.httpx.AsyncClient") as mock_httpx_cls,
            patch("orch.rag.module_gen.OllamaEmbedding") as mock_embed_cls,
            # F-00064 added _generate_and_store_module_diagram, which constructs
            # llama_index's Ollama LLM and calls .complete() — bypassing the
            # patched httpx client. Without this mock, the test hits the real
            # local Ollama (or its connection timeout) and takes 20-30s.
            patch("orch.rag.module_gen.Ollama") as mock_llm_cls,
        ):
            mock_table = MagicMock()
            mock_lancedb_connect.return_value.open_table.return_value = mock_table
            mock_table.search.return_value = mock_table
            mock_table.limit.return_value = mock_table
            mock_table.to_list = AsyncMock(return_value=[])

            mock_client = MagicMock()
            mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_post_response = MagicMock()
            mock_post_response.status_code = 200
            mock_post_response.json = MagicMock(return_value={"response": "Test answer"})
            mock_post_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_post_response)

            mock_embed = MagicMock()
            mock_embed.aget_text_embedding = AsyncMock(return_value=[0.1] * 384)
            mock_embed_cls.return_value = mock_embed

            mock_llm_response = MagicMock()
            mock_llm_response.text = (
                "```mermaid\n---\nconfig:\n  layout: elk\n---\n"
                "graph LR\n  A[Engine]\n```\n\n"
                "```purpose\nEngine module overview.\n```"
            )
            mock_llm_cls.return_value.complete = MagicMock(return_value=mock_llm_response)

            doc = await gen.generate_level2("proj", "engine/", "Engine", config, mock_session)

            assert doc is not None
            assert doc.doc_type == DocType.research
            assert doc.tier == DocTier.fully_automated
            assert doc.editorial_category == EditorialCategory.technical
            assert "Module: Engine (engine/)" in doc.title
