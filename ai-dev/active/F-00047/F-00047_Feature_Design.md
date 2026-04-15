# F-00047: Code Understanding: Dashboard Code Tab + Job UI

**Type**: Feature
**Priority**: High
**Created**: 2026-04-15
**Status**: Draft
**Depends on**: F-00046
**Blocks**: F-00048, F-00049

---

## Description

Adds a "Code" tab to each project's sub-navigation in the dashboard. The page renders the Level 1 architecture map (markdown narrative + Mermaid diagram) for the project's code understanding index. It shows a job status panel with live SSE-based progress during indexing, provides action buttons (Generate Code Map, Re-index changed files, Regenerate Map) with a dropdown, and shows a completion report after the job finishes.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key points:
- FastAPI + Jinja2 + htmx (no TypeScript, no build step)
- Tailwind CSS loaded from CDN — do NOT use dynamic class construction
- SSE already used via `hx-ext="sse"` pattern in existing fragments
- Templates in `fragments/` must NOT extend `base.html`
- Routes are thin — business logic belongs in `orch/` layer

## Scope

### In Scope

- `GET /project/{project_id}/code` — new page route rendering Code tab
- `GET /project/{project_id}/api/code/status` — JSON/fragment endpoint returning current index status and latest job
- `GET /project/{project_id}/api/code/index/stream` — SSE endpoint for live job progress
- `POST /project/{project_id}/api/code/index` — trigger full index + map generation
- `POST /project/{project_id}/api/code/reindex` — trigger incremental re-index only
- `POST /project/{project_id}/api/code/regen-map` — trigger Level 1 map regeneration only (no re-index)
- Template `dashboard/templates/project_code.html` — main Code tab page
- Template `dashboard/templates/fragments/code_architecture_view.html` — Level 1 doc render
- Template `dashboard/templates/fragments/code_job_status.html` — live job progress panel
- Template `dashboard/templates/fragments/code_empty_state.html` — no-index empty state
- Template `dashboard/templates/fragments/code_job_report.html` — completion report panel
- Nav entry "Code" added to `dashboard/templates/fragments/nav_projects.html`
- Mermaid.js CDN script added to `dashboard/templates/base.html` if not present
- Unit tests for the new route handlers (mocked DB)
- Integration tests for the SSE stream endpoint

### Out of Scope

- Actual indexing logic (F-00046)
- Ollama/embedding calls
- CLI commands (F-00049)
- Level 2/3 architecture maps (F-00048, F-00049)

---

## UI Design

### Route

```
GET /project/{project_id}/code
```

### Tab Strip (in nav_projects.html sub-nav)

The sidebar nav for each project gains a "Code" link:
```
/project/{project_id}/code
```
Appended after "Research" in the existing link list.

### Code Tab — Has Index State

```
/projects/{project_id}/code

┌─────────────────────────────────────────────────────────┐
│ PROJECT: My Project                                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  CODE UNDERSTANDING          [Generate Code Map ▼]      │
│  Provider: local (balanced) · gemma4:26b · qwen3-8b    │
│  Last indexed: 3 days ago · 247 files · 18,432 chunks  │
│                                                         │
│  ┌──────────────── ARCHITECTURE ──────────────────────┐ │
│  │ {narrative description from Level 1 doc}           │ │
│  │                                                    │ │
│  │ {Mermaid diagram rendered inline}                  │ │
│  │                                                    │ │
│  │ Components:                                        │ │
│  │  • engine/   C++ sensor ingestion...   [→]         │ │
│  │  • api/      Python FastAPI backend... [→]         │ │
│  │  • worker/   Celery async workers...   [→]         │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Code Tab — Empty State (no index yet)

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│  [icon]                                              │
│  No code map generated yet.                          │
│  Provider: local (balanced) · gemma4:26b             │
│                                                      │
│  [Generate Code Map]                                 │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Code Tab — Job Running State (live SSE updates)

```
┌──────────────────────────────────────────────────────┐
│  [spinner] Indexing in progress...                   │
│  Phase: indexing                                     │
│  Files: 127 / 247 indexed                            │
│  Chunks created: 4,821                               │
│  [████████████░░░░░░░░] 51%                          │
│  2:14 elapsed                               [Cancel] │
└──────────────────────────────────────────────────────┘
```

### Code Tab — Job Completion Report

```
┌──────────────────────────────────────────────────────┐
│  [checkmark] Code map generated successfully         │
│  Duration: 4m 32s                                    │
│  Files indexed: 247   Chunks: 18,432                 │
│  Languages: Python (198), C++ (49)                   │
│  Model: gemma4:26b · Embed: qwen3-embedding:8b       │
└──────────────────────────────────────────────────────┘
```

### Generate Button Dropdown

```
[Generate Code Map ▼]
  ├─ Generate Code Map       (full index + Level 1 map)
  ├─ Re-index changed files  (incremental index only)
  └─ Regenerate Map          (Level 1 map only, no re-index)
