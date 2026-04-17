# CR-00006: Code View UX — Jobs View, Streaming Q&A, Markdown Rendering

**Type**: Change Request
**Priority**: Medium
**Reason**: Three related UX gaps in the Code tab: (1) no unified visibility of async background operations (code mapping, research, doc generation, batch execution); (2) the Q&A panel blocks until the LLM finishes (bug — the streaming pipeline exists but buffers end-to-end); (3) assistant responses render as raw markdown text instead of formatted HTML.
**Created**: 2026-04-17
**Status**: Draft

---

## Description

Bundle three Code-view polish changes into one CR:

1. **Jobs view** — new `/project/{id}/jobs` page that aggregates async background operations (Code Mapping, Research, Document Generation, Batch Execution) into a single list with detail pages. Replaces the persistent green "Code map generated successfully" banner with a short auto-dismiss toast that links to the Jobs entry. The existing WorkItem-centric History page is left unchanged.
2. **Streaming Q&A fix** — replace the current "collect-then-emit" async bridge in `dashboard/routers/code_qa.py` with a non-buffering bridge so tokens reach the browser as Ollama produces them.
3. **Markdown rendering** — render assistant responses in the Q&A panel as sanitized Markdown using the already-loaded `marked.js` plus newly-added `DOMPurify`.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant subpackages: `dashboard/CLAUDE.md` (FastAPI + Jinja2 + htmx + Tailwind CDN, no build step) and `orch/CLAUDE.md` (SQLAlchemy 2.0 sync, psycopg v3).

## Current Behavior

### (1) Persistent banner + no unified Jobs view

- `dashboard/templates/project_code.html:77-79` renders the success banner fragment `fragments/code_job_report.html:1-20` whenever `last_completed_job` exists and completed within the last hour (gating logic at `dashboard/routers/code_ui.py:114-118`). The banner does not auto-dismiss; it stays rendered until the hour window elapses or a new job starts.
- Async background operations live in separate tables with no unified listing:
  - Code Mapping: `code_index_jobs` (`orch/db/models.py:1041-1117`)
  - Document Generation: `doc_generation_jobs` (`orch/db/models.py:912-968`)
  - Batch Execution: `batches` (`orch/db/models.py:572-631`)
  - Research: `project_docs` rows with `doc_type = DocType.research` (`orch/db/models.py:816-885`)
- The existing History page (`dashboard/templates/pages/project/history.html`, route `project_pages.py:238-282`) only lists `WorkItem` rows in `completed` or `failed` status. It is WorkItem-centric and does not surface any of the four async ops above.

### (2) Q&A streaming is buffered end-to-end

- Frontend (`dashboard/templates/fragments/code_qa_panel.html:167-232`) fetches the endpoint, parses SSE `data:` lines, and appends tokens to the response bubble — frontend behaviour is correct.
- Backend endpoint: `dashboard/routers/code_qa.py:127-168` returns a `StreamingResponse` wrapping `_sse_generator`.
- **Bug**: `_sse_generator` at `code_qa.py:85-124` calls `loop.run_in_executor(None, _run_qa_in_thread, …)` on line 97, and `_run_qa_in_thread` at lines 60-82 uses `asyncio.run(collect_tokens())` which runs the QAEngine async generator **to completion** inside a thread, appending every token into a Python list, then returns the full list. Only after that does the outer generator iterate the list and yield SSE frames. Net result: the client sees nothing until the LLM finishes, then all tokens arrive effectively at once.
- `QAEngine.answer_stream()` at `orch/rag/qa.py:36-119` already yields tokens one at a time via `llm.astream_chat(messages)` — the generator itself is not the problem.

### (3) Assistant responses render as raw text

- `code_qa_panel.html:202` assigns `responseSpan.textContent += data.token`, so markdown syntax (e.g., `**bold**`, headings, fenced code blocks) is visible as literal characters.
- `marked.js` is already loaded in `dashboard/templates/base.html:77`, but the Q&A panel does not call it.
- `DOMPurify` is not loaded anywhere in the project.

## Desired Behavior

