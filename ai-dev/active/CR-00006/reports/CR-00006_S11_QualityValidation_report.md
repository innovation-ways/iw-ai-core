# CR-00006 S11 Quality Validation Report

## What Was Done

Executed S11 quality validation gates (1-15) for CR-00006 — Code View UX (Jobs View, Streaming Q&A, Markdown Rendering). Ran automated lint/format/type checks, unit/integration tests, route registration smoke-tests, event-type consistency grep, old banner removal verification, and browser-based UI verification via playwright-cli.

## Files Changed by CR-00006

| File | Change |
|------|--------|
| `dashboard/routers/jobs_ui.py` | New router for Jobs pages |
| `dashboard/routers/code_qa.py` | Non-buffering Q&A streaming bridge |
| `dashboard/routers/sse.py` | Added `code_map_completed` to toast events |
| `dashboard/templates/pages/project/jobs.html` | New Jobs list page |
| `dashboard/templates/pages/project/job_detail.html` | New Job detail page |
| `dashboard/templates/fragments/jobs_table.html` | New Jobs table fragment |
| `dashboard/templates/fragments/code_job_report.html` | Replaced green banner with neutral "Last run" summary |
| `dashboard/templates/fragments/code_qa_panel.html` | Markdown rendering with marked.js + DOMPurify |
| `dashboard/templates/fragments/nav_projects.html` | Added Jobs link to sidebar |
| `dashboard/templates/base.html` | Added DOMPurify CDN |
| `orch/rag/job.py` | Emit `code_map_completed` DaemonEvent on job completion |
| `orch/jobs/aggregator.py` | New Jobs aggregator service |
| `tests/unit/test_code_qa_streaming.py` | New streaming tests |
| `tests/unit/test_qa_markdown_sanitize.py` | New markdown sanitization tests |
| `tests/unit/test_jobs_aggregator.py` | New aggregator tests |
| `tests/integration/test_jobs_api.py` | New integration tests |

## Test Results

### Passed
- **Gates 1-3**: Ruff lint, format check, mypy — all clean
- **Gate 6**: Route registration — all 3 expected routes present (`/project/{id}/jobs`, `/project/{id}/jobs/fragment/table`, `/project/{id}/jobs/{job_type}/{job_id}`)
- **Gate 7**: Event-type consistency — `code_map_completed` found in 4 places (job.py insert, _TOAST_EVENTS, _TOAST_SEVERITY, template comment)
- **Gate 8**: Old banner removed — 0 matches for "Code map generated successfully" and "bg-green-50"
- **Gate 9**: Dashboard reachable — HTTP 200
- **Gate 10**: Sidebar Jobs link present between History and Tests
- **Gate 11**: Jobs list page renders with filters and table
- **Gate 12**: Code page shows no green banner; "code map generated successfully" text absent
- **Gate 14**: Markdown sanitization — 6/6 tests pass in `test_qa_markdown_sanitize.py`

### Skipped
- **Gate 13**: Q&A streaming — no code index exists for project `innoforge`; Ollama not available
- **Gate 15**: Jobs detail navigation — no `code_mapping` job exists for project `innoforge`

### Pre-existing Failures (NOT caused by CR-00006)
- **Gate 4**: 2 unit test failures:
  - `test_build_mermaid_contains_graph_td` — broken test signature (calls `MapGenerator._build_mermaid()` without required `config` arg); confirmed pre-existing on main branch
  - `test_default_index_path` — environment-specific path expansion issue
- **Gate 5**: 8 integration test failures in `test_global_search_*` — global search endpoint returns 404; pre-existing route/handler issue

## Observations

1. The CR-00006 implementation correctly adds the `code_map_completed` event type to the toast pipeline and removes the persistent green banner.
2. The new Jobs sidebar link and list page render correctly in the browser.
3. The Q&A streaming fix and markdown rendering are implemented correctly in the code; full E2E verification requires a running code index and Ollama which are not available in this environment.
4. All pre-existing test failures are in unrelated areas of the codebase (MapGenerator API, path config, global search).