```

The dropdown is implemented as a pure CSS/JS details-summary or a simple positioned div toggled by a button click — no third-party framework.

---

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | api-impl | SSE endpoint + status/architecture fragments + 3 trigger POST endpoints + DELETE cancel endpoint in `dashboard/routers/code_ui.py` | — |
| S02 | code-review-impl | Review S01 API work | — |
| S03 | frontend-impl | All 5 templates + nav update + base.html Mermaid script | — |
| S04 | code-review-impl | Review S03 frontend work | — |
| S05 | code-review-final-impl | Final cross-agent review | — |
| S06 | qv-gate (lint) | `uv run ruff check .` | — |
| S07 | qv-gate (format) | `uv run ruff format --check .` | — |
| S08 | qv-gate (typecheck) | `uv run mypy orch/ dashboard/` | — |
| S09 | qv-gate (unit-tests) | `uv run pytest tests/unit/ -v` | — |
| S10 | qv-gate (integration-tests) | `uv run pytest tests/integration/ -v --alluredir=allure-results` | — |
| S11 | qv-browser | `playwright-cli` verification of Code tab golden paths (empty state, dropdown open/close, running-job SSE, architecture Mermaid SVG, cancel path) | — |

---

## Route Specification

### Page Route (HTML)

```
GET /project/{project_id}/code
```

Router module: `dashboard/routers/code_ui.py`  
Template: `dashboard/templates/project_code.html`

Template context variables:
- `current_project` — `Project` ORM object
- `index_status` — dict or None:
  ```python
  {
    "provider": str,                   # e.g. "local (balanced)"
    "llm_model": str,                  # e.g. "gemma4:26b" — CodeIndexJob.llm_model
    "embed_model": str,                # e.g. "qwen3-embedding:8b" — CodeIndexJob.embed_model
    "last_indexed_at": datetime | None,  # CodeIndexJob.completed_at
    "files_count": int,                # CodeIndexJob.files_indexed
    "chunks_count": int,               # CodeIndexJob.chunks_created
    "languages_detected": list[str],   # CodeIndexJob.languages_detected (JSONB)
    "level1_doc_markdown": str | None, # resolved from CodeIndexJob.doc_id → ProjectDoc.content
  }
  ```
- `running_job` — `CodeIndexJob` ORM object or None
- `last_completed_job` — `CodeIndexJob` ORM object or None
- `last_completed_recent` — `bool` — True when `(now() - last_completed_job.completed_at) < 1 hour`. Computed in the route handler; the template does not do time math.
- `last_completed_duration` — `str | None` — pre-formatted duration (e.g. `"4m 32s"`) computed in the route handler from `(completed_at - triggered_at)`. The template does not do time math.
- `arch_doc` — the `ProjectDoc` ORM object for the architecture map, or `None`. Loaded from `DocService.get_doc(project_id, "architecture-map")` when `last_completed_job.doc_id` is set.
- `content_html` — `str | None` — the architecture doc's markdown rendered to HTML with ` ```mermaid ` fenced blocks pre-processed into `<div class="mermaid">...</div>` wrappers. Computed by the route handler via a shared helper (see below). `None` when no architecture doc exists.

