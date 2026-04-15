# F-00049_S03_API_prompt

**Work Item**: F-00049 — Code Understanding: Q&A Panel (SSE Streaming)
**Step**: S03
**Agent**: api-impl

---

## Input Files

- `ai-dev/active/F-00049/F-00049_Feature_Design.md` — Full design document (read this first)
- `ai-dev/work/F-00049/reports/F-00049_S01_Backend_report.md` — S01 implementation report (read what QAEngine expects)
- `orch/rag/qa.py` — QAEngine (read before writing the endpoint)
- `orch/rag/config.py` — CodeUnderstandingConfig (read how to construct it)
- `dashboard/routers/sse.py` — Existing SSE StreamingResponse pattern (study this)
- `dashboard/routers/code.py` — Existing code-related router (follow same conventions)
- `dashboard/app.py` — Router registration (you will modify this)
- `dashboard/dependencies.py` — `get_db()` async session dependency
- `orch/db/models.py` — `Project` model (used for project existence check)
- `tests/conftest.py` — Test fixtures
- `tests/CLAUDE.md` — Testing rules (NON-NEGOTIABLE)
- `CLAUDE.md` — Project-level conventions (NON-NEGOTIABLE)

## Output Files

- `dashboard/routers/code_qa.py` — New file: POST endpoint
- `dashboard/app.py` — Modified to register `code_qa` router
- `tests/integration/test_code_qa_routes.py` — Integration tests
- `ai-dev/work/F-00049/reports/F-00049_S03_API_report.md` — Step report

---

## Context

You are implementing the API layer for **F-00049: Code Understanding Q&A Panel**. The endpoint wraps `QAEngine.answer_stream()` in an SSE `StreamingResponse`. Read `dashboard/routers/sse.py` for the existing SSE pattern before writing anything.

Read `CLAUDE.md` and `dashboard/CLAUDE.md` before writing any code.

---

## Requirements

### 1. Pydantic Request Model

Define in `dashboard/routers/code_qa.py`:

```python
from pydantic import BaseModel, Field

class ConversationMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class QARequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    context_level: str = Field(..., pattern="^(architecture|module)$")
    context_doc_id: str | None = None
    module_path: str | None = None
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
```

Validation:
- `question` is required, 1–1000 characters (Pydantic `min_length=1, max_length=1000`)
- `context_level` must be `"architecture"` or `"module"` (Pydantic `pattern` validator)
- `conversation_history` defaults to empty list
- Return HTTP 422 (FastAPI automatic) on Pydantic validation failure — do NOT override this with a custom 400

### 2. Endpoint

```python
@router.post("/api/projects/{project_id}/code/qa")
async def code_qa(
    project_id: str,
    request: QARequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
```

**Step-by-step implementation**:

1. **Verify project exists**: Query `Project` by `project_id`. If not found, raise `HTTPException(status_code=404, detail="Project not found")`.

2. **Verify LanceDB index exists**: Check that the path `{config.index_path}/{project_id}/vectors/` exists on disk using `pathlib.Path.exists()`. If not, raise `HTTPException(status_code=404, detail="No code index found for this project")`. Use `CodeUnderstandingConfig` constructed from the project's settings (or use global config from `orch.config`).

3. **Build async generator**. All SSE payloads MUST be built with `json.dumps()` — never f-string interpolation — so error messages containing quotes or backslashes cannot break the stream contract:
   ```python
   async def _sse_generator() -> AsyncGenerator[str, None]:
       full_response_parts: list[str] = []
       try:
           engine = QAEngine(project_id=project_id, config=config)
           async for token in engine.answer_stream(
               question=request.question,
               context_level=request.context_level,
               context_doc_id=request.context_doc_id,
               module_path=request.module_path,
               conversation_history=[m.model_dump() for m in request.conversation_history],
               session=db,
           ):
               if token.startswith("__ERROR__:"):
                   error_msg = token[len("__ERROR__:"):]
                   payload = json.dumps({"event": "error", "message": error_msg})
                   yield f"data: {payload}\n\n"
                   return
               full_response_parts.append(token)
               payload = json.dumps({"token": token})
               yield f"data: {payload}\n\n"
       except (httpx.ConnectError, ConnectionRefusedError):
           payload = json.dumps({
               "event": "error",
               "message": "Local AI unavailable. Check that Ollama is running.",
           })
           yield f"data: {payload}\n\n"
           return
       full_response = "".join(full_response_parts)
       payload = json.dumps({"event": "done", "full_response": full_response})
       yield f"data: {payload}\n\n"
   ```
   Do NOT catch bare `Exception` inside the generator — unexpected errors should propagate so FastAPI logs them and the client sees a connection drop rather than a misleading "unexpected error" event. Only the known Ollama connection errors are caught here (the engine already handles these via its `__ERROR__:` prefix, but catch them at the router layer too in case the engine raises before yielding anything).

