# F-00045_S03_Backend_prompt

**Work Item**: F-00045 -- Code Understanding: Foundation
**Step**: S03
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/F-00045/F-00045_Feature_Design.md` — Full design document
- `ai-dev/work/F-00045/reports/F-00045_S01_Database_report.md` — S01 report (understand what DB layer built)
- `orch/config.py` — Existing config (read before modifying)
- `orch/db/models.py` — Existing models (read to understand `CodeIndexJob` fields)

## Output Files

- `orch/rag/__init__.py` — New package marker
- `orch/rag/config.py` — Pydantic config models for Code Understanding
- `orch/config.py` — Updated with `IW_CORE_INDEX_PATH`
- `tests/unit/test_rag_config.py` — Unit tests for config models
- `ai-dev/work/F-00045/reports/F-00045_S03_Backend_report.md` — Step report

## Context

You are implementing the Python package skeleton and configuration models for **Code Understanding: Foundation (F-00045)**. Your job is to create the `orch/rag/` package with Pydantic config models and extend `orch/config.py` with the `IW_CORE_INDEX_PATH` setting.

Read `CLAUDE.md` and `orch/CLAUDE.md` before writing any code.

---

## Requirements

### 1. Create orch/rag/__init__.py

This file marks `orch/rag/` as a Python package. It should be empty (just a module docstring is fine):

```python
"""orch.rag — Code Understanding: indexing, retrieval, and generation support."""
```

No imports, no logic. Just the docstring.

### 2. Create orch/rag/config.py

Create the full Pydantic config module. Here is the complete expected implementation — implement exactly this:

```python
"""Configuration models for the Code Understanding feature.

Defines provider enums, tier enums, per-tier model defaults, and the
CodeUnderstandingConfig Pydantic model that validates the 'code_understanding'
block in a project's config JSONB column.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class CodeUnderstandingProvider(str, Enum):
    """Supported indexing providers. Only 'local' (Ollama) is supported in v1."""

    LOCAL = "local"


class IndexTier(str, Enum):
    """Index quality tier controlling model selection and indexing depth."""

    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


# Default LLM and embedding models per tier.
# These are used when the project config does not explicitly specify a model.
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
                "ollama_url": "http://localhost:11434"
            }
        }
    """

    provider: CodeUnderstandingProvider = CodeUnderstandingProvider.LOCAL
    llm_model: str | None = None
    embed_model: str | None = None
    index_tier: IndexTier = IndexTier.BALANCED
    ollama_url: str = "http://localhost:11434"

    def resolved_llm_model(self) -> str:
        """Return the effective LLM model: explicit value or tier default."""
        return self.llm_model or TIER_DEFAULTS[self.index_tier]["llm_model"]

    def resolved_embed_model(self) -> str:
        """Return the effective embedding model: explicit value or tier default."""
        return self.embed_model or TIER_DEFAULTS[self.index_tier]["embed_model"]
```

**Implementation notes**:
- Use `from __future__ import annotations` — this is a plain Python module, not an ORM model file
- Use `str | None` union type (Python 3.10+ style)
- `TIER_DEFAULTS` must cover all three `IndexTier` values — verify no `KeyError` is possible
- Both `resolved_*` methods must return `str` (never `None`)

### 3. Extend orch/config.py

Add `IW_CORE_INDEX_PATH` to `DaemonConfig`. This is an **optional** env var with a default — do NOT use `_require()`.

**Changes to make**:

In the `DaemonConfig` dataclass, add one new field after the existing fields (before the `projects_toml` field):

```python
# Code Understanding
index_path: str = "~/.iw-ai-core/indexes"
```

In the `load_config()` function body, pass the new field:

```python
index_path=os.environ.get("IW_CORE_INDEX_PATH", "~/.iw-ai-core/indexes"),
```

**CRITICAL**: `DaemonConfig` is a frozen dataclass. The field must have a default value so existing callers of `load_config()` that don't set `IW_CORE_INDEX_PATH` continue to work. Do NOT use `field(default_factory=...)` — a plain `str` default is correct here.

**Do not change** any other field in `DaemonConfig` or any other line in `load_config()`.

### 4. Unit Tests: tests/unit/test_rag_config.py

Create comprehensive unit tests. These are pure Python — no DB, no fixtures needed.

**TDD: Write tests FIRST (they will fail because `orch/rag/config.py` doesn't exist yet), then implement the module.**

Test file outline:

```python
"""Unit tests for orch.rag.config — CodeUnderstandingConfig Pydantic model."""

import pytest
from pydantic import ValidationError

from orch.rag.config import (
    CodeUnderstandingConfig,
    CodeUnderstandingProvider,
    IndexTier,
    TIER_DEFAULTS,
)


