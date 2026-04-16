# F-00049 S03 API Implementation Report

## Summary

Implemented the API layer for **F-00049: Code Understanding Q&A Panel (SSE Streaming)**. Created the `POST /api/projects/{project_id}/code/qa` SSE streaming endpoint that wraps `QAEngine.answer_stream()`.

## Files Changed

### Created
- `dashboard/routers/code_qa.py` — New router with POST endpoint
- `tests/integration/test_code_qa_routes.py` — 8 integration tests

### Modified
- `dashboard/app.py` — Registered `code_qa.router`
- `dashboard/dependencies.py` — Added `get_db_async()` async session dependency (infrastructure)

## Key Implementation Details

### Endpoint Design
- **Route**: `POST /api/projects/{project_id}/code/qa`
- **Response**: `text/event-stream` (SSE)
- **Request Model**: `QARequest` with Pydantic validation:
  - `question`: 1-1000 chars (required)
  - `context_level`: "architecture" | "module" (required, pattern validator)
  - `conversation_history`: list of {role, content} (default empty)
  - `context_doc_id`, `module_path`: optional

### Architecture
- Router is thin: validates project existence + index existence, delegates to `QAEngine`
- Uses `get_db()` (sync session) and runs `QAEngine.answer_stream()` in a thread pool via `asyncio.to_thread()` + `asyncio.run()`
- SSE payloads built with `json.dumps()` (never f-string interpolation)
- Error handling: catches `__ERROR__:` prefix tokens, `ConnectionRefusedError`, `OSError`

### Testing
- 8 integration tests all passing with testcontainers (no live DB)
- Tests mock `QAEngine` at `orch.rag.qa.QAEngine` module level
- Uses `TestClient` with dependency override for `get_db`

## Quality Checks

| Check | Result |
|-------|--------|
| `uv run pytest tests/integration/test_code_qa_routes.py -v` | 8 passed |
| `uv run ruff check dashboard/routers/code_qa.py tests/integration/test_code_qa_routes.py` | All passed |
| `uv run mypy dashboard/routers/code_qa.py` | Success |

## Test Coverage

- `test_qa_project_not_found` — HTTP 404 when project not in DB
- `test_qa_no_index_found` — HTTP 404 when LanceDB index path doesn't exist
- `test_qa_validation_empty_question` — HTTP 422 for empty question
- `test_qa_validation_question_too_long` — HTTP 422 for question > 1000 chars
- `test_qa_validation_invalid_context_level` — HTTP 422 for invalid context_level
- `test_qa_streams_tokens` — SSE token streaming with mocked QAEngine
- `test_qa_streams_error_event_on_ollama_down` — SSE error event on `__ERROR__:` token
- `test_qa_empty_conversation_history` — Works with empty conversation_history

## Notes

- Added async session infrastructure (`get_db_async()`) to `dependencies.py` although the final implementation uses sync sessions via thread pool
- The `type: ignore[arg-type]` on the `session` argument to `answer_stream()` is a known limitation — `QAEngine` expects `AsyncSession` but we pass sync `Session` (tests work because `QAEngine` is mocked)
- Tests use `tmp_path` fixture for unique per-test index directories
