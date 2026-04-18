"""Unit tests for orch.rag.config — CodeUnderstandingConfig Pydantic model."""

import pytest
from pydantic import ValidationError

from orch.rag.config import (
    TIER_DEFAULTS,
    CodeUnderstandingConfig,
    CodeUnderstandingProvider,
    IndexTier,
)


class TestCodeUnderstandingConfigDefaults:
    def test_default_provider_is_local(self):
        config = CodeUnderstandingConfig()
        assert config.provider == CodeUnderstandingProvider.LOCAL

    def test_default_index_tier_is_balanced(self):
        config = CodeUnderstandingConfig()
        assert config.index_tier == IndexTier.BALANCED

    def test_default_llm_model_is_none(self):
        config = CodeUnderstandingConfig()
        assert config.llm_model is None

    def test_default_embed_model_is_none(self):
        config = CodeUnderstandingConfig()
        assert config.embed_model is None

    def test_default_ollama_url(self):
        config = CodeUnderstandingConfig()
        assert config.ollama_url == "http://localhost:11434"


class TestResolvedLlmModel:
    def test_fast_tier_default(self):
        config = CodeUnderstandingConfig(index_tier=IndexTier.FAST)
        assert config.resolved_llm_model() == "gemma4:e4b"

    def test_balanced_tier_default(self):
        config = CodeUnderstandingConfig(index_tier=IndexTier.BALANCED)
        assert config.resolved_llm_model() == "gemma4:26b"

    def test_quality_tier_default(self):
        config = CodeUnderstandingConfig(index_tier=IndexTier.QUALITY)
        assert config.resolved_llm_model() == "gemma4:31b"

    def test_explicit_override_wins(self):
        config = CodeUnderstandingConfig(index_tier=IndexTier.FAST, llm_model="custom:7b")
        assert config.resolved_llm_model() == "custom:7b"


class TestResolvedEmbedModel:
    def test_fast_tier_default(self):
        config = CodeUnderstandingConfig(index_tier=IndexTier.FAST)
        assert config.resolved_embed_model() == "qwen3-embedding:8b"

    def test_balanced_tier_default(self):
        config = CodeUnderstandingConfig(index_tier=IndexTier.BALANCED)
        assert config.resolved_embed_model() == "qwen3-embedding:8b"

    def test_quality_tier_default(self):
        config = CodeUnderstandingConfig(index_tier=IndexTier.QUALITY)
        assert config.resolved_embed_model() == "manutic/nomic-embed-code"

    def test_explicit_override_wins(self):
        config = CodeUnderstandingConfig(index_tier=IndexTier.BALANCED, embed_model="my-embed:4b")
        assert config.resolved_embed_model() == "my-embed:4b"


class TestCodeUnderstandingConfigValidation:
    def test_invalid_provider_raises(self):
        with pytest.raises(ValidationError):
            CodeUnderstandingConfig(provider="openai")  # type: ignore[arg-type]

    def test_invalid_index_tier_raises(self):
        with pytest.raises(ValidationError):
            CodeUnderstandingConfig(index_tier="ultra")  # type: ignore[arg-type]

    def test_valid_provider_local(self):
        config = CodeUnderstandingConfig(provider="local")
        assert config.provider == CodeUnderstandingProvider.LOCAL

    def test_valid_tier_values(self):
        for tier in [IndexTier.FAST, IndexTier.BALANCED, IndexTier.QUALITY]:
            config = CodeUnderstandingConfig(index_tier=tier)
            assert config.index_tier == tier


class TestTierDefaults:
    def test_all_tiers_have_defaults(self):
        for tier in IndexTier:
            assert tier in TIER_DEFAULTS
            assert "llm_model" in TIER_DEFAULTS[tier]
            assert "embed_model" in TIER_DEFAULTS[tier]

    def test_no_none_in_defaults(self):
        for tier_data in TIER_DEFAULTS.values():
            assert tier_data["llm_model"] is not None
            assert tier_data["embed_model"] is not None


class TestIndexPathConfig:
    def test_default_index_path(self, monkeypatch):
        monkeypatch.delenv("IW_CORE_INDEX_PATH", raising=False)
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "testdb")
        monkeypatch.setenv("IW_CORE_DB_USER", "test")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "test")
        monkeypatch.setenv("IW_CORE_DASHBOARD_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DASHBOARD_PORT", "9900")
        monkeypatch.setenv("IW_CORE_POLL_INTERVAL", "60")
        monkeypatch.setenv("IW_CORE_STALL_THRESHOLD", "300")
        monkeypatch.setenv("IW_CORE_PID_FILE", "/tmp/test.pid")  # noqa: S108
        monkeypatch.setenv("IW_CORE_ARCHIVE_DIR", "/tmp/archive")  # noqa: S108
        monkeypatch.setenv("IW_CORE_ARCHIVE_TTL", "30")
        monkeypatch.setenv("IW_CORE_LOG_LEVEL", "INFO")
        monkeypatch.setenv("IW_CORE_LOG_FILE", "/tmp/test.log")  # noqa: S108
        from orch.config import load_config

        cfg = load_config()
        from orch.rag.config import DEFAULT_INDEX_PATH

        assert cfg.index_path == DEFAULT_INDEX_PATH

    def test_custom_index_path(self, monkeypatch):
        monkeypatch.setenv("IW_CORE_INDEX_PATH", "/data/indexes")
        monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_NAME", "testdb")
        monkeypatch.setenv("IW_CORE_DB_USER", "test")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "test")
        monkeypatch.setenv("IW_CORE_DASHBOARD_HOST", "localhost")
        monkeypatch.setenv("IW_CORE_DASHBOARD_PORT", "9900")
        monkeypatch.setenv("IW_CORE_POLL_INTERVAL", "60")
        monkeypatch.setenv("IW_CORE_STALL_THRESHOLD", "300")
        monkeypatch.setenv("IW_CORE_PID_FILE", "/tmp/test.pid")  # noqa: S108
        monkeypatch.setenv("IW_CORE_ARCHIVE_DIR", "/tmp/archive")  # noqa: S108
        monkeypatch.setenv("IW_CORE_ARCHIVE_TTL", "30")
        monkeypatch.setenv("IW_CORE_LOG_LEVEL", "INFO")
        monkeypatch.setenv("IW_CORE_LOG_FILE", "/tmp/test.log")  # noqa: S108
        from orch.config import load_config

        cfg = load_config()
        assert cfg.index_path == "/data/indexes"