class TestCodeUnderstandingConfigDefaults:
    def test_default_provider_is_local(self): ...
    def test_default_index_tier_is_balanced(self): ...
    def test_default_llm_model_is_none(self): ...
    def test_default_embed_model_is_none(self): ...
    def test_default_ollama_url(self): ...


class TestResolvedLlmModel:
    def test_fast_tier_default(self): ...      # returns "gemma4:e4b"
    def test_balanced_tier_default(self): ...  # returns "gemma4:26b"
    def test_quality_tier_default(self): ...   # returns "gemma4:31b"
    def test_explicit_override_wins(self): ... # explicit "custom:7b" overrides tier


class TestResolvedEmbedModel:
    def test_fast_tier_default(self): ...      # returns "qwen3-embedding:8b"
    def test_balanced_tier_default(self): ...  # returns "qwen3-embedding:8b"
    def test_quality_tier_default(self): ...   # returns "manutic/nomic-embed-code"
    def test_explicit_override_wins(self): ... # explicit "my-embed:4b" overrides tier


class TestCodeUnderstandingConfigValidation:
    def test_invalid_provider_raises(self): ...     # provider="openai" → ValidationError
    def test_invalid_index_tier_raises(self): ...   # index_tier="ultra" → ValidationError
    def test_valid_provider_local(self): ...        # provider="local" succeeds
    def test_valid_tier_values(self): ...           # fast, balanced, quality all valid


class TestTierDefaults:
    def test_all_tiers_have_defaults(self): ...     # TIER_DEFAULTS covers all IndexTier values
    def test_no_none_in_defaults(self): ...         # no None values in TIER_DEFAULTS


class TestIndexPathConfig:
    def test_default_index_path(self, monkeypatch): ...
    # monkeypatch.delenv("IW_CORE_INDEX_PATH", raising=False)
    # from orch.config import load_config
    # cfg = load_config()
    # assert cfg.index_path == "~/.iw-ai-core/indexes"

    def test_custom_index_path(self, monkeypatch): ...
    # monkeypatch.setenv("IW_CORE_INDEX_PATH", "/data/indexes")
    # from orch.config import load_config
    # cfg = load_config()
    # assert cfg.index_path == "/data/indexes"
```

**CRITICAL for `TestIndexPathConfig`**: To test `load_config()` with env var changes, you MUST import `load_config` inside the test function body (not at module level) to avoid stale config state. Use `monkeypatch.setenv` / `monkeypatch.delenv` only — NEVER `importlib.reload(orch.config)`.

Also, `load_config()` requires other env vars to be present. Check `tests/conftest.py` to see if there's an existing fixture that sets all required env vars, or set them manually with `monkeypatch.setenv` in your test:

```python
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
    monkeypatch.setenv("IW_CORE_PID_FILE", "/tmp/test.pid")
    monkeypatch.setenv("IW_CORE_ARCHIVE_DIR", "/tmp/archive")
    monkeypatch.setenv("IW_CORE_ARCHIVE_TTL", "30")
    monkeypatch.setenv("IW_CORE_LOG_LEVEL", "INFO")
    monkeypatch.setenv("IW_CORE_LOG_FILE", "/tmp/test.log")
    from orch.config import load_config
    cfg = load_config()
    assert cfg.index_path == "~/.iw-ai-core/indexes"
```

---

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` before writing any code.

Key rules:
- `orch/rag/config.py` is a plain Python module — NOT an ORM model file. Use `from __future__ import annotations` here
- `orch/config.py` is a frozen dataclass — preserve the frozen=True attribute
- Unit tests live in `tests/unit/` — no containers, no DB
- NEVER use `importlib.reload(orch.config)` — use `monkeypatch` only
- Pydantic v2 is the project's Pydantic version — use `BaseModel` from `pydantic`

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write `tests/unit/test_rag_config.py` with all test functions as stubs — they will fail because `orch/rag/config.py` does not exist
2. **GREEN**: Create `orch/rag/__init__.py`, `orch/rag/config.py`, and update `orch/config.py` — tests should now pass
3. **REFACTOR**: Review for clarity, type annotations, docstrings

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run: `uv run pytest tests/unit/test_rag_config.py -v`
2. Run: `uv run ruff check orch/rag/ orch/config.py tests/unit/test_rag_config.py`
3. Run: `uv run ruff format --check orch/rag/ orch/config.py tests/unit/test_rag_config.py`
4. Run: `uv run mypy orch/rag/ orch/config.py`
5. Do NOT report `tests_passed: true` unless ALL tests pass with zero failures
6. Fix any type errors or lint issues before reporting completion

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00045",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/rag/__init__.py",
    "orch/rag/config.py",
    "orch/config.py",
    "tests/unit/test_rag_config.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
