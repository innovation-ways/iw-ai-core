# CR-00009 S07 — Tests Report

## Summary

Implemented tests for acceptance criteria AC3, AC4, AC5, and AC7 of the Chat Panel Context Awareness feature.

## Files Changed

- `tests/unit/test_qa_engine.py` — Extended with 5 new unit tests for `_build_system_prompt` and 4 new async tests for `answer_stream` fallback behavior
- `tests/integration/test_code_qa_routes.py` — Extended with 3 new integration tests for `module_name` round-trip

## Test Cases Added

### Unit Tests (TestBuildSystemPrompt)

| Test | AC | Description |
|------|-----|-------------|
| `test_system_prompt_no_module_is_byte_identical_to_pre_change_output` | AC5 | Hard-coded expected string guards against textual drift |
| `test_system_prompt_emits_module_block_when_path_provided` | AC3 | Module block appears with path and name |
| `test_system_prompt_module_block_without_name` | AC3 | No stray `()` when module_name is None |
| `test_system_prompt_retrieval_note_only_when_fallback_triggered` | AC4 | Retrieval Note only when fallback_triggered=True |
| `test_system_prompt_no_module_block_when_path_empty_string` | AC3 | No module block when path is empty |

### Unit Tests (TestAnswerStream)

| Test | AC | Description |
|------|-----|-------------|
| `test_answer_stream_falls_back_when_module_filter_empty` | AC4 | Fallback triggered when module filter returns empty |
| `test_answer_stream_does_not_fall_back_when_module_filter_nonempty` | AC5 | No fallback when module filter returns results |
| `test_answer_stream_does_not_fall_back_for_architecture_context` | AC5 | Architecture context skips module filtering entirely |
| `test_answer_stream_handles_lancedb_exception_without_claiming_fallback` | AC4 | LanceDB exceptions are handled gracefully |

### Integration Tests

| Test | AC | Description |
|------|-----|-------------|
| `test_post_qa_with_module_name_forwards_to_engine` | AC7 | module_name is forwarded to engine |
| `test_post_qa_without_module_name_still_accepted` | AC7 | Missing module_name accepted (defaults to None) |
| `test_post_qa_with_module_name_null_still_accepted` | AC7 | Explicit null module_name accepted |

## Test Results

```
tests/unit/test_qa_engine.py    — 19 passed
tests/integration/test_code_qa_routes.py — 11 passed
ruff check tests/               — All checks passed
```

## DOM Tests

DOM tests for header-label behavior were intentionally **not** added per the S16 coverage note in the instructions. The qv-browser step (S16) covers DOM behavior.

## Notes

- Async mocking of `llama_index.llms.ollama.Ollama.astream_chat` required careful handling: `async def` with `yield` returns an async generator (not awaitable), so tests use a `return inner_generator()` pattern instead
- Mocking `asyncio.to_thread` with `side_effect=mock_to_thread` was needed because the real function doesn't properly await `AsyncMock` results
- The `lancedb.connect` mock required `mock_db.open_table.return_value = mock_table` to properly chain through the context manager pattern
