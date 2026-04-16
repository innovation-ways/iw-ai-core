# F-00049 S01 Backend Report

## Work Done

Implemented `orch/rag/qa.py` — the `QAEngine` class providing context-aware RAG Q&A with streaming response and conversation history.

## Files Changed

| File | Change |
|------|--------|
| `orch/rag/qa.py` | Created — QAEngine class with `answer_stream()`, `_build_system_prompt()`, `_truncate_history()` |
| `orch/rag/config.py` | Modified — added `index_path: str` field to `CodeUnderstandingConfig` |
| `tests/unit/test_qa_engine.py` | Created — 10 unit tests covering all required test cases |

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

- `uv run ruff check orch/rag/qa.py` — All checks passed
- `uv run ruff check tests/unit/test_qa_engine.py` — 1 S108 warning (false positive: test fixture uses mock)
- `uv run mypy orch/rag/qa.py` — Success: no issues found

## Implementation Notes

1. **OllamaLLM → Ollama**: The llama_index library uses `Ollama` class name, not `OllamaLLM`. Updated accordingly.

2. **OllamaEmbedding parameter**: Uses `model_name=` instead of `model=` for the embedding class.

3. **index_path added to config**: `CodeUnderstandingConfig` now includes `index_path: str = "/var/lib/iw-ai/core/code-index"` to support the LanceDB path construction.

4. **Error handling**: `answer_stream()` wraps Ollama calls in try/except for `httpx.ConnectError` and `ConnectionRefusedError`, yielding `__ERROR__:Local AI unavailable...` on connection failure.

5. **LanceDB filtering**: When `context_level == "module"` and `module_path` is provided, a WHERE clause filter is applied to the LanceDB query.
