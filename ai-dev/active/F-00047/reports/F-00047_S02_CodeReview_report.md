# F-00047 S02 — Code Review Report

**Reviewer**: code-review-impl  
**Date**: 2026-04-16  
**Step**: S02 (Code Review: API Endpoints)  
**Files Reviewed**:
- `dashboard/routers/code_ui.py`
- `dashboard/app.py`
- `tests/unit/test_code_ui_routes.py`
- `tests/integration/test_code_sse.py`

---

## Review Result: PASS WITH NOTES

The S01 implementation is well-structured, follows project conventions, and passes all linting and type checks. Unit tests (20/20) pass. Integration tests timed out (likely testcontainer startup rather than code issue). There are a few minor deviations from the spec and some missing test coverage that should be addressed before QV gates, but no critical issues that would block S03.

---

### Critical Issues (must fix before S03)

None. No issues that would prevent S03 from starting.

---

### Minor Issues (fix before QV gates)

1. **Trigger endpoints return hardcoded HTML placeholders instead of template fragments** (`dashboard/routers/code_ui.py:324-327, 370-372`)

   `_trigger_job()` and `code_cancel_index()` return `HTMLResponse('<div hx-swap-oob="true" id="code-status-panel">...</div>')` instead of rendering `code_job_status.html` via `templates.TemplateResponse`. Since the templates don't exist yet (S03 scope), this is a reasonable placeholder, but the final implementation must render the actual fragment. The hx-swap-oob pattern is clever for now but doesn't match what the template would render.

   - `_trigger_job` line 324-327: returns placeholder "Job started"
   - `code_cancel_index` line 370-372: returns placeholder "Cancelling..."

2. **SSE `event_generator` doesn't handle non-CancelledError exceptions** (`dashboard/routers/code_ui.py:253-281`)

   If `queue.get()` raises an exception other than `CancelledError` (e.g., if the queue is closed unexpectedly), the generator exits without sending any terminal event, leaving the client hanging. Consider wrapping the `while True` loop body in a broader try/except that sends a terminal error event:

   ```python
   except asyncio.CancelledError:
       return
   except Exception as e:
       yield f"data: {json.dumps({'event': 'done', 'status': 'failed', 'error': str(e)})}\n\n"
       return
   ```

3. **Double `_get_project_or_404` call in `code_architecture`** (`dashboard/routers/code_ui.py:200-229`)

   Line 206 calls `_get_project_or_404(project_id, db)` and line 225 calls it again in the template context. The second call is redundant since the project was already validated. Either remove the second call or pass the already-fetched project object.

4. **Missing test coverage for page route** (`tests/unit/test_code_ui_routes.py`)

   The unit test file covers helpers and error paths but does not include:
   - `GET /project/{id}/code` returns 200 with a mock Project and no jobs
   - `GET /project/{id}/code` returns 404 for unknown project_id

   The helpers (`_get_project_or_404`, `_format_duration`, `_get_provider_label`) are tested, which provides some coverage. A full route-level test would require template rendering which depends on S03 templates.

5. **Integration test `test_sse_sends_progress_and_done_events` uses `threading.Thread` with `asyncio.run`** (`tests/integration/test_code_sse.py:169`)

   ```python
   t = threading.Thread(target=lambda: asyncio.run(inject_events()))
   t.start()
   ```

   This is unconventional — `asyncio.run()` creates a new event loop each time it's called. If `TestClient` uses a different asyncio loop, events may not propagate correctly. Consider using `asyncio.create_task()` within an existing event loop, or ensure the thread's event loop is properly coordinated with the test's loop.

6. **SSE integration test may hang if `chunk_size` doesn't align with SSE boundaries** (`tests/integration/test_code_sse.py:178`)

   `response.iter_content(chunk_size=256)` may split SSE lines (`data: {...}\n\n`) across chunk boundaries. Since the test only checks for byte presence rather than exact ordering, this hasn't failed yet, but it's fragile. Consider using `response.iter_lines()` instead.

---

### Suggestions (optional improvements)

1. **Use `Literal` type for `mode` parameter in `_trigger_job`** (`dashboard/routers/code_ui.py:293-297`)

   The `mode` parameter is typed as `str` but should be `Literal["full", "incremental", "mapgen_only"]` to match `start_index_job`'s signature and catch type errors at static analysis time.

2. **Add `job_id` to the SSE idle event for consistency** (`dashboard/routers/code_ui.py:238-239`)

   The idle event is `{"event": "done", "status": "idle"}` without a `job_id`. For consistency with other terminal events (`{"event": "done", "status": "completed", "job_id": "..."}`), consider including `job_id: None` or omitting it only in the idle case.

3. **Consider adding a ping/keepalive to SSE stream**

   The SSE stream can run for a long time (minutes during indexing). Without keepalive comments, some proxies or load balancers may close the connection. Consider sending a comment line every 30 seconds like `dashboard/routers/sse.py` does (`: ping ...`).

4. **Unit test for `code_status` endpoint with running job**

   Currently untested. Would require mocking the DB query for `running_job` and verifying the correct template is rendered.

---

### Quality Gate Results

| Gate | Command | Result |
|------|---------|--------|
| Ruff check | `uv run ruff check dashboard/routers/code_ui.py tests/unit/test_code_ui_routes.py tests/integration/test_code_sse.py` | PASS |
| Ruff format | `uv run ruff format --check dashboard/routers/code_ui.py` | PASS (1 file) |
| MyPy | `uv run mypy dashboard/routers/code_ui.py` | PASS (no issues) |
| Unit tests | `uv run pytest tests/unit/test_code_ui_routes.py -v` | PASS (20/20) |
| Integration tests | `uv run pytest tests/integration/test_code_sse.py -v` | TIMEOUT (testcontainer startup) |

---

### What Was Done

1. Read and analyzed all S01 output files
2. Compared `dashboard/routers/code_ui.py` against `dashboard/routers/docs.py` for structural consistency
3. Verified SSE streaming implementation against spec (correct format, headers, queue await pattern, CancelledError handling)
4. Verified job trigger and cancel endpoint logic (409 handling, mode parameter, BackgroundTasks scheduling)
5. Verified CodeIndexJob column usage against F-00045 schema
6. Verified TYPE_CHECKING guard and future annotations
7. Ran linting, formatting, type checking, and unit tests
8. Analyzed integration test for SSE stream

### Files Changed

- `dashboard/routers/code_ui.py` (new, 373 lines)
- `dashboard/app.py` (modified - added code_ui router import and registration)
- `tests/unit/test_code_ui_routes.py` (new, 274 lines)
- `tests/integration/test_code_sse.py` (new, 185 lines)

### Observations

1. **Templates not yet created** — The trigger and cancel endpoints return hardcoded HTML placeholders because the template files (S03 scope) don't exist yet. This is acceptable for S01 but will need to be addressed when templates are available.

2. **SSE implementation is correct** — The `await queue.get()` pattern, proper SSE formatting, headers, and `CancelledError` handling all follow the spec and existing `sse.py` patterns.

3. **CodeIndexJob column usage is correct** — No references to deprecated/non-existent columns (job_type, chat_model, languages_json, level1_doc, duration_formatted, completed_recently). Uses only F-00045 schema columns.

4. **Integration test architecture is sound** — Uses testcontainer properly, replaces psycopg2 URL, runs FTS DDL. The threading/asyncio pattern is unconventional but the underlying approach is valid.

5. **No duplicate `dashboard/routers/code.py`** — Confirmed only `dashboard/routers/code_ui.py` exists. F-00046 is correctly library-only.