> **Field sourcing note (Option C)**: `CodeIndexJob` is defined by F-00045 with columns `llm_model`, `embed_model`, `files_indexed`, `chunks_created`, `languages_detected`, `doc_id`, `triggered_at`, `completed_at` (see F-00045 Database Schema). The `level1_doc` Markdown is NOT stored on `CodeIndexJob` directly — it lives in the `ProjectDoc` referenced by `CodeIndexJob.doc_id` (composite id `{project_id}:architecture-map`). F-00047 route handlers must join-load / fetch that `ProjectDoc` when rendering the architecture view. There is no `job_type`, `chat_model`, `languages_json`, `duration_formatted`, or `completed_recently` on the ORM model — the route handler derives display values instead.

### API Endpoints (HTML fragments)

```
GET  /project/{project_id}/api/code/status
     Returns: code_job_status.html fragment or code_empty_state.html
     Poll target: #code-status-panel

POST /project/{project_id}/api/code/index
     Body: (empty)
     Action: creates CodeIndexJob(status="queued"), calls start_index_job(job, project, mode="full"),
             schedules runner via BackgroundTasks
     Returns: code_job_status.html fragment

POST /project/{project_id}/api/code/reindex
     Body: (empty)
     Action: creates CodeIndexJob(status="queued"), calls start_index_job(..., mode="incremental"),
             schedules runner via BackgroundTasks
     Returns: code_job_status.html fragment

POST /project/{project_id}/api/code/regen-map
     Body: (empty)
     Action: creates CodeIndexJob(status="queued"), calls start_index_job(..., mode="mapgen_only"),
             schedules runner via BackgroundTasks
     Returns: code_job_status.html fragment

GET  /project/{project_id}/api/code/index/stream
     Media-type: text/event-stream
     Streams: progress events until job completes or no running job
     Format: see SSE Event Schema below

GET  /project/{project_id}/api/code/architecture
     Returns: code_architecture_view.html fragment
     Used for htmx refresh after job completes

DELETE /project/{project_id}/api/code/index
     Action: cooperatively cancel the currently running CodeIndexJob for the project.
             Looks up the runner in JOB_REGISTRY[project_id]; calls runner.request_cancel()
             (exposed by F-00046). The runner checks the flag at its next awaitable
             checkpoint, emits a terminal SSE event {"event":"done","status":"cancelled"},
             and updates the DB row to status="cancelled" in its finally block.
     Returns: code_job_status.html fragment on the in-flight cancel
              (so the UI immediately swaps to a "Cancelling..." state),
              or 404 if no running job exists for the project.
```

### SSE Event Schema

Progress events sent by `/api/code/index/stream`:

```json
{
  "event": "progress",
  "phase": "indexing | embedding | map_generation | done | error",
  "files_indexed": 127,
  "files_total": 247,
  "chunks_created": 4821,
  "elapsed_seconds": 134,
  "message": "Indexing file 127/247: src/engine/sensor.cpp"
}
```

Terminal event (job done):
```json
{"event": "done", "status": "completed", "job_id": "abc123"}
```

Terminal event (job failed):
```json
{"event": "done", "status": "failed", "error": "Connection refused to Ollama"}
```

Terminal event (job cancelled):
```json
{"event": "done", "status": "cancelled", "job_id": "abc123"}
```

No running job:
```json
{"event": "done", "status": "idle"}
```

---

## Template Specification

### `dashboard/templates/project_code.html`

