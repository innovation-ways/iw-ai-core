# F-00045_S04_CodeReview_prompt

**Work Item**: F-00045 -- Code Understanding: Foundation
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/F-00045/F-00045_Feature_Design.md` — Design document
- `ai-dev/work/F-00045/reports/F-00045_S03_Backend_report.md` — S03 implementation report
- All files listed in the S03 report's `files_changed`:
  - `orch/rag/__init__.py`
  - `orch/rag/config.py`
  - `orch/config.py`
  - `tests/unit/test_rag_config.py`

## Output Files

- `ai-dev/work/F-00045/reports/F-00045_S04_CodeReview_report.md` — Review report

## Context

You are reviewing the backend implementation done in S03 by the backend-impl agent for **Code Understanding: Foundation (F-00045)**.

Read the design document to understand what was intended. Read the S03 report to understand what was done. Then review all changed files carefully.

---

## Review Checklist

### 1. orch/rag/__init__.py

- Is the file present and valid Python?
- Does it contain only a module docstring (no imports, no logic)?

### 2. orch/rag/config.py — Enums

- Is `CodeUnderstandingProvider` a `str, Enum` with `LOCAL = "local"` as the only value?
- Is `IndexTier` a `str, Enum` with `FAST = "fast"`, `BALANCED = "balanced"`, `QUALITY = "quality"`?
- Are both enums using `str` as a mixin (so `CodeUnderstandingProvider.LOCAL == "local"` is True)?

### 3. orch/rag/config.py — TIER_DEFAULTS

- Does `TIER_DEFAULTS` cover all three `IndexTier` values (FAST, BALANCED, QUALITY)?
- Are the default model names exactly:
  - FAST: `llm_model="gemma4:e4b"`, `embed_model="qwen3-embedding:8b"`
  - BALANCED: `llm_model="gemma4:26b"`, `embed_model="qwen3-embedding:8b"`
  - QUALITY: `llm_model="gemma4:31b"`, `embed_model="manutic/nomic-embed-code"`
- Is the type annotation `dict[IndexTier, dict[str, str]]`?

### 4. orch/rag/config.py — CodeUnderstandingConfig

- Does it extend `pydantic.BaseModel`?
- Are defaults: `provider=CodeUnderstandingProvider.LOCAL`, `index_tier=IndexTier.BALANCED`, `ollama_url="http://localhost:11434"`, `llm_model=None`, `embed_model=None`?
- Does `resolved_llm_model()` return `self.llm_model or TIER_DEFAULTS[self.index_tier]["llm_model"]`?
- Does `resolved_embed_model()` return `self.embed_model or TIER_DEFAULTS[self.index_tier]["embed_model"]`?
- Are both `resolved_*` methods annotated to return `str` (not `str | None`)?
- Is `from __future__ import annotations` present? (appropriate here, unlike `models.py`)

### 5. orch/config.py Changes

- Is `index_path: str = "~/.iw-ai-core/indexes"` added to `DaemonConfig`?
- Does `load_config()` read `IW_CORE_INDEX_PATH` with `os.environ.get("IW_CORE_INDEX_PATH", "~/.iw-ai-core/indexes")`?
- Is `_require()` NOT used for `IW_CORE_INDEX_PATH` (it must be optional with a default)?
- Are no other lines in `load_config()` changed?
- Is the `DaemonConfig` dataclass still frozen (`@dataclass(frozen=True)`)?

### 6. Unit Tests

- Is `tests/unit/test_rag_config.py` present?
- Do tests cover all required cases:
  - All three tiers for `resolved_llm_model()` (fast, balanced, quality)?
  - All three tiers for `resolved_embed_model()` (fast, balanced, quality)?
  - Explicit model override wins over tier default?
  - Invalid provider raises `ValidationError`?
  - Invalid tier raises `ValidationError`?
  - `IW_CORE_INDEX_PATH` absent → default value?
  - `IW_CORE_INDEX_PATH` set → custom value?
- Do `TestIndexPathConfig` tests import `load_config` inside the test function body?
- Do they use `monkeypatch.setenv` / `monkeypatch.delenv` (NOT `importlib.reload`)?
- Are tests free of DB access, containers, or network calls?

### 7. Design Document Compliance

Verify each acceptance criterion from the design document:
- AC4: FAST tier defaults (gemma4:e4b, qwen3-embedding:8b)
- AC5: Explicit override wins over tier default
- AC6: IW_CORE_INDEX_PATH optional with default
- AC7: Invalid provider raises ValidationError
- AC8: Invalid index_tier raises ValidationError

### 8. Code Quality

- No hardcoded credentials anywhere
- Imports are clean and organized
- Type annotations are present on all public functions and the `TIER_DEFAULTS` dict
- Docstrings are accurate

---

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run: `uv run pytest tests/unit/test_rag_config.py -v`
2. Run: `uv run ruff check orch/rag/ orch/config.py tests/unit/test_rag_config.py`
3. Run: `uv run mypy orch/rag/ orch/config.py`
4. Report actual pass/fail counts — do NOT assume tests pass

---

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

---

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "F-00045",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: Use `pass` if there are zero CRITICAL or HIGH findings AND zero MEDIUM (fixable) findings. Use `fail` if any mandatory fixes are needed.
- `mandatory_fix_count`: Count of CRITICAL + HIGH + MEDIUM (fixable) findings.
