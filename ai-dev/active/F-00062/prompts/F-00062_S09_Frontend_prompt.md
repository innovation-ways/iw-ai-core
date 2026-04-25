# F-00062_S09_Frontend_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step**: S09
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You enrich the dashboard with container-status data sourced from `docker ps` (read-only). Read-only `docker ps|inspect|logs` is allowed and necessary for the enrichment. NO state-changing docker commands. The "Force teardown" action you build calls `worktree_compose.down()` (the S03 module), NOT docker directly. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No alembic execution against live orch DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Design doc (AC10)
- S01-S08 reports
- `dashboard/routers/worktrees.py` — particularly `_collect_worktrees` (line ~308) and `worktrees_page` (line ~431)
- `dashboard/templates/pages/system/worktrees.html` — page template
- `dashboard/templates/fragments/worktree_table.html` — htmx-driven table fragment
- `dashboard/templates/fragments/worktree_files.html` (existing pattern reuse)
- `orch/daemon/worktree_compose.py` (S03) — for `is_alive`, `down`
- `orch/daemon/worktree_reaper.py` (S05) — for the classification logic and `ReaperFinding` dataclass you'll reuse

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S09_Frontend_report.md`

## Context

The existing global Worktree Health view at `/worktrees` shows git status of each active worktree. You are extending it to also show per-worktree compose stack status, with per-row actions (Open dashboard / Stream logs / Force teardown).

**No new view is created.** All changes land in the existing `system/worktrees.html` and `worktree_table.html`.

## Requirements

### 1. Enrich the worktree row data in `dashboard/routers/worktrees.py`

Extend `_collect_worktrees(db)` (line ~308) so each `WorktreeRow` (or its dict equivalent) carries:

- `container_status: Literal["running", "stopped", "missing", "n/a"]` — `n/a` for legacy items (no `worktree_compose_path`)
- `db_port: int | None`
- `app_port: int | None`
- `classification: Literal["active", "stale", "orphan", "n/a"]` — reuse `worktree_reaper.classify()` per row

Source the container status by calling a new helper, e.g., `worktree_compose.is_alive(batch_item_id)` (already exists from S03). For the dashboard's purpose, also surface "stopped" (compose project exists but no running containers).

For orphan rows (containers labelled but no matching BatchItem), append synthetic rows to the collection so the dashboard surfaces them. Use `worktree_reaper.scan()` to enumerate.

Performance: `_collect_worktrees` runs on every page load. Limit `docker ps` queries to ONE invocation per page render (label-filter once, build a map by `iwcore.batch_item`). Don't call `is_alive` per-row — that would mean N docker calls.

### 2. Update `dashboard/templates/pages/system/worktrees.html`

Add column headers to the table:
- "Container" (badge: green=running, yellow=stopped, gray=missing, blank=n/a)
- "DB :Port"
- "App :Port"
- "Class" (badge: active=neutral, stale=yellow, orphan=red)
- "Actions" (icon group: Open / Logs / Teardown)

Reuse existing table classes from the page; do not introduce new CSS.

### 3. Update `dashboard/templates/fragments/worktree_table.html`

Render the new cells. Per-row actions:

- **Open** — `<a href="http://localhost:{{ row.app_port }}" target="_blank">…</a>` (omit when `app_port is None`)
- **Logs** — htmx button: `hx-get="/worktrees/{{ row.batch_item_id }}/logs/stream"` `hx-target="#wt-logs-{{ row.batch_item_id }}"` `hx-swap="innerHTML"` (the SSE/htmx pattern is the same one used by the daemon-events feed; reuse a shared partial if one exists)
- **Force teardown** — htmx `hx-post="/worktrees/{{ row.batch_item_id }}/teardown"` `hx-confirm="Tear down this worktree's containers? This is irreversible."` `hx-target="#worktree-table"` `hx-swap="outerHTML"`

For orphan rows (no batch_item_id but a container_id), use `/worktrees/orphan/{{ container_id }}/teardown` instead, which calls `worktree_compose.down()` with the project_name parsed from the container's labels.

Apply a CSS class to highlight orphan rows (e.g., `class="row-orphan"`) — extend the existing dashboard CSS file rather than adding new files.

### 4. Add the new route handlers in `dashboard/routers/worktrees.py`

```python
@router.get("/worktrees/{batch_item_id}/logs/stream", response_class=HTMLResponse)
def worktree_logs_stream(batch_item_id: str, request: Request, ...) -> Any: ...
    # Use the existing daemon-events SSE/htmx pattern. Stream `docker logs --follow`
    # for the matching `iwcore-{batch_item_id}_*` containers, line by line.
    # Cap stream duration at 60s to avoid runaway connections.

@router.post("/worktrees/{batch_item_id}/teardown", response_class=HTMLResponse)
def worktree_teardown(batch_item_id: str, db: Session = Depends(get_db)) -> Any: ...
    # Look up batch_item, call worktree_compose.down(batch_item_id, batch_item.worktree_compose_path).
    # Emit DaemonEvent(phase='down', metadata={trigger: 'operator_force', ...}).
    # Return refreshed worktree_table fragment.

@router.post("/worktrees/orphan/{container_id}/teardown", response_class=HTMLResponse)
def worktree_orphan_teardown(container_id: str, ...) -> Any: ...
    # docker inspect to read labels, derive batch_item_id from iwcore.batch_item label,
    # call worktree_compose.down(batch_item_id_from_label, compose_path=None).
    # Return refreshed fragment.
```

Match the existing CSRF / auth patterns in the dashboard (if any). Read other POST handlers in `dashboard/routers/` for precedent.

### 5. Tests

`tests/dashboard/test_worktrees_view.py` (or extend an existing test file):
- `test_worktrees_table_includes_container_status_columns` — render the page, parse HTML, assert column headers present
- `test_orphan_container_appears_in_table_with_orphan_class` — testcontainer-style fixture with a labelled container that has no BatchItem; assert it shows
- `test_force_teardown_invokes_compose_down` — POST to the endpoint; mock `worktree_compose.down`; assert called with the right args

Frontend JS lint: per `CLAUDE.md` Common Commands, `make lint` runs `node --check` on `dashboard/static/**/*.js`. If you add JS, ensure it passes.

## Project Conventions

- Read `CLAUDE.md` and `dashboard/CLAUDE.md`
- htmx + Jinja2 fragments — no new build pipeline
- Reuse existing CSS classes; avoid new CSS files unless necessary
- SSE pattern matches the daemon-events feed (look at how `/daemon/events/stream` works — your logs endpoint mirrors it)

## TDD Requirement

RED → GREEN for the route handlers. Render-tests in `tests/dashboard/` are sufficient; full Playwright validation is an optional follow-up since the user explicitly waived browser evidence for this Feature.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass
2. `make lint` (includes `node --check` on dashboard JS)
3. Visual smoke test in your worktree's dashboard: load `/worktrees`, confirm columns render, confirm at least one row shows container status. Capture a screenshot to `ai-dev/active/F-00062/evidences/post/F-00062-worktree-health.png` if you have `playwright-cli` configured.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "frontend-impl",
  "work_item": "F-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/worktrees.py",
    "dashboard/templates/pages/system/worktrees.html",
    "dashboard/templates/fragments/worktree_table.html",
    "tests/dashboard/test_worktrees_view.py",
    "<any CSS file extended>"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