Extends `base.html`. Sets `current_project` for sidebar. Layout:
1. Page header: "Code Understanding" title + dropdown action button (top right)
2. Meta bar: provider · models · last indexed · file/chunk counts
3. `#code-status-panel` div — conditionally renders:
   - If `running_job`: `code_job_status.html` fragment (with SSE listener)
   - If `last_completed_job` and recently finished: `code_job_report.html` fragment
4. `#code-architecture-panel` div — conditionally renders:
   - If `content_html` is non-null (i.e. the architecture `ProjectDoc` exists): `code_architecture_view.html` fragment
   - Else: `code_empty_state.html` fragment

Both the page route (`GET /project/{id}/code`) and the architecture fragment route (`GET /api/code/architecture`) MUST use the same `_render_architecture_html(arch_doc)` helper so the server-side pre-processed HTML passed to the template is identical on initial load and after htmx refresh. The helper returns `None` when `arch_doc` is missing.

### `dashboard/templates/fragments/code_architecture_view.html`

Does NOT extend `base.html`. Shows:
- Section heading "Architecture"
- Rendered markdown content (use `marked.js` like existing docs renderer, or server-side render via `render_markdown()` helper)
- Mermaid diagrams extracted from markdown fenced code blocks and placed in `<div class="mermaid">...</div>` for auto-rendering
- Components list (if present in Level 1 doc): bulleted list with arrow link per component

### `dashboard/templates/fragments/code_job_status.html`

Does NOT extend `base.html`. Shows live job progress:
- Spinner + "Indexing in progress..." or phase-specific label
- Phase indicator
- Files progress: "127 / 247 indexed"
- Chunks created count
- Progress bar: `<div style="width: {pct}%">` where pct = files_indexed/files_total*100
- Elapsed time counter (JS interval, same pattern as `docs_job_status.html`)
- Cancel button: `hx-delete` to cancel endpoint
- Uses vanilla JS `EventSource` to connect to `/project/{project_id}/api/code/index/stream`
- Updates UI elements directly (not via hx-ext="sse" swap — direct JS DOM manipulation for fine-grained updates)

### `dashboard/templates/fragments/code_empty_state.html`

Does NOT extend `base.html`. Shows:
- SVG icon (code/terminal style)
- "No code map generated yet." heading
- Provider/model info line
- "Generate Code Map" button (hx-post to `/api/code/index`)

### `dashboard/templates/fragments/code_job_report.html`

Does NOT extend `base.html`. Shows completion summary:
- Green checkmark icon + "Code map generated successfully"
- Duration
- Files indexed / chunks count
- Languages breakdown (Python N, C++ N, etc.)
- Model used

---

## Mermaid Integration

Add to `dashboard/templates/base.html` inside `{% block head %}` or after marked.js:

```html
<!-- Mermaid.js for code architecture diagrams -->
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<script>
  mermaid.initialize({ startOnLoad: true, theme: 'default' });
</script>
```

After any htmx swap that may contain Mermaid diagrams, reinitialize:
```javascript
document.body.addEventListener('htmx:afterSwap', function(e) {
  if (e.detail.target && e.detail.target.querySelector('.mermaid')) {
    mermaid.init(undefined, e.detail.target.querySelectorAll('.mermaid'));
  }
});
```

---

## SSE Client Pattern

The `code_job_status.html` fragment uses vanilla JS `EventSource` (NOT htmx `hx-ext="sse"`) because the progress updates require fine-grained DOM manipulation (progress bar width, multiple counters):

```javascript
(function() {
  var es = new EventSource('/project/PROJECT_ID/api/code/index/stream');
  es.onmessage = function(e) {
    var data = JSON.parse(e.data);
    if (data.event === 'progress') {
      // update phase, files_indexed, files_total, chunks, elapsed, progress bar
    } else if (data.event === 'done') {
      es.close();
      if (data.status === 'completed' || data.status === 'failed') {
        // reload #code-status-panel and #code-architecture-panel via htmx
        htmx.ajax('GET', '/project/PROJECT_ID/api/code/status', {target: '#code-status-panel', swap: 'innerHTML'});
        htmx.ajax('GET', '/project/PROJECT_ID/api/code/architecture', {target: '#code-architecture-panel', swap: 'innerHTML'});
      }
    }
  };
  es.onerror = function() { es.close(); };
})();
```

