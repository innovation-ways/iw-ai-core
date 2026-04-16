"""Integration tests for ModuleGenerator.

All DB operations use testcontainers (NEVER the live platform DB on port 5433).
All Ollama HTTP calls and LanceDB operations are mocked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session


class TestModuleGeneratorIntegration:
    @pytest.mark.asyncio
    async def test_get_or_generate_creates_project_doc(
        self, db_session: Session, test_project, tmp_path: Path
    ):
        """Full cycle: generate Level 2, confirm ProjectDoc saved in DB"""
        from orch.db.models import DocTier, DocType, EditorialCategory, ProjectDoc
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.module_gen import ModuleGenerator

        config = CodeUnderstandingConfig()
        gen = ModuleGenerator()

        with (
            patch("orch.rag.module_gen.lancedb") as mock_lancedb,
            patch("orch.rag.module_gen.httpx.AsyncClient") as mock_httpx_cls,
            patch("orch.rag.module_gen.OllamaEmbedding") as mock_embed_cls,
        ):
            mock_table = MagicMock()
            mock_lancedb.connect.return_value = mock_table
            mock_table.search.return_value = mock_table
            mock_table.limit.return_value = mock_table
            mock_table.to_list = AsyncMock(return_value=[])

            mock_client = MagicMock()
            mock_httpx_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx_cls.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_post_response = MagicMock()
            mock_post_response.status_code = 200
            mock_post_response.json = MagicMock(return_value={"response": "Test answer for module"})
            mock_post_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_post_response)

            mock_embed = MagicMock()
            mock_embed.aget_text_embedding = AsyncMock(return_value=[0.1] * 384)
            mock_embed_cls.return_value = mock_embed

            doc, was_cached = await gen.get_or_generate(
                test_project.id, "engine/", "Engine", config, db_session
            )

            assert was_cached is False
            assert doc.slug == f"{test_project.id}-module-engine"
            assert doc.doc_type == DocType.research
            assert doc.tier == DocTier.fully_automated
            assert doc.editorial_category == EditorialCategory.technical
            assert "Module: Engine (engine/)" in doc.title

            db_session.commit()

            reloaded = db_session.get(ProjectDoc, doc.id)
            assert reloaded is not None
            assert reloaded.id == doc.id

    @pytest.mark.asyncio
    async def test_get_or_generate_returns_cached_on_second_call(
        self, db_session: Session, test_project, tmp_path: Path
    ):
        """Second call returns same doc without regenerating"""
        from orch.rag.config import CodeUnderstandingConfig
        from orch.rag.module_gen import ModuleGenerator

        config = CodeUnderstandingConfig()
        gen = ModuleGenerator()

        with (
            patch("orch.rag.module_gen.lancedb") as mock_lancedb,
            patch("orch.rag.module_gen.httpx.AsyncClient") as mock_httpx_cls,
            patch("orch.rag.module_gen.OllamaEmbedding") as mock_embed_cls,
        ):
            mock_table = MagicMock()
            mock_lancedb.connect.return_value = mock_table
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

            doc1, _ = await gen.get_or_generate(
                test_project.id, "engine/", "Engine", config, db_session
            )

            doc2, was_cached = await gen.get_or_generate(
                test_project.id, "engine/", "Engine", config, db_session
            )

            assert was_cached is True
            assert doc1.id == doc2.id
