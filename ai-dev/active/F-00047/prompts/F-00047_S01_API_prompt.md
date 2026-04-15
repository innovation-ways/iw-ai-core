# F-00047 S01 — API: Code Tab Endpoints

## Mission

Implement **all** FastAPI route handlers for the Code Understanding dashboard tab. F-00047 owns the HTTP layer end-to-end — F-00046 is library-only. Create `dashboard/routers/code_ui.py` with the page route, the three POST action endpoints, the status/architecture HTML fragment endpoints, and the SSE progress stream. Register the router in `dashboard/app.py`.

## Scope Contract (Option C)

F-00046 provides Python entry points only, in `orch.rag.job`:

- `start_index_job(job, project, *, mode: Literal["full","incremental","mapgen_only"]) -> CodeIndexJobRunner`
- `JOB_REGISTRY: dict[str, CodeIndexJobRunner]`
- `CodeIndexJobRunner` (with `.progress_queue: asyncio.Queue`)
- `JobAlreadyRunningError`

F-00047's route handlers call `start_index_job` inside the request, catch `JobAlreadyRunningError` → HTTP 409, and schedule `runner.run()` via FastAPI `BackgroundTasks`. There is no `dashboard/routers/code.py` anywhere in the codebase — only this new `dashboard/routers/code_ui.py`.

## Required Reading

Before writing any code, read these files in order:
1. `CLAUDE.md` — architecture rules and critical constraints
2. `dashboard/CLAUDE.md` — dashboard-specific conventions (thin routes, fragment patterns)
3. `dashboard/app.py` — to understand how routers are registered
4. `dashboard/routers/docs.py` — follow this module's structure and style exactly
5. `dashboard/routers/sse.py` — follow the StreamingResponse / SSE pattern
6. `dashboard/dependencies.py` — `get_db()` usage
7. `orch/db/models.py` — `CodeIndexJob` model (from F-00045: columns `llm_model`, `embed_model`, `files_indexed`, `chunks_created`, `languages_detected`, `doc_id`, `triggered_at`, `completed_at`) and `Project`, `ProjectDoc`
8. `orch/rag/job.py` — `JOB_REGISTRY`, `start_index_job`, `JobAlreadyRunningError`, `CodeIndexJobRunner` (all from F-00046)
9. `orch/doc_service.py` — `DocService` for reading the architecture-map `ProjectDoc`
10. `ai-dev/active/F-00047/F-00047_Feature_Design.md` — full route and SSE event specification, plus the Field sourcing note

## What to Implement

### File: `dashboard/routers/code_ui.py`

Router prefix: `/project/{project_id}`

#### Route 1: Page

```
GET /project/{project_id}/code
```

- Look up `Project` by `project_id` (raise 404 if not found — same pattern as `docs.py`)
- Query the DB for:
  - Latest `CodeIndexJob` with `status == 'completed'` for this project → `last_completed_job`
  - Latest `CodeIndexJob` with `status == 'running'` for this project → `running_job`