---

## Dropdown Button Pattern

Pure CSS/JS — no framework:

```html
<div class="relative" id="code-action-dropdown">
  <button onclick="toggleCodeDropdown()"
          class="inline-flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90">
    Generate Code Map
    <svg class="w-4 h-4"><!-- chevron down --></svg>
  </button>
  <div id="code-dropdown-menu" class="hidden absolute right-0 top-full mt-1 w-52 bg-card border border-border rounded-md shadow-lg z-10">
    <button hx-post="..." class="block w-full text-left px-4 py-2 text-sm hover:bg-muted">Generate Code Map</button>
    <button hx-post="..." class="block w-full text-left px-4 py-2 text-sm hover:bg-muted">Re-index changed files</button>
    <button hx-post="..." class="block w-full text-left px-4 py-2 text-sm hover:bg-muted">Regenerate Map</button>
  </div>
</div>
<script>
function toggleCodeDropdown() {
  document.getElementById('code-dropdown-menu').classList.toggle('hidden');
}
document.addEventListener('click', function(e) {
  if (!e.target.closest('#code-action-dropdown')) {
    document.getElementById('code-dropdown-menu').classList.add('hidden');
  }
});
</script>
```

---

## File Manifest

| File | Action |
|------|--------|
| `dashboard/routers/code_ui.py` | Create — all route handlers |
| `dashboard/app.py` | Modify — register new `code_ui` router |
| `dashboard/templates/project_code.html` | Create — main Code tab page |
| `dashboard/templates/fragments/code_architecture_view.html` | Create — Level 1 doc render |
| `dashboard/templates/fragments/code_job_status.html` | Create — live progress panel |
| `dashboard/templates/fragments/code_empty_state.html` | Create — empty state |
| `dashboard/templates/fragments/code_job_report.html` | Create — completion report |
| `dashboard/templates/fragments/nav_projects.html` | Modify — add "Code" nav link |
| `dashboard/templates/base.html` | Modify — add Mermaid.js CDN script |
| `tests/unit/test_code_ui_routes.py` | Create — unit tests for route handlers |
| `tests/integration/test_code_sse.py` | Create — integration tests for SSE stream |

---

## Quality Gates

All gates must pass before the feature is considered complete:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy orch/ dashboard/
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v --alluredir=allure-results
```

Browser verification is required: use `playwright-cli` to confirm the Code tab renders, the dropdown opens, and the empty state displays correctly.

---

## Acceptance Criteria

### AC1: Code nav link appears and routes correctly

```
Given a project is registered in the dashboard
When a user expands the project in the sidebar nav
Then a "Code" link appears after "Research"
 And clicking it navigates to GET /project/{project_id}/code
 And the page returns HTTP 200 with the Code tab highlighted as active
```

### AC2: Empty state when no index exists

```
Given a project has no completed CodeIndexJob
When a user visits /project/{project_id}/code
Then the page renders the empty-state fragment
 And a "Generate Code Map" button is visible
 And no architecture view is rendered
```

### AC3: Architecture view renders Level 1 doc with Mermaid

```
Given a project has a completed CodeIndexJob with a Level 1 architecture doc containing a ```mermaid fenced block
When a user visits /project/{project_id}/code
Then the page renders the architecture fragment
 And the markdown narrative is shown as HTML
 And the Mermaid block is rendered as an SVG diagram (not raw text)
```

### AC4: Job progress updates live via SSE

```
Given a CodeIndexJob is running for a project
When a user visits /project/{project_id}/code
Then the page renders the job status fragment
 And an EventSource connection is opened to the stream endpoint
 And progress events update the phase label, file counts, chunk count, and progress bar
 And on the terminal "done" event the EventSource is closed
 And both #code-status-panel and #code-architecture-panel are refreshed via htmx
```

