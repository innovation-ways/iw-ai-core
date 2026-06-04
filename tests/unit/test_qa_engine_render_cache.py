"""Unit tests for QAEngine render cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest


class MockWorkItem:
    """Mock WorkItem for testing."""

    def __init__(self, wi_id: str, created_at: datetime) -> None:
        self.id = wi_id
        self.type = MagicMock(value="Feature")
        self.title = f"Test {wi_id}"
        self.summary = "Test summary"
        self.design_doc_content = "Test content"
        self.created_at = created_at


class TestRenderCache:
    """Tests for the render cache on QAEngine."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock CodeUnderstandingConfig."""
        config = MagicMock()
        config.resolved_embed_model.return_value = "qwen3-embedding:8b"
        config.resolved_llm_model.return_value = "gemma4:26b"
        config.ollama_url = "http://localhost:11434"
        config.index_path = "test-index"
        return config

    @pytest.fixture
    def engine(self, mock_config: MagicMock):
        """Create a QAEngine instance."""
        from orch.rag.qa import QAEngine

        return QAEngine(project_id="test-project", config=mock_config)

    def test_cache_put_and_get(self, engine) -> None:
        """Basic cache put and get works."""
        from orch.rag.evidence import CodeChunk, EvidenceBundle

        bundle = EvidenceBundle(
            question="test question",
            code_chunks=[CodeChunk("file.py", "code")],
            doc_chunks=[],
            work_items=[],
        )

        render_id = "test-render-id"
        engine._cache_put(render_id, bundle, "test question")

        result = engine._cache_get(render_id)

        assert result is not None
        assert result.question == "test question"

    def test_cache_miss_returns_none(self, engine) -> None:
        """Non-existent render_id returns None."""
        result = engine._cache_get("non-existent-id")
        assert result is None

    def test_expired_entry_returns_none(self, engine) -> None:
        """Expired cache entry returns None and is evicted."""
        from orch.rag.evidence import EvidenceBundle

        bundle = EvidenceBundle(question="test", work_items=[])

        render_id = "expired-id"

        with engine._render_cache_lock:
            engine._render_cache[render_id] = (
                datetime.now(UTC) - timedelta(minutes=15),
                bundle,
                "test question",
            )

        result = engine._cache_get(render_id)

        assert result is None
        with engine._render_cache_lock:
            assert render_id not in engine._render_cache

    def test_lru_ordering(self, engine) -> None:
        """Most recently accessed entries are kept when at capacity."""
        from orch.rag.evidence import EvidenceBundle

        mock_bundle = MagicMock(spec=EvidenceBundle)
        mock_bundle.question = "test"

        render_ids = [f"render-{i}" for i in range(10)]

        for rid in render_ids[:7]:
            with engine._render_cache_lock:
                engine._render_cache[rid] = (
                    datetime.now(UTC),
                    mock_bundle,
                    "test",
                )

        engine._cache_get(render_ids[0])

        with engine._render_cache_lock:
            assert render_ids[0] in engine._render_cache

        assert len(engine._render_cache) == 7

    def test_capacity_enforcement(self, engine) -> None:
        """Cache does not exceed RENDER_CACHE_MAX (64)."""
        from orch.rag.evidence import EvidenceBundle

        mock_bundle = MagicMock(spec=EvidenceBundle)
        mock_bundle.question = "test"

        for i in range(70):
            with engine._render_cache_lock:
                engine._render_cache[f"render-{i}"] = (
                    datetime.now(UTC),
                    mock_bundle,
                    "test",
                )
            engine._evict_expired_locked()
            if len(engine._render_cache) > 64:
                engine._render_cache.popitem(last=False)

        with engine._render_cache_lock:
            assert len(engine._render_cache) <= 64

    def test_cache_put_evicts_expired(self, engine) -> None:
        """Putting new entry evicts expired entries."""
        from orch.rag.evidence import EvidenceBundle

        old_bundle = EvidenceBundle(question="old", work_items=[])
        new_bundle = EvidenceBundle(question="new", work_items=[])

        with engine._render_cache_lock:
            engine._render_cache["old-id"] = (
                datetime.now(UTC) - timedelta(minutes=20),
                old_bundle,
                "old",
            )
            engine._render_cache["new-id"] = (
                datetime.now(UTC),
                new_bundle,
                "new",
            )

        engine._cache_put("another-id", new_bundle, "test")

        with engine._render_cache_lock:
            assert "old-id" not in engine._render_cache
            assert "new-id" in engine._render_cache


class TestRenderCacheMaxAndTTL:
    """Tests for RENDER_CACHE_MAX and RENDER_CACHE_TTL constants."""

    def test_render_cache_max_is_64(self) -> None:
        """RENDER_CACHE_MAX is set to 64."""
        from orch.rag.qa import RENDER_CACHE_MAX

        assert RENDER_CACHE_MAX == 64

    def test_render_cache_ttl_is_10_minutes(self) -> None:
        """RENDER_CACHE_TTL is set to 10 minutes."""
        from orch.rag.qa import RENDER_CACHE_TTL

        assert timedelta(minutes=10) == RENDER_CACHE_TTL