### (1) Jobs view

- New page at `/project/{project_id}/jobs` added to the sidebar (in `dashboard/templates/fragments/nav_projects.html`) listed directly after `History`. Shows a single sortable/filterable table of async operations across all four types with columns:
  - **ID** (e.g., `CIJ-abc12345`, `DGJ-…`, `B-00042`, `RES-…`)
  - **Type** (`code_mapping`, `doc_generation`, `batch_execution`, `research`)
  - **Title** (short summary: e.g., "Code map — full", doc title, batch name, research title)
  - **Status** (`queued`, `running`, `completed`, `failed`, `cancelled`)
  - **Started at** (human timestamp)
  - **Finished at** (human timestamp, blank if running)
  - **Duration** (hh:mm:ss or `—`)
  - **Triggered by** (user/system label when available)
- Filters: **Type** (multi-select), **Status** (multi-select), **Date range** (from/to).
- Pagination: 25 rows per page; server-side ordering by `started_at desc` by default.
- Clicking a row opens `/project/{project_id}/jobs/{job_type}/{job_id}` showing:
  - Full parameters (e.g., `llm_model`, `index_tier`, `trigger_reason`)
  - Lifecycle events (for code map: stream events; for batches: `StepRun` rows; for doc gen: `agent_output`)
  - Output artifact link (e.g., generated architecture map, research doc, batch diagram, doc preview)
  - Error message if `status == failed`
- **Banner replacement**: on code map completion, insert a `DaemonEvent` with `event_type = "code_map_completed"`. The existing SSE toast pipeline (`dashboard/routers/sse.py:208-219`) emits a toast with severity `success`. The fragment at `fragments/code_job_report.html` is replaced with a compact, permanent "Last run" summary (not a green banner) that includes a **link** to the Jobs detail page for that run. The green banner is removed.

### (2) Q&A streaming — truly streaming

- The first token must be visible to the browser within **1 second** of Ollama yielding it to the server (measured locally, network latency excluded).
- Backend change is localized to `dashboard/routers/code_qa.py`. The QAEngine itself is untouched. Approach: build an `asyncio.Queue`, run `QAEngine.answer_stream` inside a dedicated thread with its own event loop (via `asyncio.run_coroutine_threadsafe`) that drains tokens into the queue, and have the outer async generator `await queue.get()` in a loop, yielding SSE frames as each token arrives.
- Stream errors (`ConnectionRefusedError`, `httpx.ConnectError`) and client disconnects (`Request.is_disconnected`) are handled gracefully: an error frame is emitted as `{"event": "error", "message": "…"}` (same wire format as today) and the thread is signalled to stop.

### (3) Sanitized Markdown rendering

- Load `DOMPurify` via CDN in `dashboard/templates/base.html` (just after `marked.js`).
- In `code_qa_panel.html`:
  - Maintain a per-bubble `rawMarkdown` accumulator separate from the rendered DOM.
  - On each token, append to `rawMarkdown`, call `marked.parse(rawMarkdown)` with `{ gfm: true, breaks: true }`, then `DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })`, and set the bubble's `.innerHTML` to the sanitized result.
  - Supported elements: headings (h1-h6), paragraphs, `<strong>`/`<em>`, inline code, fenced code blocks, lists (ordered/unordered), links (`target="_blank"` and `rel="noopener noreferrer"` — enforced by a DOMPurify hook), tables, blockquotes.
  - Syntax highlighting: out of scope. Code blocks render monospace via Tailwind (`pre code` styling added to theme or inline).
  - User bubbles remain plain text (no markdown rendering on user input).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `dashboard/routers/code_qa.py` | `_run_qa_in_thread` collects all tokens into a list, then SSE yields them | Non-buffering bridge: thread runs async generator into an `asyncio.Queue`; outer generator yields SSE frames as tokens arrive |
