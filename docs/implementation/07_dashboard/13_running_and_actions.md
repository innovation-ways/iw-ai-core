# Step 13: Running Tasks Page, Action Endpoints & SSE

## Context

Dashboard foundation is complete. Now build the most critical page: Running Tasks — the operational control center. Plus all action endpoints and real-time SSE updates.

Read these documents:
- `IW_AI_Core_Dashboard_Design.md` — sections 4.2 (running tasks wireframe), 3.3 (htmx patterns), 5 (SSE), 9.2-9.4 (routes)
- `IW_AI_Core_Daemon_Design.md` — section 5 (dashboard action handlers)

## Task

### 1. Running Tasks Page (`dashboard/routers/running.py`)

Route: `GET /system/running`

Three sections:
- **Running Now**: All step_runs with status='running' across all projects. Show: project, item, step, agent, PID, live duration, [Kill] button.
- **Failed / Needs Attention**: All workflow_steps with status in ('failed', 'needs_fix', 'stalled'). Show: project, item, step, error message, [Restart] [Skip] buttons.
- **Recently Completed** (last hour): step_runs completed in the last hour. Show: project, item, step, duration, result.

Use htmx SSE for live updates (running table refreshes when events arrive).

Also create per-project filtered view: `GET /project/{id}/running` — same layout, filtered to one project.

### 2. Action Endpoints (`dashboard/routers/actions.py`)

All actions from the Daemon Design doc section 5:

#### `POST /project/{id}/api/item/{iid}/kill-step/{n}`
- Find active step_run, send SIGTERM, update status to killed
- Return htmx fragment (updated table row) or redirect

#### `POST /project/{id}/api/item/{iid}/restart-step/{n}`
- Create new step_run with status=pending, copy command/worktree from last run
- Reset workflow_step to pending
- Daemon picks up on next poll

#### `POST /project/{id}/api/item/{iid}/skip-step/{n}`
- Mark step as skipped, workflow advances

#### `POST /project/{id}/api/item/{iid}/restart-from/{n}`
- Reset all steps >= n to pending
- Create pending step_run for step n

#### Confirmation dialog endpoint
`GET /project/{id}/api/confirm/{action}/{iid}/{step_n}`
- Returns HTML fragment for the confirmation modal
- Used by htmx for destructive actions (kill, skip)

### 3. SSE Event Stream (`dashboard/routers/sse.py`)

#### `GET /api/stream/events`
- Server-Sent Events endpoint using FastAPI's StreamingResponse
- Polls `daemon_events` table every 5 seconds for new events
- Maps event types to SSE event names (see Dashboard Design section 5.2):
  - step_launched/completed/killed → `running-update` (refresh running table)
  - step_failed/timeout/batch_completed → `toast` (notification)
- Client-side: htmx `sse-connect` attribute on the running table, JavaScript for toasts

### 4. Toast Notifications (`dashboard/templates/components/toast.html`)

- Jinja2 macro for toast message rendering
- JavaScript to display toasts from SSE events: slide in from top-right, auto-dismiss after 10s, click to navigate
- Color-coded by severity: success (green), warning (yellow), error (red), info (blue)
- Stack up to 5, oldest dismissed first

### 5. htmx Fragment Templates

Create fragments for partial page updates (no base layout):
- `dashboard/templates/fragments/running_table.html` — just the table body rows
- `dashboard/templates/fragments/toast_message.html` — single toast
- `dashboard/templates/fragments/step_row.html` — single step row update

### 6. Integration Test

**Integration tests** (`tests/integration/test_dashboard_actions.py`):
- Test: kill-step endpoint sends SIGTERM (mocked) and updates DB
- Test: restart-step creates new pending step_run with correct fields
- Test: skip-step marks step as skipped
- Test: restart-from resets all downstream steps
- Test: actions reject invalid states (e.g., restart a running step → error)

## Acceptance Criteria

- [ ] `/system/running` shows all running steps across all projects
- [ ] Duration counters update live (every second via JS)
- [ ] [Kill] button sends SIGTERM and updates the table without page reload
- [ ] [Restart] button creates new step_run, table updates
- [ ] [Skip] button marks step skipped, table updates
- [ ] SSE notifications appear as toasts for failures and completions
- [ ] Destructive actions show confirmation dialog first
- [ ] `make test` passes, `make quality` passes
