# Step 15: Queue, History, Search & System Status

## Context

Main project pages are complete. Now build the remaining dashboard pages.

Read these documents:
- `IW_AI_Core_Dashboard_Design.md` — sections 4.6 (queue), 4.7 (history), 4.8 (system status), 3.3 pattern 4 (search)

## Task

### 1. Queue & Backlog (`dashboard/routers/queue.py`)

Route: `GET /project/{id}/queue`

Two sections:
- **Ready for Execution** (status=approved): checkboxes for multi-select, item details (title, type, date). "Create Batch from Selected" button → `POST /project/{id}/api/batch/create-from-selection` which calls `iw batch-create`.
- **Drafts** (status=draft): list of items awaiting review. Click → item detail page. [Approve] button inline.

### 2. History (`dashboard/routers/history.py`)

Route: `GET /project/{id}/history`

- Paginated table of items with phase=done or status in (completed, failed)
- Columns: ID, type, title, status, date, duration
- Filters (URL query params, persistent): type dropdown (All/Feature/Issue/CR), date range, status
- Click row → item detail page
- Pagination: 20 items per page, page controls at bottom

### 3. Search

#### Global search bar (in sidebar or header)
- `<input>` with htmx: `hx-get="/api/search" hx-trigger="keyup changed delay:300ms" hx-target="#search-results"`
- Returns fragment with result list

#### Search results fragment (`dashboard/routers/search.py`)
- Route: `GET /api/search?q=...&project=...&type=...&limit=20`
- Queries `work_items` with tsvector FTS
- Returns HTML fragment: each result shows title, project badge, type badge, summary snippet, date, relevance
- Click → item detail page

#### Dedicated search page (optional, for full results)
- Route: `GET /project/{id}/search?q=...` — full page with filters and paginated results

### 4. System Status (`dashboard/routers/system.py`)

Route: `GET /system/status`

Panels:
- **Daemon**: status (running/stopped), PID, uptime, last poll time, poll count. [Stop] [Restart] buttons.
- **Projects**: table of all projects with enabled/disabled, item count, active batches.
- **LLM Quota**: placeholder cards for Claude (5h/7d bars) and MiniMax. Populated from daemon's quota cache (Phase 2 feature — show "Not configured" for now).
- **Git Status**: per-project git info (branch, uncommitted count, unpushed count, worktree count). Read from daemon's git status cache or query directly.

### 5. System Config Viewer

Route: `GET /system/config`

- Read-only display of `projects.toml`
- Environment configuration summary (non-sensitive values only — mask passwords)
- Active project configs (`.iw-orch.json` content for each project)

### 6. All Active Work (`/system/all-active`)

Route: `GET /system/all-active`

- Cross-project view of all non-terminal work items (status not in completed/failed, phase not done)
- Grouped by project, showing: item ID, title, type, status, current step, batch
- Quick glance at everything in flight across all projects

### 7. Tests

**Integration tests** (`tests/integration/test_dashboard_remaining.py`):
- Test: queue page shows approved items with checkboxes
- Test: history page pagination works
- Test: search returns relevant results ranked by relevance
- Test: system status shows daemon info
- Test: search with no results returns empty state

## Acceptance Criteria

- [ ] `/project/innoforge/queue` shows approved and draft items
- [ ] Batch creation from selected queue items works
- [ ] `/project/innoforge/history` shows paginated completed items with filters
- [ ] Search bar returns live results with 300ms debounce
- [ ] `/system/status` shows daemon health and project info
- [ ] `/system/all-active` shows cross-project active work
- [ ] `make test` passes, `make quality` passes
