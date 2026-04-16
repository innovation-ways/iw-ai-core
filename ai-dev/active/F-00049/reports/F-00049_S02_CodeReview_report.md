# F-00049 S02 Code Review Report

## Summary

Reviewed S01 backend implementation of `QAEngine` in `orch/rag/qa.py` against the F-00049 design document and review checklist.

**Verdict: PASS**

## Files Changed

| File | Status |
|------|--------|
| `orch/rag/qa.py` | Reviewed - 166 lines |
| `tests/unit/test_qa_engine.py` | Reviewed - 298 lines |

## Test Results

```
10 passed, 0 failed
- TestBuildSystemPrompt::test_build_system_prompt_includes_context_doc PASSED
- TestBuildSystemPrompt::test_build_system_prompt_empty_context_doc PASSED
- TestTruncateHistory::test_truncate_history_within_limit PASSED
- TestTruncateHistory::test_truncate_history_at_limit PASSED
- TestTruncateHistory::test_truncate_history_exceeds_limit PASSED
- TestTruncateHistory::test_truncate_history_empty PASSED
- TestAnswerStream::test_answer_stream_returns_async_generator PASSED
- TestAnswerStream::test_answer_stream_error_token_on_ollama_down PASSED
- TestQAEngineConstants::test_top_k_is_8 PASSED
- TestQAEngineConstants::test_max_history_turns_is_5 PASSED
```

## Quality Checks

| Check | Result |
|-------|--------|
| `uv run ruff check orch/rag/qa.py` | ✅ Pass |
| `uv run ruff check tests/unit/test_qa_engine.py` | ⚠️ 1 S108 warning (test fixture uses `/tmp/lancedb` - false positive for test code) |
| `uv run mypy orch/rag/qa.py` | ✅ Success: no issues |

## Checklist Findings

### Architecture Compliance ✅
- `QAEngine` correctly placed in `orch/rag/qa.py`
- `answer_stream()` is `async def` generator with `yield` (line 117)
- Typed as `AsyncGenerator[str, None]`
- `TOP_K = 8`, `MAX_HISTORY_TURNS = 5` as class constants
- `__init__` accepts only `project_id: str` and `config: CodeUnderstandingConfig`
- `module_path: str | None = None` on `answer_stream()`
- `_truncate_history()` returns last `MAX_HISTORY_TURNS * 2` messages
- Stateless engine - no conversation history stored as instance state

### LanceDB Integration ✅
- Table name: `f"code_{project_id.replace('-', '_')}"` (line 65)
- Index path from `config.index_path` (line 64)
- Module filter applied when `context_level == "module"` and `module_path` provided (lines 73-78)
- No filter for `context_level == "architecture"` (line 80)
- Vector query uses `TOP_K = 8` as limit

### Embedding and LLM Usage ✅
- `OllamaEmbedding` used with `config.resolved_embed_model()`
- `Ollama` (llama-index class) used with `config.resolved_llm_model()`
- `config.ollama_url` passed to both clients
- `astream_chat()` (async streaming) used correctly

### System Prompt Construction ✅
- Includes context doc content when non-empty
- Substitutes `"(No architecture document available)"` when empty
- Includes retrieved chunk text with `---` separators
- Ends with instruction to answer based on context

### Conversation History ✅
- `_truncate_history()` called before building message list
- Correctly converted to `ChatMessage` objects with `role` and `content`
- System prompt injected as first message (role="system")
- Current question added as final user message

### Error Handling ✅
- `httpx.ConnectError` and `ConnectionRefusedError` caught around Ollama LLM call
- On connection error: yields `"__ERROR__:Local AI unavailable..."` token and returns
- No bare `except Exception` that swallows all errors silently

### Imports and Code Quality ✅
- `from __future__ import annotations` present
- Type-only imports (`AsyncSession`) guarded by `TYPE_CHECKING`
- No unused imports
- No hardcoded credentials, ports, or model names

### Test Quality ✅
- All 8 required test cases implemented
- Uses `unittest.mock.patch` (not live LanceDB or Ollama)
- No port 5433 connections
- Deterministic and isolated tests

## Findings

| Severity | Category | Description | Suggestion |
|----------|----------|-------------|------------|
| MEDIUM (suggestion) | conventions | Design doc specifies `config.resolved_chat_model()` but implementation uses `config.resolved_llm_model()`. The config at `orch/rag/config.py:68` does have `resolved_llm_model()`, so this is not a bug — just a naming discrepancy between design and implementation. | Consider aligning naming in design doc to `resolved_llm_model()` or vice versa. Not a blocker. |

## Acceptance Criteria Review

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Token streaming via async generator | ✅ |
| AC2 | Module-level filtering via `file_path LIKE` filter | ✅ |
| AC3 | Architecture context uses full index (no filter) | ✅ |
| AC4 | History truncation at `MAX_HISTORY_TURNS * 2` | ✅ |
| AC5 | Ollama error yields `__ERROR__:` token | ✅ |

## Notes

- Implementation is clean, correct, and ready for S03 (API layer)
- The `Ollama` class from `llama_index.llms.ollama` is the correct import (not `OllamaLLM`)
- Test mocking approach is adequate for the test cases covered
- The S108 ruff warning in tests is a false positive — test fixtures intentionally use temp paths