| `dashboard/templates/fragments/code_qa_panel.html` | `responseSpan.textContent += token` (plain text) | Maintain `rawMarkdown`; render with `marked.parse` + `DOMPurify.sanitize` on each token |
| `dashboard/templates/base.html` | Loads `marked.js` only | Also loads `DOMPurify` from CDN |
| `dashboard/templates/fragments/code_job_report.html` | Green persistent banner "Code map generated successfully" with duration/counters | Compact neutral "Last run" summary with a link to the Jobs detail page; no green banner |
| `orch/rag/job.py` (job completion path) | Updates `CodeIndexJob.status = completed` | Also inserts `DaemonEvent(event_type="code_map_completed")` with `entity_id = job.id`, `message = "Code map generated — N files, M chunks"` |
| `dashboard/routers/sse.py` | `_TOAST_EVENTS` and `_TOAST_SEVERITY` do not include `code_map_completed` | Add `code_map_completed: success` to both sets |
| `orch/jobs/aggregator.py` | Does not exist | New read-only service: `list_jobs(project_id, filters, page)` and `get_job(project_id, job_type, job_id)`; unions `code_index_jobs`, `doc_generation_jobs`, `batches`, research `project_docs` |
| `dashboard/routers/jobs_ui.py` | Does not exist | New router with `GET /project/{id}/jobs`, `GET /project/{id}/jobs/{job_type}/{job_id}`, and htmx-friendly fragment variants for filter changes |
| `dashboard/templates/pages/project/jobs.html` | Does not exist | New page (extends `base.html`) — filters + table |
| `dashboard/templates/fragments/jobs_table.html` | Does not exist | Filter-responsive fragment |
| `dashboard/templates/pages/project/job_detail.html` | Does not exist | New detail page (one template with `{% if job_type == … %}` blocks — no new routers per type) |
| `dashboard/templates/fragments/nav_projects.html` | Sidebar has no Jobs link | Insert `('/project/' ~ project.id ~ '/jobs', 'Jobs')` after the `History` entry |
| `tests/unit/test_code_qa_streaming.py` | Does not exist | Unit test: bridge emits tokens as they arrive (timing assertion) |
| `tests/unit/test_jobs_aggregator.py` | Does not exist | Unit test: aggregator unions four sources, filters, sorts, paginates |
| `tests/integration/test_jobs_api.py` | Does not exist | Integration test: `/jobs` list + detail endpoints round-trip via testcontainer |
| `tests/unit/test_qa_markdown_sanitize.py` | Does not exist | Unit test: XSS vectors sanitized, markdown subsets render correctly |

### Breaking Changes

- None. The `/api/projects/{id}/code/qa` endpoint keeps the same wire format (`data: {"token": "…"}\n\n`, `data: {"event": "done", "full_response": "…"}\n\n`, `data: {"event": "error", "message": "…"}\n\n`). No database schema change. No API endpoint removals.

### Data Migration

