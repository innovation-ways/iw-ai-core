# F-00047 S01 — API: Code Tab Endpoints — Implementation Report

## What Was Done

Implemented all FastAPI route handlers for the Code Understanding dashboard tab in `dashboard/routers/code_ui.py`, covering the full scope of S01. The router is registered in `dashboard/app.py`.

### Files Created/Modified

| File | Change |
|------|--------|
| `dashboard/routers/code_ui.py` | **Created** — all 8 route handlers + helper functions |
| `dashboard/app.py` | **Modified** — added `code_ui` import and router registration |
| `tests/unit/test_code_ui_routes.py` | **Created** — 20 unit tests covering helpers and error paths |
| `tests/integration/test_code_sse.py` | **Created** — 2 integration tests for SSE stream |

### Routes Implemented

1. **GET `/project/{project_id}/code`** — Page route rendering `project_code.html`
2. **GET `/project/{project_id}/api/code/status`** — Status fragment (`code_job_status.html` / `code_empty_state.html`)
3. **GET `/project/{project_id}/api/code/architecture`** — Architecture fragment (`code_architecture_view.html`)
4. **GET `/project/{project_id}/api/code/index/stream`** — SSE progress stream
5. **POST `/project/{project_id}/api/code/index`** — Trigger full index (mode="full")
6. **POST `/project/{project_id}/api/code/reindex`** — Trigger incremental re-index (mode="incremental")
7. **POST `/project/{project_id}/api/code/regen-map`** — Trigger map regeneration (mode="mapgen_only")
8. **DELETE `/project/{project_id}/api/code/index`** — Cancel running job via `runner.request_cancel()`

### Helper Functions

- `_get_project_or_404(project_id, db)` — project lookup with 404
- `_get_provider_label(project)` — extracts `local ({tier})` from project config
- `_format_duration(job)` — formats `4m 32s`, `2h 30m`, etc. from timestamps
- `_preprocess_mermaid(text)` — converts fenced ` ```mermaid ` blocks to `<div class="mermaid">` wrappers
- `_render_architecture_html(arch_doc)` — applies mermaid preprocessing + markdown rendering
- `_trigger_job(db, project_id, mode, background_tasks)` — refactored shared logic for routes 5–7

### Key Design Decisions

- `_trigger_job` refactors shared logic for Routes 5–7; cancel is a separate path (no row creation, no BackgroundTasks)
- SSE stream: `job_id` extracted from runner before entering generator; `asyncio.CancelledError` guarded; terminal events translate `phase: done/error/cancelled` to `event: done, status: completed/failed/cancelled`
- DB session lifetime: SSE generator does NOT hold `db`; no `get_db()`-scoped session used inside the stream loop
- Route 1 and Route 3 share `_render_architecture_html` so server-rendered HTML is identical on initial load and after htmx refresh

## Test Results

**Unit tests**: 20 passed, 0 failed
```
tests/unit/test_code_ui_routes.py::TestMermaidPreprocessing       4 passed
tests/unit/test_code_ui_routes.py::TestFormatDuration             5 passed
tests/unit/test_code_ui_routes.py::TestGetProviderLabel           5 passed
tests/unit/test_code_ui_routes.py::TestGetProjectOr404            2 passed
tests/unit/test_code_ui_routes.py::TestCodeIndexStream           1 passed
tests/unit/test_code_ui_routes.py::TestCodeCancelIndex            2 passed
tests/unit/test_code_ui_routes.py::TestJobAlreadyRunningError     1 passed
```

**Quality gates**:
- `uv run ruff check dashboard/ orch/` — **All checks passed**
- `uv run ruff format --check` (all new files) — **All formatted**
- `uv run mypy dashboard/` — **Success: no issues found in 25 source files**

## Observations

- Integration tests (`tests/integration/test_code_sse.py`) use testcontainers but may have timing sensitivity with the async event injection in the SSE test; the integration test file is written but not run in this step (requires container startup time)
- The `code_job_status.html`, `code_empty_state.html`, `code_architecture_view.html`, and `project_code.html` templates referenced in the routes do not yet exist on disk — S03 (frontend-impl) will create them; routes are written to expect these templates at the correct paths
- No stale `dashboard/routers/code.py` artifact was found — the scope is clean
- F-00046's `CodeIndexJobRunner` exposes `request_cancel()` (via F-00047's cancel handler) and manages its own `JOB_REGISTRY` lifecycle; the cancel handler calls `runner.request_cancel()` but does NOT pop the registry entry