### AC5: Action dropdown triggers correct jobs

```
Given a user is on /project/{project_id}/code with no running job
When the user opens the "Generate Code Map" dropdown and clicks a menu item
Then a POST is issued to the matching endpoint (full / incremental / regen-map)
 And the response fragment replaces #code-status-panel
 And the dropdown closes after the request
 And buttons are re-enabled after the response arrives
```

### AC6: Concurrent job rejection

```
Given a CodeIndexJob is already running for a project
When a POST is issued to any of the three trigger endpoints
Then the server returns HTTP 409
 And no new CodeIndexJob row is created
```

### AC7: Cancel running job

```
Given a CodeIndexJob is running for a project and a runner is registered in JOB_REGISTRY
When a user issues DELETE /project/{project_id}/api/code/index
Then runner.request_cancel() is called on the matching runner
 And the response is the code_job_status.html fragment reflecting a cancelling state
 And the SSE stream subsequently emits a terminal {"event":"done","status":"cancelled"} event
 And the CodeIndexJob row reaches status="cancelled" in its finally block
 And JOB_REGISTRY is cleared of the project_id entry
```

```
Given no CodeIndexJob is running for a project
When a user issues DELETE /project/{project_id}/api/code/index
Then the server returns HTTP 404
 And no state is mutated
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Unknown project | `project_id` not in DB | `GET /project/{id}/code` returns 404 |
| No completed job, no running job | empty `code_index_jobs` | Empty state fragment renders |
| Completed job with no architecture ProjectDoc | `CodeIndexJob.doc_id` is null or the referenced `ProjectDoc` is missing | Empty state fragment renders (not architecture view) |
| Running job with missing registry entry | DB row exists but `JOB_REGISTRY` empty | SSE stream sends `{"event":"done","status":"idle"}` and closes |
| Client disconnects mid-stream | `asyncio.CancelledError` raised | SSE generator exits cleanly, no server error logged |
| Mermaid CDN unavailable | `typeof mermaid === 'undefined'` | Page still renders; architecture view shows raw code block without crashing |
| Markdown with no Mermaid block | `ProjectDoc.content` has no fenced ` ```mermaid ` block | Architecture view renders HTML without inserting empty `<div class="mermaid">` |
| Duplicate trigger POST | Job already running | 409 response, no duplicate row |
| Cancel with no running job | `project_id` not in `JOB_REGISTRY` | DELETE returns 404, no state mutated |
| Cancel during map generation | Runner is past indexing but pre-DB-commit | Runner observes flag on next checkpoint, emits `done/cancelled`, row reaches `status="cancelled"` |

## Invariants

1. Exactly one `CodeIndexJob` per project is in `status='running'` at any time.
2. The SSE stream always terminates with exactly one `{"event":"done", ...}` event (or client disconnect). Valid terminal statuses: `completed`, `failed`, `cancelled`, `idle`.
3. The architecture view is rendered only when a completed job's Level 1 doc is non-null.
4. Fragment templates under `dashboard/templates/fragments/` do NOT extend `base.html`.
5. All `hx-post` URLs in templates resolve to a registered route handler (no 404s on dropdown clicks).
6. The Mermaid CDN script is loaded exactly once per page (no duplicate `<script>` tags in `base.html`).

## Dependencies

