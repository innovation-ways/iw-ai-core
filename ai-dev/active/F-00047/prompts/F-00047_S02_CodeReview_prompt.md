# F-00047 S02 — Code Review: API Endpoints

## Mission

Review all code produced in S01 for correctness, style, and adherence to project conventions.

## Required Reading

1. `CLAUDE.md` — architecture and critical rules
2. `dashboard/CLAUDE.md` — dashboard conventions
3. `ai-dev/active/F-00047/F-00047_Feature_Design.md` — feature specification
4. `ai-dev/active/F-00047/prompts/F-00047_S01_API_prompt.md` — what was asked of S01
5. All files created or modified by S01:
   - `dashboard/routers/code_ui.py`
   - `dashboard/app.py`
   - `tests/unit/test_code_ui_routes.py`
   - `tests/integration/test_code_sse.py`

## Review Checklist

### Structure and Conventions
- [ ] Router module follows the same structure as `dashboard/routers/docs.py`
- [ ] Router is registered in `dashboard/app.py` using the same pattern as existing routers
- [ ] All route handlers are thin — no business logic, only DB queries + template rendering
- [ ] `_get_project_or_404()` helper used (or equivalent) for 404 handling
- [ ] Imports use `from __future__ import annotations` at top
- [ ] `TYPE_CHECKING` guard used for type-only imports

### SSE Endpoint
- [ ] `StreamingResponse` used with `media_type="text/event-stream"`
- [ ] Correct SSE format: `data: {json}\n\n` (two newlines)
- [ ] `asyncio.CancelledError` caught and handled (client disconnect)
- [ ] Progress events are **awaited from `runner.progress_queue`** — not polled via a `sleep` loop
- [ ] Response headers set: `Cache-Control: no-cache`, `X-Accel-Buffering: no`
- [ ] Terminal `done` event sent before closing when the runner emits `phase="done"` or `phase="error"`
- [ ] No-job case (`project_id` not in `JOB_REGISTRY`) sends `{"event": "done", "status": "idle"}` and closes immediately
- [ ] The SSE handler does NOT pop the runner from `JOB_REGISTRY` — that is `CodeIndexJobRunner.run()`'s job
- [ ] The SSE handler does NOT reference the `Depends(get_db)` session inside the generator body — that session is closed by FastAPI's dependency cleanup as soon as the handler returns the `StreamingResponse`. The generator must operate on locally-captured variables (runner reference, project_id, job_id). If a DB operation is genuinely needed inside the generator, it uses a short-lived `with SessionLocal() as s:` block and closes before the next `await queue.get()`. Flag any use of the request-scoped `db` inside the generator as CRITICAL (use-after-close).

### Action POST Endpoints
- [ ] 409 returned when `start_index_job` raises `JobAlreadyRunningError` (caught explicitly — not a generic try/except Exception)
- [ ] New `CodeIndexJob` ORM objects created using only F-00045 schema columns — verify NO references to `job_type`, `chat_model`, `languages_json`, `level1_doc`, `duration_formatted`, or `completed_recently`
- [ ] `llm_model` / `embed_model` populated from `CodeUnderstandingConfig.resolved_llm_model()` / `resolved_embed_model()`
- [ ] DB session committed before `start_index_job` is called (so `job.id` is assigned)
- [ ] `start_index_job(job, project, mode=...)` called with the correct mode per endpoint (`"full"`, `"incremental"`, `"mapgen_only"`)
- [ ] Background task uses FastAPI `BackgroundTasks.add_task(runner.run)` — not `asyncio.create_task`
- [ ] No duplicate `dashboard/routers/code.py` created or imported anywhere (F-00046 is library-only)

### Cancel Endpoint (DELETE /api/code/index)
- [ ] 404 returned when `project_id` is not in `JOB_REGISTRY`
- [ ] Calls `runner.request_cancel()` on the matching runner (not `asyncio.Task.cancel()`, not `runner.run()` itself)
- [ ] Does NOT pop the runner from `JOB_REGISTRY` — cleanup is the runner's `finally` block
- [ ] Does NOT create a new `CodeIndexJob` row — cancel operates on the existing row
- [ ] Returns the `code_job_status.html` fragment (same contract as the trigger POSTs) so the UI can swap to a cancelling state immediately
- [ ] Not routed through `_trigger_job` helper — separate code path

### Type Safety
- [ ] All route handlers have explicit return type annotations (`-> Any` or specific Response type)
- [ ] `Jinja2Templates` accessed via `request.app.state.templates` (not imported directly)
- [ ] No `Any` used where a specific type is possible

### Tests
- [ ] Unit tests do NOT connect to live DB — all DB interactions mocked
- [ ] Integration tests use testcontainer (not port 5433)
- [ ] Integration tests run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `create_all()`
- [ ] psycopg2 URL replaced with psycopg in testcontainer tests
- [ ] At minimum: 200, 404, and 409 cases covered for page and action routes
- [ ] SSE stream tested for both `idle` (no job) and `progress + done` cases

### Mermaid Pre-processing
- [ ] Regex used to extract `\`\`\`mermaid ... \`\`\`` blocks from markdown
- [ ] Replacement produces `<div class="mermaid">...</div>`
- [ ] `| safe` filter used in template to render this pre-processed HTML

## Output Format

Provide a structured report:

```
## Review Result: PASS | FAIL | PASS WITH NOTES

### Critical Issues (must fix before S03)
- ...

### Minor Issues (fix before QV gates)
- ...

### Suggestions (optional improvements)
- ...
```

If there are critical issues, the agent implementing S03 MUST NOT start until they are resolved. List the exact file and line number for each issue found.
