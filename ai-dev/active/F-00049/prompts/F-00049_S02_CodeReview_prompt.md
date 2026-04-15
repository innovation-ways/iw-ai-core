# F-00049_S02_CodeReview_prompt

**Work Item**: F-00049 — Code Understanding: Q&A Panel (SSE Streaming)
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/F-00049/F-00049_Feature_Design.md` — Design document
- `ai-dev/work/F-00049/reports/F-00049_S01_Backend_report.md` — S01 implementation report
- All files listed in the S01 report's `files_changed`:
  - `orch/rag/qa.py`
  - `tests/unit/test_qa_engine.py`

## Output Files

- `ai-dev/work/F-00049/reports/F-00049_S02_CodeReview_report.md` — Review report

---

## Context

You are reviewing the backend implementation done in S01 by the backend-impl agent for **F-00049: Code Understanding Q&A Panel**. Your goal is to ensure `QAEngine` is correct, testable, and safe to build upon in S03 (API layer).

Read the design document thoroughly. Read the S01 report. Then read all changed files carefully before writing findings.

---

## Review Checklist

### 1. Architecture Compliance

- Is `QAEngine` in `orch/rag/qa.py` (not in a router or template)?
- Is `answer_stream()` an `async def` function that is also a generator (uses `yield`)?
- Is `answer_stream()` typed as returning `AsyncGenerator[str, None]`?
- Does the class carry `TOP_K = 8` and `MAX_HISTORY_TURNS = 5` as class-level constants?
- Does `__init__` accept only `project_id: str` and `config: CodeUnderstandingConfig`?
- Is `module_path: str | None = None` present as a parameter on `answer_stream()`?
- Does `_truncate_history()` return the last `MAX_HISTORY_TURNS * 2` messages?
- Is conversation history never stored as instance state (stateless engine)?

### 2. LanceDB Integration

- Is the LanceDB table name derived as `f"code_{project_id.replace('-', '_')}"` (matches F-00046 convention)?
- Is the LanceDB index path derived from `config.index_path` (no hardcoding)?
- When `context_level == "module"` and `module_path` is provided, is a metadata filter applied to the LanceDB query?
- When `context_level == "architecture"`, is no filter applied (full index search)?
- Is the vector query using `TOP_K = 8` as the limit?

### 3. Embedding and LLM Usage

- Is `OllamaEmbedding` used with `config.resolved_embed_model()` (no hardcoded model name)?
- Is `OllamaLLM` used with `config.resolved_chat_model()` (no hardcoded model name)?
- Is `config.ollama_base_url` passed to both Ollama clients?
- Is `astream_chat()` (async streaming) used, not `chat()` (blocking)?

### 4. System Prompt Construction

- Does `_build_system_prompt()` include the context doc content when non-empty?
- Does it substitute a placeholder when `context_doc_content == ""`?
- Does it include retrieved chunk text?
- Does it end with a clear instruction to answer the question about the codebase?

### 5. Conversation History

- Is `_truncate_history()` called before building the LlamaIndex message list?
- Is the truncated history correctly converted to `ChatMessage` objects with `role="user"` or `role="assistant"`?
- Is the system prompt injected as the first message (role="system")?
- Is the current question added as the final user message?

### 6. Error Handling

- Is `httpx.ConnectError` caught (or `ConnectionRefusedError`) around the Ollama LLM call?
- On connection error: does the generator yield a token starting with `"__ERROR__:"` and then return (not re-raise)?
- Are there no bare `except Exception` blocks that swallow all errors silently?

### 7. Imports and Code Quality

- Is `from __future__ import annotations` present at the top of `qa.py`?
- Are type-only imports (`AsyncSession`) guarded by `TYPE_CHECKING`?
- Are there no unused imports?
- Is the module free of hardcoded credentials, ports, or model names?

### 8. Test Quality

- Are all 8 required test cases from the S01 prompt implemented?
  - `_build_system_prompt` with content
  - `_build_system_prompt` with empty content
  - `_truncate_history` within limit
  - `_truncate_history` at exact limit
  - `_truncate_history` exceeds limit
  - `_truncate_history` with empty input
  - `answer_stream` returns async generator
  - `answer_stream` yields error token on Ollama down
- Do tests use `unittest.mock.patch` (not live LanceDB or Ollama)?
- Do tests NOT connect to port 5433?
- Are tests deterministic and isolated (no shared mutable state)?

### 9. Design Compliance

Review each acceptance criterion from the design document:
- AC1: Token streaming (generator yields strings)
- AC2: Module-level filtering applied correctly
- AC3: Architecture context uses full index
- AC4: History truncation at MAX_HISTORY_TURNS
- AC5: Ollama error yields `__ERROR__:` token

---

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run: `uv run pytest tests/unit/test_qa_engine.py -v`
2. Run: `uv run ruff check orch/rag/qa.py tests/unit/test_qa_engine.py`
3. Run: `uv run mypy orch/rag/qa.py`
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
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00049",
  "step_reviewed": "S01",
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