4. **Return StreamingResponse**:
   ```python
   return StreamingResponse(
       _sse_generator(),
       media_type="text/event-stream",
       headers={
           "Cache-Control": "no-cache",
           "X-Accel-Buffering": "no",
           "Connection": "keep-alive",
       },
   )
   ```

**Note on config construction**: Read `orch/rag/config.py` to understand how `CodeUnderstandingConfig` is built. If there is a factory function or a way to get a project-specific config, use it. If `CodeUnderstandingConfig` reads from environment variables, construct it once at module level or per-request. Do not hardcode model names or paths.

### 3. Router Registration

In `dashboard/app.py`, import and include the new router:

```python
from dashboard.routers import code_qa
app.include_router(code_qa.router)
```

Follow the exact pattern used for the existing `code` router registration.

### 4. Integration Tests: tests/integration/test_code_qa_routes.py

**NON-NEGOTIABLE rules** (from `tests/CLAUDE.md`):
- Use testcontainers for DB (never port 5433)
- Use the `db_session`, `test_project`, and `async_client` fixtures from `conftest.py`
- Mock all Ollama and LanceDB calls — never call real Ollama in tests
- Never mock the DB itself — use testcontainers

**Test cases (TDD: write RED first)**:

```python
# test_qa_project_not_found
# Given: a project_id that does not exist in the DB
# When: POST /api/projects/{project_id}/code/qa with a valid body
# Then: HTTP 404 is returned

# test_qa_no_index_found
# Given: a valid project in DB but no LanceDB index on disk
# When: POST /api/projects/{project_id}/code/qa
# Then: HTTP 404 with detail "No code index found for this project"

# test_qa_validation_empty_question
# Given: request body with question = ""
# When: POST /api/projects/{project_id}/code/qa
# Then: HTTP 422 is returned (Pydantic validation)

# test_qa_validation_question_too_long
# Given: request body with question = "x" * 1001
# When: POST /api/projects/{project_id}/code/qa
# Then: HTTP 422 is returned

# test_qa_validation_invalid_context_level
# Given: request body with context_level = "symbol"
# When: POST /api/projects/{project_id}/code/qa
# Then: HTTP 422 is returned

# test_qa_streams_tokens
# Given: valid project, mocked LanceDB index exists, mocked QAEngine.answer_stream yields ["Hello", " world"]
# When: POST /api/projects/{project_id}/code/qa with valid body
# Then: response Content-Type is text/event-stream
# And: response body contains 'data: {"token": "Hello"}'
# And: response body contains 'data: {"token": " world"}'
# And: response body contains '"event": "done"'
# Implementation note: patch QAEngine.answer_stream as an AsyncMock returning an async generator

# test_qa_streams_error_event_on_ollama_down
# Given: valid project, mocked index exists, QAEngine.answer_stream yields "__ERROR__:Local AI unavailable..."
# When: POST /api/projects/{project_id}/code/qa
# Then: response body contains '"event": "error"'
# And: response body contains "Local AI unavailable"

# test_qa_empty_conversation_history
# Given: valid request with conversation_history = []
# When: POST /api/projects/{project_id}/code/qa
# Then: HTTP 200 with streaming response (no error from empty history)
```

For `test_qa_streams_tokens` and related streaming tests, collect the full response body as a string and parse SSE lines. Use `httpx.AsyncClient` in test mode.

---

## Project Conventions

- Routes are thin: `code_qa.py` contains only request validation + `QAEngine` delegation
- No business logic in the router — all RAG logic lives in `orch/rag/qa.py`
- Use `AsyncSession` from `dashboard/dependencies.py:get_db()`
- Follow the router prefix pattern from existing routers (no `/api` prefix on the router object itself — or follow exactly what existing `code.py` does)
- `from __future__ import annotations` at top of every new file
- All JSON serialization uses `import json` (stdlib)

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write all integration tests first. They will fail because `code_qa.py` does not exist.
2. **GREEN**: Create `dashboard/routers/code_qa.py` and register it. Tests should pass.
3. **REFACTOR**: Clean up, remove dead code, ensure docstrings are accurate.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run: `uv run pytest tests/integration/test_code_qa_routes.py -v`
2. Run: `uv run ruff check dashboard/routers/code_qa.py tests/integration/test_code_qa_routes.py`
3. Run: `uv run mypy dashboard/routers/code_qa.py`
4. Do NOT report `tests_passed: true` unless ALL tests pass with zero failures
5. If tests fail, fix them before reporting completion

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "api-impl",
  "work_item": "F-00049",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/code_qa.py",
    "dashboard/app.py",
    "tests/integration/test_code_qa_routes.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