- None. Option A (query-aggregation) is used: no new tables, no column changes, no dual-write, no backfill. The aggregator queries existing tables at request time.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Bug fix in `dashboard/routers/code_qa.py` (non-buffering bridge) + new `orch/jobs/aggregator.py` (read-only service) + insert `DaemonEvent(code_map_completed)` at code index job completion | — |
| S02 | code-review-impl | Review S01: streaming bridge correctness, aggregator SQL correctness, event emission | — |
| S03 | api-impl | New routes in `dashboard/routers/jobs_ui.py`: `GET /project/{id}/jobs`, `GET /project/{id}/jobs/{job_type}/{job_id}`, `GET /project/{id}/jobs/fragment/table` (filter-change htmx response). Register with app in `dashboard/app.py`. Add `code_map_completed` to `_TOAST_EVENTS`/`_TOAST_SEVERITY` in `sse.py` | — |
| S04 | code-review-impl | Review S03: route contracts, status codes, filter parameter validation, error paths | — |
| S05 | frontend-impl | New templates `pages/project/jobs.html`, `pages/project/job_detail.html`, `fragments/jobs_table.html`. Replace `fragments/code_job_report.html` with a neutral "Last run" summary linking to the Jobs detail. Add `Jobs` link to `fragments/nav_projects.html`. Add DOMPurify CDN to `base.html`. Update `code_qa_panel.html` to render sanitized markdown per-token. | — |
| S06 | code-review-impl | Review S05: template correctness, accessibility (alt text, aria-labels), sanitization hook, link safety (`target="_blank" rel="noopener noreferrer"`), responsive table | — |
| S07 | tests-impl | Unit tests: streaming bridge (asserts first token arrives before last), aggregator (fixture rows across 4 tables; filters/sort/pagination), markdown sanitizer (XSS vectors + markdown subset). Integration test for `/jobs` endpoints using PostgreSQL testcontainer | — |
| S08 | code-review-impl | Review S07: coverage, assertions, no live-DB leaks, testcontainer fixtures | — |
| S09 | code-review-final-impl | Global cross-agent review of all changes for consistency and completeness | — |
| S10 | code-review-fix-final-impl | Apply any CRITICAL/HIGH fixes from S09 | — |
| S11 | quality-validation-impl | QV gates: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy orch/ dashboard/`, `make test-unit`, `make test-integration`, browser verification via `playwright-cli` (screenshots + live token streaming + markdown render + banner→toast + Jobs navigation) | — |

Agent slugs used: `backend-impl`, `api-impl`, `frontend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `code-review-fix-final-impl`, `quality-validation-impl`. These are the canonical slugs recognised by the `orch/cli/item_commands.py:_AGENT_STEP_TYPE_PATTERNS` inference (substring match). Earlier drafts used specialist `-review` slugs (`backend-review`, etc.) which would default to `StepType.implementation` and break fix-cycle dispatch.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: Not applicable. No Alembic migration is generated.

### API Changes

- **New endpoints**:
  - `GET /project/{project_id}/jobs` — HTML page
  - `GET /project/{project_id}/jobs/fragment/table` — htmx fragment, accepts query params `type`, `status`, `date_from`, `date_to`, `page`, `sort_by`, `sort_dir`
  - `GET /project/{project_id}/jobs/{job_type}/{job_id}` — HTML detail page (`job_type` ∈ `code_mapping|doc_generation|batch_execution|research`)
- **Modified endpoints**:
  - `POST /api/projects/{project_id}/code/qa` — unchanged wire format; implementation of internal streaming bridge is replaced
- **Removed endpoints**: None

### Frontend Changes

- **New components**:
  - `dashboard/templates/pages/project/jobs.html`
  - `dashboard/templates/pages/project/job_detail.html`
  - `dashboard/templates/fragments/jobs_table.html`
- **Modified components**:
  - `dashboard/templates/base.html` — add DOMPurify CDN script
  - `dashboard/templates/fragments/code_qa_panel.html` — markdown rendering per token
  - `dashboard/templates/fragments/code_job_report.html` — replace green banner with neutral "Last run" link
  - `dashboard/templates/fragments/nav_projects.html` — add `Jobs` sidebar link
- **Removed components**: None (the green-banner markup is *replaced* inside the same fragment file; the filename is kept to preserve the include chain in `project_code.html`)

## File Manifest

All files for this work item live under `ai-dev/active/CR-00006/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00006_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00006_S01_Backend_prompt.md` | Prompt | S01 backend implementation |
| `prompts/CR-00006_S02_CodeReview_prompt.md` | Prompt | S02 review of backend layer |
| `prompts/CR-00006_S03_Api_prompt.md` | Prompt | S03 API routes |
| `prompts/CR-00006_S04_CodeReview_prompt.md` | Prompt | S04 review of API layer |
| `prompts/CR-00006_S05_Frontend_prompt.md` | Prompt | S05 frontend templates + JS |
| `prompts/CR-00006_S06_CodeReview_prompt.md` | Prompt | S06 review of frontend layer |
| `prompts/CR-00006_S07_Tests_prompt.md` | Prompt | S07 unit + integration tests |
| `prompts/CR-00006_S08_CodeReview_prompt.md` | Prompt | S08 review of tests layer |
| `prompts/CR-00006_S09_CodeReview_Final_prompt.md` | Prompt | S09 global review |
| `prompts/CR-00006_S10_CodeReview_Fix_Final_prompt.md` | Prompt | S10 final fixes |
| `prompts/CR-00006_S11_QualityValidation_prompt.md` | Prompt | S11 QV gates + browser verification |