- If `last_completed_job` exists and has a non-null `doc_id`, fetch the referenced `ProjectDoc` (composite id = `last_completed_job.doc_id`, which for F-00046's output will be `{project_id}:architecture-map`). Use `DocService.get_doc(project_id, "architecture-map")` or an equivalent query. The `ProjectDoc.content` is the Markdown `level1_doc_markdown`.
- Build `index_status` dict from `last_completed_job` (or None if no completed job). Use the exact F-00045 column names — do NOT invent field names:
  ```python
  index_status = None
  if last_completed_job:
      level1_md: str | None = None
      if last_completed_job.doc_id:
          arch_doc = DocService(session).get_doc(project_id, "architecture-map")
          level1_md = arch_doc.content if arch_doc else None
      index_status = {
          "provider": _get_provider_label(project),            # from project.config JSONB
          "llm_model": last_completed_job.llm_model,           # F-00045 column
          "embed_model": last_completed_job.embed_model,       # F-00045 column
          "last_indexed_at": last_completed_job.completed_at,
          "files_count": last_completed_job.files_indexed or 0,
          "chunks_count": last_completed_job.chunks_created or 0,
          "languages_detected": last_completed_job.languages_detected or [],
          "level1_doc_markdown": level1_md,
      }
  ```
- Compute display-only values in the route handler (the template must NOT do time math):
  ```python
  from datetime import datetime, timedelta, timezone
  last_completed_recent = (
      last_completed_job is not None
      and last_completed_job.completed_at is not None
      and (datetime.now(timezone.utc) - last_completed_job.completed_at) < timedelta(hours=1)
  )
  last_completed_duration = _format_duration(last_completed_job) if last_completed_job else None
  ```
  where `_format_duration(job)` returns a string like `"4m 32s"` from `(job.completed_at - job.triggered_at)`.
- Compute `arch_doc` and `content_html` via the shared `_render_architecture_html(arch_doc)` helper (see Helper functions). These MUST be passed to `project_code.html` so the included `code_architecture_view.html` fragment has the context variables it needs. Both Route 1 and Route 3 call the same helper — do not duplicate the mermaid pre-processing logic.
- Render template `project_code.html` with context: `current_project`, `index_status`, `running_job`, `last_completed_job`, `last_completed_recent`, `last_completed_duration`, `arch_doc`, `content_html`.

#### Route 2: Status fragment

```
GET /project/{project_id}/api/code/status
```

- Returns HTML fragment (no full page) — either `code_job_status.html` or `code_empty_state.html`
- Same DB queries as Route 1 but returns only the status panel fragment

#### Route 3: Architecture fragment

```
GET /project/{project_id}/api/code/architecture
```

- Returns `code_architecture_view.html` fragment
- Loads the architecture-map `ProjectDoc` via `DocService.get_doc(project_id, "architecture-map")` (composite id `{project_id}:architecture-map`). If missing, return the `code_empty_state.html` fragment instead.
- Calls `_render_architecture_html(arch_doc)` to produce `content_html` — do NOT re-implement the mermaid pre-processing here, reuse the helper so Route 1 and Route 3 emit identical HTML.
- Template context: `current_project`, `content_html` (pre-processed), `arch_doc` (ProjectDoc or None).

#### Route 4: SSE stream

```
GET /project/{project_id}/api/code/index/stream
```

- Returns `StreamingResponse` with `media_type="text/event-stream"`
- Looks up the running runner from `JOB_REGISTRY` (imported from `orch.rag.job`) using `project_id` as the key
- If no entry found: emit a single `data: {"event": "done", "status": "idle"}\n\n` and close
- If an entry is found: `await` events from `runner.progress_queue` and serialize each as `data: {json}\n\n`. Do NOT poll — `await queue.get()` blocks until the runner puts the next event.
- Emit a terminal event when the runner emits `phase="done"` (translate to `{"event": "done", "status": "completed", "job_id": runner.job_id}`) or `phase="error"` (translate to `{"event": "done", "status": "failed", "error": ...}`), then break out of the loop.
- Set response headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`
- Guard the generator body with `try/except asyncio.CancelledError: return` for client disconnects.
- Do NOT remove the runner from `JOB_REGISTRY` here — `CodeIndexJobRunner.run()` owns that lifecycle.
- **DB session lifetime (critical)**: the SSE handler must NOT hold a `get_db()`-scoped session across the long-lived stream. The queue-drain loop can run for minutes — holding a session that entire time pins a connection from the pool and blocks other requests. Pattern to follow:
  1. Resolve the `Project` / `JOB_REGISTRY` lookup inside the request handler with the normal `db = Depends(get_db)` session.
  2. Extract everything the generator needs (runner reference, project_id, job_id) into local variables **before** entering the `StreamingResponse` generator body.
  3. Do NOT reference the `Session` object inside the generator. If the generator needs to read or write DB rows after the initial lookup (it should not, in this design — all state updates belong to `CodeIndexJobRunner.run()`), open a short-lived `with SessionLocal() as s:` block for that specific operation and close it before the next `await queue.get()`.
  4. The request-scoped session from `Depends(get_db)` is closed automatically when the handler returns the `StreamingResponse`, which is fine — the generator runs **after** the handler returns, so FastAPI's dependency cleanup has already released that session. Any attempt to use `db` inside the generator is a use-after-close bug.

SSE event format — each line:
```
data: {json}\n\n
```

Progress event JSON:
```json
{
  "event": "progress",
  "phase": "indexing",
  "files_indexed": 127,
  "files_total": 247,
  "chunks_created": 4821,
  "elapsed_seconds": 134,
  "message": "Indexing file 127/247"
}
```

Terminal event JSON:
```json
{"event": "done", "status": "completed", "job_id": "abc123"}
```

or:
```json
{"event": "done", "status": "failed", "error": "..."}
```

#### Route 5: Trigger full index

```
POST /project/{project_id}/api/code/index
```

- Look up `Project` (404 if missing).
- Create a new `CodeIndexJob(project_id=project_id, status="queued", llm_model=..., embed_model=..., ...)` — set the model fields from `CodeUnderstandingConfig.resolved_llm_model()` / `resolved_embed_model()`. Do **not** set a `job_type` field — F-00045's schema has no such column.
- Commit the row so `job.id` is assigned.
- Call `start_index_job(job, project, mode="full")` synchronously. Wrap in `try/except JobAlreadyRunningError` → return `HTTPException(status_code=409, detail="A job is already running for this project")` (or the plain-text equivalent the other dashboard routers use).
- Schedule the returned runner via `background_tasks.add_task(runner.run)`.
- Return `code_job_status.html` fragment (with `running_job=job` and `current_project=project` in context).

#### Route 6: Trigger incremental re-index

```
POST /project/{project_id}/api/code/reindex
```

- Same as Route 5 but `start_index_job(..., mode="incremental")`.

#### Route 7: Trigger map regeneration

```
POST /project/{project_id}/api/code/regen-map
```

- Same as Route 5 but `start_index_job(..., mode="mapgen_only")`.

**Refactor the shared logic** of Routes 5–7 into a single private helper `_trigger_job(db, project_id, mode, background_tasks)` that does the lookup, row creation, `start_index_job` call, 409 handling, and scheduling. The three public handlers become one-liners that call it with different `mode` values.

#### Route 8: Cancel running job

```
DELETE /project/{project_id}/api/code/index
```

- Look up `Project` (404 if missing).
- Look up the runner: `runner = JOB_REGISTRY.get(project_id)`. If `None`, raise `HTTPException(status_code=404, detail="No running job for this project")`.
- Call `runner.request_cancel()` — a non-blocking cooperative cancel flag set exposed by F-00046. Do NOT await the runner's completion here; the runner's own `finally` block updates the DB row to `status="cancelled"` and removes itself from `JOB_REGISTRY`, and the SSE stream emits the terminal `{"event":"done","status":"cancelled"}` event on its own.
- Return the `code_job_status.html` fragment for the running job. The UI will keep showing the status panel (labeled "Cancelling..." by the template logic — the template checks whether the DB row's status is `running` or `cancelled`), and the SSE stream's terminal event will subsequently trigger a full refresh of both panels.
- Do NOT pop `JOB_REGISTRY[project_id]` here — the runner owns that lifecycle, same as the normal completion path.

The cancel handler must NOT be part of `_trigger_job` — it is a separate path with different semantics (no new row created, no `BackgroundTasks.add_task`, no `start_index_job` call).

### Helper functions

```python
def _get_provider_label(project: Project) -> str:
    """Extract provider label from project.config JSONB code_understanding block."""
    ...

def _format_duration(job: CodeIndexJob) -> str | None:
    """Return a short duration string like '4m 32s' from (job.completed_at - job.triggered_at). Returns None if either timestamp is missing."""
    ...

def _render_architecture_html(arch_doc: ProjectDoc | None) -> str | None:
    """Render the architecture-map ProjectDoc.content to HTML, pre-processing
    ```mermaid fenced blocks into <div class="mermaid">...</div> wrappers before
    calling dashboard.utils.markdown.render_markdown(). Returns None when arch_doc
    is None or has no content. Used by BOTH the page route and the architecture
    fragment route so the server-rendered HTML is identical on initial load and
    on htmx refresh after a job completes."""
    ...
```

Read config from `project.config.get("code_understanding", {})` — keys defined in F-00045's `orch/rag/config.py` (`provider`, `index_tier`, optional `llm_model` / `embed_model` overrides). Use `CodeUnderstandingConfig(**project.config.get("code_understanding", {}))` to materialize the Pydantic config, then `resolved_llm_model()` / `resolved_embed_model()` to populate the `CodeIndexJob` row.

Do NOT add `chat_model`, `job_type`, `completed_recently`, `duration_formatted`, `languages_json`, or `level1_doc` helpers — these names do not correspond to F-00045 schema columns. Use the actual F-00045 columns and compute display values in the route.

### Note on Mermaid extraction

In the architecture route, after server-side rendering the markdown, also extract raw Mermaid blocks from the original markdown and convert them to `<div class="mermaid">...</div>` before passing to template. The `render_markdown()` helper produces HTML — Mermaid blocks must be preserved as raw text for the client-side renderer. Either:
a) Pre-process the markdown string to replace ` ```mermaid ... ``` ` blocks with `<div class="mermaid">...</div>` before calling `render_markdown()`, OR
b) Pass the raw markdown to the template and let JS (marked.js + mermaid) handle it.

Option (a) is preferred — server-side pre-processing avoids client-side markdown parsing complexity. Use a simple regex to extract fenced mermaid blocks.

### File: `dashboard/app.py`

Add import and registration of the new router:
```python
from dashboard.routers import code_ui
app.include_router(code_ui.router)
```

Follow the exact pattern used for other routers in `app.py`. Confirm there is **no** existing `dashboard/routers/code.py` being registered — if one exists it is a stale artifact from an earlier draft of F-00046; delete it and flag in the step report. F-00046 is library-only; it must not register any router.

## Tests to Write

### `tests/unit/test_code_ui_routes.py`

Use the existing unit test pattern (mock DB, use `TestClient`). Write tests for:
- `GET /project/{id}/code` returns 200 with correct template
- `GET /project/{id}/code` returns 404 for unknown project
- `GET /project/{id}/api/code/status` returns 200
- `POST /project/{id}/api/code/index` creates a job and returns fragment
- `POST /project/{id}/api/code/index` returns 409 when job already running
- `DELETE /project/{id}/api/code/index` calls `runner.request_cancel()` and returns the status fragment when a runner is registered (use a fake runner injected into `JOB_REGISTRY` with a `request_cancel` mock)
- `DELETE /project/{id}/api/code/index` returns 404 when no runner is registered for the project

### `tests/integration/test_code_sse.py`

Use testcontainer pattern. Write tests for:
- SSE stream returns `done/idle` when no running job
- SSE stream sends progress events and terminal done event when job is in registry

Read `tests/CLAUDE.md` and `tests/conftest.py` before writing any test code.

## Quality Gates

After implementation, run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy orch/ dashboard/
uv run pytest tests/unit/test_code_ui_routes.py -v
```

All must pass before marking this step done.
