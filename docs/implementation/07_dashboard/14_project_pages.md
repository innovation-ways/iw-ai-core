# Step 14: Project Dashboard, Batches & Work Item Detail

## Context

Running tasks page and actions are complete. Now build the main project-scoped pages.

Read these documents:
- `IW_AI_Core_Dashboard_Design.md` — sections 4.3 (project dashboard), 4.4 (batch detail), 4.5 (work item detail)

## Task

### 1. Project Dashboard (`dashboard/routers/project_dashboard.py`)

Route: `GET /project/{id}/`

- Summary cards: active batches, running steps, completed this week
- Active batches list with progress bars and [Pause] [View] buttons
- Recent activity feed (last 20 daemon_events for this project)
- Git status panel (branch, unpushed commits, active worktrees) — read from daemon's cached git status or query directly

### 2. Batch List (`dashboard/routers/batches.py`)

Route: `GET /project/{id}/batches`

- Table of all batches: ID, status, item count, progress, created date, duration
- Status filter (tabs or dropdown): All, Executing, Completed, Failed
- Click row → batch detail

### 3. Batch Detail

Route: `GET /project/{id}/batch/{bid}`

- Header: batch ID, status, item count, max_parallel, created/completed dates
- Action buttons: [Approve] (if planning), [Pause/Resume] (if executing), [Archive] (if completed)
- Items table: item ID, execution group, status, current step, duration, actions
- Step pipeline visualization for each item (using `step_pipeline` macro)
- Tabs: Items | Timeline | Logs
  - Items: table view (default)
  - Timeline: horizontal bar chart (Gantt-style, use Chart.js or simple div bars for v1)
  - Logs: dispatcher log (if available) with auto-scroll

### 4. Work Item Detail (`dashboard/routers/items.py`)

Route: `GET /project/{id}/item/{iid}`

- Header: item ID, title, type badge, status badge, batch reference
- Summary (from `work_items.summary` if archived, or from design doc preview)
- Metric cards: total time, fix cycles, steps completed
- htmx tabs (load via fragments, no page reload):

#### Tab: Overview (default)
- Step pipeline visualization with durations per step
- For each step: status, agent, run count, duration, error message (if failed)
- Action buttons per step: [Restart] [Skip] (if failed)
- [Restart from Step N] selector

#### Tab: Design Document
- Route: `GET /project/{id}/item/{iid}/tab/design-doc`
- Render `work_items.design_doc_content` as HTML (markdown → HTML server-side)
- For active items (not archived): read from file on disk, render
- Styled with the document CSS (code blocks, tables, headings)

#### Tab: Reports
- Route: `GET /project/{id}/item/{iid}/tab/reports`
- For each step: render `workflow_steps.report_content` as HTML
- Collapsible sections per step (click step header to expand)
- Show run number if step had multiple runs

#### Tab: Full Artifacts (Tier 2, on-demand)
- Route: `GET /project/{id}/item/{iid}/tab/artifacts`
- If not archived: show file browser from `ai-dev/design/active/{id}/` on disk
- If archived: show "Load Artifacts" button → htmx calls extraction endpoint → shows file browser
- File browser: tree view with file names, sizes, click to view content (text rendered, images displayed)

### 5. Markdown Rendering Utility

Create `dashboard/utils/markdown.py`:
- Function to convert markdown string to safe HTML (using `markdown` library)
- Syntax highlighting for code blocks (optional, via Pygments or similar)
- Used by design doc tab and reports tab

### 6. Tests

**Integration tests** (`tests/integration/test_dashboard_pages.py`):
- Test: project dashboard returns 200 with correct project context
- Test: batch detail shows correct items and statuses
- Test: item detail design doc tab renders markdown as HTML
- Test: item detail reports tab shows step reports
- Test: non-existent project/batch/item returns 404

## Acceptance Criteria

- [ ] `/project/innoforge/` shows project dashboard with active batches and activity
- [ ] `/project/innoforge/batch/BATCH-001` shows batch items with step pipelines
- [ ] `/project/innoforge/item/I001` shows tabs, step pipeline, design doc
- [ ] Tabs load via htmx without page reload
- [ ] Design documents render as formatted HTML
- [ ] `make test` passes, `make quality` passes