Reports are created during execution in `ai-dev/work/CR-00006/reports/`.

## Acceptance Criteria

### AC1: Q&A tokens stream live to the browser

```
Given the dashboard is running and a code index exists for project P
And Ollama is available and the model is warmed up
When a user submits a Q&A question with an expected response longer than 200 tokens
Then the first token appears in the assistant bubble within 1 second of Ollama emitting it
And subsequent tokens append incrementally (not all at once)
And the "..." loading state on the submit button persists until the "done" SSE frame arrives
```

Verification: `playwright-cli` records a trace showing at least 3 distinct DOM mutations on the assistant bubble with ≥200ms gaps between them for a long answer.

### AC2: Q&A responses render as sanitized markdown

```
Given the Q&A panel receives an assistant message containing markdown:
  "# Heading\n\nHere is **bold** and `inline code`.\n\n```python\nprint('hi')\n```\n\n- item 1\n- item 2"
When the response stream completes
Then the bubble contains an <h1>, <strong>, <code>, <pre><code>, and <ul><li> elements
And no raw markdown characters (#, **, backticks) are visible as literal text
```

```
Given the assistant response contains "<script>alert(1)</script>" or "<img src=x onerror=alert(1)>"
When the response is rendered
Then no <script> element is inserted into the DOM
And no onerror attribute survives sanitization
And no network request to x is made
```

Verification: unit test with known XSS vectors + `playwright-cli` DOM snapshot.

### AC3: Jobs view lists the four async operation types

```
Given a project has at least one row in each of: code_index_jobs, doc_generation_jobs, batches, project_docs (doc_type=research)
When a user navigates to /project/{project_id}/jobs
Then the table contains at least 4 rows — one per job type
And each row shows ID, Type, Title, Status, Started at, Finished at, Duration, Triggered by
And the Type filter reduces results to just the selected type(s)
And the Status filter reduces results to just the selected statuses
And clicking a row navigates to /project/{project_id}/jobs/{job_type}/{job_id}
```

### AC4: Job detail shows full parameters and artifacts

```
Given a completed code mapping job J exists
When a user navigates to /project/{project_id}/jobs/code_mapping/{J.id}
Then the page shows: llm_model, embed_model, index_tier, files_indexed, chunks_created, duration, trigger time
And a link to the generated architecture map (ProjectDoc artifact) is present if job.doc_id is set
And any errors are displayed if status == failed
```

### AC5: Green banner is replaced by toast + neutral Last-Run link

```
Given a code mapping job completes successfully
When the user is on /project/{project_id}/code
Then a success toast "Code map generated — N files, M chunks" appears and auto-dismisses after 10 seconds
And the toast is clickable, linking to the Jobs detail page for that run
And the persistent green "Code map generated successfully" banner is no longer rendered
And a compact neutral "Last run" summary (single line with link) appears in place of the previous banner
```

### AC6: Sidebar has a Jobs entry

```
Given the user has expanded a project in the sidebar
Then a link labelled "Jobs" appears between "History" and "Tests"
And the link points to /project/{project_id}/jobs
And it highlights as active when on any /jobs/* path
```

### AC7: No regressions

```
Given CR-00006 is implemented
When running: uv run ruff check . && uv run ruff format --check . && uv run mypy orch/ dashboard/ && make test-unit && make test-integration
Then all commands exit 0
```

## Rollback Plan

- **Code**: Revert the squash-merge commit. The three feature areas are interdependent in the CR but all diffs live in the new files listed above plus targeted edits to `code_qa.py`, `code_qa_panel.html`, `base.html`, `code_job_report.html`, `nav_projects.html`, `sse.py`, and the code-index job completion path.
- **Database**: Not applicable — no schema change.
- **Data**: No data loss on rollback. `DaemonEvent` rows of type `code_map_completed` inserted while the CR was live remain in the table but are ignored by the reverted toast map (they become no-ops).

