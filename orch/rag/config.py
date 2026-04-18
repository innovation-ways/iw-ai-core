"""Configuration models for the Code Understanding feature.

Defines provider enums, tier enums, per-tier model defaults, and the
CodeUnderstandingConfig Pydantic model that validates the 'code_understanding'
block in a project's config JSONB column.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

DEFAULT_INDEX_PATH: str = str(Path.home() / ".local" / "share" / "iw-ai-core" / "code-index")


class CodeUnderstandingProvider(StrEnum):
    """Supported indexing providers. Only 'local' (Ollama) is supported in v1."""

    LOCAL = "local"


class IndexTier(StrEnum):
    """Index quality tier controlling model selection and indexing depth."""

    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


TIER_DEFAULTS: dict[IndexTier, dict[str, str]] = {
    IndexTier.FAST: {
        "llm_model": "gemma4:e4b",
        "embed_model": "qwen3-embedding:8b",
    },
    IndexTier.BALANCED: {
        "llm_model": "gemma4:26b",
        "embed_model": "qwen3-embedding:8b",
    },
    IndexTier.QUALITY: {
        "llm_model": "gemma4:31b",
        "embed_model": "manutic/nomic-embed-code",
    },
}


class CodeUnderstandingConfig(BaseModel):
    """Validates the 'code_understanding' block in a project's config JSONB column.

    Example project config:
        {
            "code_understanding": {
                "provider": "local",
                "llm_model": null,
                "embed_model": null,
                "index_tier": "balanced",
                "ollama_url": "http://localhost:11434",
                "index_path": "/var/lib/iw-ai/core/code-index"
            }
        }
    """

    provider: CodeUnderstandingProvider = CodeUnderstandingProvider.LOCAL
    llm_model: str | None = None
    embed_model: str | None = None
    index_tier: IndexTier = IndexTier.BALANCED
    ollama_url: str = "http://localhost:11434"
    index_path: str = DEFAULT_INDEX_PATH

    def resolved_llm_model(self) -> str:
        """Return the effective LLM model: explicit value or tier default."""
        return self.llm_model or TIER_DEFAULTS[self.index_tier]["llm_model"]

    def resolved_embed_model(self) -> str:
        """Return the effective embedding model: explicit value or tier default."""
        return self.embed_model or TIER_DEFAULTS[self.index_tier]["embed_model"]


def build_code_config_from_project(
    project_config: dict[str, Any] | None,
    fallback_index_path: str | None = None,
) -> CodeUnderstandingConfig:
    """Build a CodeUnderstandingConfig from a project's `config` JSONB.

    Applies `fallback_index_path` when the project does not pin its own
    `index_path`, so the read side (Q&A, modules) and the write side (indexer)
    agree on where the LanceDB table lives.
    """
    code_cfg = dict((project_config or {}).get("code_understanding", {}) or {})
    if fallback_index_path and not code_cfg.get("index_path"):
        code_cfg["index_path"] = fallback_index_path
    return CodeUnderstandingConfig(**code_cfg)