- **Depends on**: F-00046 (`orch.rag.job.start_index_job`, `JOB_REGISTRY`, `CodeIndexJobRunner`, `JobAlreadyRunningError` — Python API only, no HTTP layer; F-00046 is amended to additionally expose `CodeIndexJobRunner.request_cancel()` and a `cancelled` terminal status so F-00047's DELETE handler can cooperatively cancel a running job), F-00045 (`CodeIndexJob` ORM model, `orch/rag/config.py`, `ProjectDoc` already exists; the `code_index_job_status` ENUM must include `'cancelled'`)
- **Blocks**: F-00048, F-00049

## TDD Approach

- **Unit tests** (`tests/unit/test_code_ui_routes.py`):
  - 200 + correct template for `GET /project/{id}/code` with a mock Project and no jobs
  - 404 for unknown `project_id`
  - 200 for `GET /api/code/status` in empty and running states
  - POST endpoints create a `CodeIndexJob` row (DB mocked) and return the status fragment
  - POST endpoints return 409 when a job is already running
  - Mermaid pre-processing helper: fenced ```mermaid blocks become `<div class="mermaid">...</div>`
- **Integration tests** (`tests/integration/test_code_sse.py`):
  - Real PostgreSQL via testcontainer (NEVER port 5433)
  - SSE stream returns `done/idle` when no running job
  - SSE stream sends at least one `progress` event followed by a terminal `done` event when a fake runner is injected into `JOB_REGISTRY`
  - Client disconnect does not raise an unhandled exception on the server
- **Edge cases**:
  - Project with no `code_understanding` block in `config` JSONB (helpers must return sane defaults)
  - Completed job with `doc_id` = null or referenced `ProjectDoc` missing (empty state, not architecture view)
  - Concurrent POSTs to trigger endpoints (only one row created, second gets 409 via `JobAlreadyRunningError`)
- **Browser verification** (`playwright-cli`):
  - Code tab appears in the sidebar and navigates correctly
  - Empty state renders when no index exists
  - Dropdown opens and closes on outside click
  - With a seeded completed job, the architecture view renders and Mermaid SVG is present in the DOM

## Notes

- **Scope split with F-00046 (Option C, resolved)**: F-00046 is now library-only. It exposes `start_index_job(job, project, *, mode)`, `CodeIndexJobRunner`, `JOB_REGISTRY`, and `JobAlreadyRunningError` from `orch.rag.job`. F-00047 **owns the HTTP layer in its entirety** — there is exactly one router module, `dashboard/routers/code_ui.py`, and one URL prefix, `/project/{id}/api/code/*`. F-00047's POST handlers must call `start_index_job`, catch `JobAlreadyRunningError` → HTTP 409, and schedule `runner.run()` via FastAPI `BackgroundTasks`. The SSE handler subscribes to `JOB_REGISTRY[project_id].progress_queue` directly. If F-00046 ships before F-00047, none of its work will be reachable from the dashboard until F-00047 lands — this is intentional.
- **CodeIndexJob field mapping (resolved)**: the route handler reads from the F-00045 schema columns (`llm_model`, `embed_model`, `files_indexed`, `chunks_created`, `languages_detected`, `doc_id`, `triggered_at`, `completed_at`). The `level1_doc_markdown` display value is resolved by loading the `ProjectDoc` referenced by `CodeIndexJob.doc_id` (composite id `{project_id}:architecture-map`). Display-only values (`last_completed_recent`, `last_completed_duration`) are computed in the route handler, not read from the model. No new columns are added to `CodeIndexJob` by this feature.
- **Mode is runtime-only**: the three dropdown actions (full / incremental / regen-map) select different `mode` arguments to `start_index_job` — they do NOT persist a `job_type` column on `CodeIndexJob`. F-00045's schema intentionally has no such column.
- **Tailwind dark mode**: the CDN build must have `darkMode: 'class'` (or the equivalent) enabled for the `dark:` utility classes in the new fragments to take effect. Verify against existing templates that already use `dark:`.
- **Mermaid re-init after htmx swaps**: the global `htmx:afterSwap` listener must guard on `[data-processed]` to avoid re-rendering an already-rendered diagram on subsequent swaps.
- **No `tests-impl` step**: test writing is inlined into S01 (unit tests for route handlers + SSE integration test). If the scope grows, consider splitting a dedicated tests step.