## Dependencies

- **Depends on**: None (existing Ollama + QAEngine + DaemonEvent + SSE toast infrastructure is already present).
- **Blocks**: None.

## TDD Approach

### Unit tests

- `tests/unit/test_code_qa_streaming.py`:
  - Stub `QAEngine.answer_stream` with an async generator that yields 5 tokens with `await asyncio.sleep(0.1)` between them.
  - Call the SSE generator in `code_qa.py` and collect the yield-timestamps of each `data:` frame.
  - Assert: `(timestamp[-1] - timestamp[0]) ≥ 0.4s` (would be ~0s with the old buffering bug).
- `tests/unit/test_jobs_aggregator.py`:
  - Insert fixture rows into all four tables using `Base.metadata.create_all()` on a testcontainer.
  - Assert `list_jobs` returns 4 rows with correct `job_type` labels.
  - Assert type filter, status filter, date range filter, pagination, and sort order all behave as specified.
- `tests/unit/test_qa_markdown_sanitize.py`:
  - Not a Python test — place under `tests/unit/frontend/` and run via a minimal `node` harness that loads `marked` + `DOMPurify` and the helper from the panel (extract the `renderMarkdown(raw)` function into a pure helper).
  - Assert each XSS vector is neutralised; assert markdown subset renders to expected tag set.
  - If a JS test harness is not already in the project, implement the helper as a pure function tested via a tiny `tests/unit/frontend/run.mjs` and gate on `node --version` availability; otherwise, add an integration smoke-test via `playwright-cli` that navigates, submits a canned response, and inspects the DOM.

### Integration tests

- `tests/integration/test_jobs_api.py`:
  - Spin up the FastAPI app in a test client with the testcontainer DB.
  - Seed rows across all four tables.
  - Hit `GET /project/{id}/jobs`, `GET /project/{id}/jobs/fragment/table?type=code_mapping`, and `GET /project/{id}/jobs/code_mapping/{job_id}`.
  - Assert HTTP 200, HTML contains expected identifiers, filters narrow results, and detail page shows the expected fields.

### Updated tests

- Any existing `test_code_qa_*.py` tests that assert buffered behaviour must be updated to assert streaming behaviour (unlikely — grep confirms the current tests are minimal, but S07 must scan and adjust if any exist).

## Notes

- **Why Option A (query-aggregation) over Option B (new `job_runs` table)**: Option A is strictly smaller in blast radius — no migration, no dual-write, no rename, no backfill risk. If the Jobs view proves popular and we later need cross-type queries in hot paths, a canonical `job_runs` table can be added in a follow-up CR without rewriting the view.
- **Why the banner stays as a fragment (`code_job_report.html`) but with new content instead of being deleted**: the include at `project_code.html:78` and the rendering gate at `code_ui.py:114-118` both remain meaningful (we still want a "Last run" summary on the Code page). Replacing file contents in-place is a smaller diff than refactoring the include chain.
- **Why the Jobs page does not replace History**: History is work-item-centric (features, incidents, CRs — long-running multi-step flows). Jobs is single-shot background operations. Merging them would muddy both.
- **Event-emission site**: S01 must insert the `DaemonEvent` inside the same DB session/commit as the `CodeIndexJob.status = completed` update so the toast cannot be emitted for a run that later rolled back. Look for the completion path in `orch/rag/job.py` and related modules.
- **DOMPurify version**: pin to a specific CDN URL (e.g., `https://cdn.jsdelivr.net/npm/dompurify@3/dist/purify.min.js`) — not a floating tag — so behaviour is reproducible.
- **Link safety**: configure DOMPurify with `ADD_ATTR: ['target']` and a `afterSanitizeAttributes` hook that sets `rel="noopener noreferrer"` on every `<a>` with `target="_blank"`.
- **First-token latency**: Ollama cold-start can exceed 1 second regardless of streaming. AC1 measures from "Ollama emits first token" to "token appears in DOM", not from request-submission to first-paint. Verification must warm the model first.
