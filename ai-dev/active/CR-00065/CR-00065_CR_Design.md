# CR-00065: Live Agent Session Log Viewer

**Type**: Change Request
**Priority**: Medium
**Reason**: `pi` runtime produces 0-byte log files (it writes to `~/.pi/agent/sessions/` not stdout), making it impossible to diagnose running or crashed steps. All 3 runtimes need live-accessible logs.
**Created**: 2026-05-20
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item adds one new nullable column to `step_runs`. The Database step generates the Alembic migration file; the daemon applies it via the merge pipeline.

## Description

Agent steps running under the `pi` runtime write all conversational output — tool calls, assistant messages, thinking blocks — to `~/.pi/agent/sessions/{slug}/{timestamp}_{uuid}.jsonl`, not to stdout. The `log_file` captured by the daemon is therefore always empty for `pi` runs, leaving operators with no visibility into what the agent did or why it crashed. This CR adds a **Logs icon column** (immediately right of the Status column) in the item steps table that opens a live popup rendering the real session content for all three runtimes (`pi`, `claude`, `opencode`), with auto-refresh every 3 seconds while the step is in progress.

## Project Context

Read `CLAUDE.md` for architecture, conventions, and hard rules. Key areas:
- Dashboard is FastAPI + Jinja2 + htmx (`dashboard/`); routers are thin — logic in `orch/`.
- `StepRun` is append-only in `orch/db/models.py`; each retry is a new row.
- `step_monitor.py` in `orch/daemon/` runs every poll cycle and checks PID liveness.
- `item_steps_table.html` is the fragment that renders the step table inside item detail.
- Plain CSS goes directly to `dashboard/static/styles.css` (Tailwind toolchain may be broken in worktrees — see CLAUDE.md).

## Current Behavior

- For `claude` and `opencode` runs: the daemon captures stdout to `StepRun.log_file` (e.g. `ai-dev/logs/CR-XXXXX_S01_run1.log`). `StepRun.log_content` holds an ANSI-stripped tail. These are accessible from the Logs tab on the item detail page, but not directly from the step pipeline table.
- For `pi` runs: stdout is empty. `StepRun.log_file` points to a 0-byte file. The actual session is stored by `pi` in `~/.pi/agent/sessions/{cwd-slug}/{timestamp}_{uuid}.jsonl` — a JSONL file containing typed events: messages (role=assistant/user/toolResult), compaction, and error entries.
- The item steps table (`item_steps_table.html`) has no per-step log access widget. Users must navigate to the Logs tab and select a run manually.
- There is no live-updating log view for in-progress steps.

## Desired Behavior

- A new **"Logs" column** (icon button, right of Status) in `item_steps_table.html` opens a modal popup showing the rendered session log for the most recent run of that step.
- **For `pi` runs**: the popup parses the session JSONL and renders a structured view: assistant text (readable), thinking blocks (collapsed/expandable), tool calls (`tool_name: summary_of_args`), tool results (first 300 chars), and error events. The session file path is resolved by `step_monitor` and stored in the new `StepRun.session_file` column on the first poll cycle after step launch.
- **For `claude` / `opencode` runs**: the popup shows the captured log file content (ANSI-stripped, tail-limited), sourced from `StepRun.log_file`.
- **While the step is `in_progress`**: the popup auto-refreshes every 3 seconds via `hx-trigger="load, every 3s"` htmx polling.
- **For completed/failed steps**: the popup shows the final log snapshot (no polling).
- **For completed steps**: `StepRun.session_file` retains the historical path so past runs remain inspectable.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `step_runs` table | No session file tracking | New `session_file TEXT NULL` column |
| `orch/daemon/step_monitor.py` | Checks PID alive; emits warnings | Also resolves + stores pi session file path on first poll |
| `orch/daemon/session_reader.py` | Does not exist | New module: reads pi JSONL or log_file and returns rendered HTML-safe segments |
| `dashboard/routers/items.py` | Logs tab only; no per-step log endpoint | New `GET .../step/{step_id}/session-log` fragment endpoint |
| `dashboard/templates/fragments/item_steps_table.html` | No Logs column | New Logs icon column with htmx popup trigger |
| `dashboard/templates/fragments/session_log_popup_content.html` | Does not exist | New popup fragment template |

### Breaking Changes

- None. New DB column is nullable; new endpoint is additive; template changes are additive.

### Data Migration

- New nullable column `session_file TEXT` on `step_runs`. No backfill needed — existing rows remain NULL; only new `pi` runs will have the column populated.
- Reversible: `alembic downgrade` drops the column (no data dependency).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add `session_file TEXT NULL` to `step_runs`; Alembic migration | — |
| S02 | qv-gate | `make migration-check` — round-trip test | — |
| S03 | backend-impl | `step_monitor` resolves + stores pi session file; `session_reader` module | — |
| S04 | api-impl | `GET /project/{id}/api/item/{item_id}/step/{step_id}/session-log` fragment endpoint | — |
| S05 | frontend-impl | Logs column in `item_steps_table.html`; `session_log_popup_content.html` fragment; CSS | — |
| S06 | code-review-impl | Review S01–S05 | — |
| S07 | code-review-fix-impl | Fix CRITICAL/HIGH findings | — |
| S08 | code-review-final-impl | Cross-agent final review | — |
| S09 | code-review-fix-final-impl | Fix final findings | — |
| S10 | qv-gate | `make test-integration` | — |
| S11 | qv-browser | Browser verification — popup opens, renders content, live-refreshes | — |
| S12 | self-assess-impl | Self-assessment | — |

### Database Changes

- **New tables**: None
- **Modified tables**: `step_runs` — add `session_file TEXT NULL`
- **Migration notes**: Non-destructive nullable add; no default needed

### API Changes

- **New endpoints**: `GET /project/{project_id}/api/item/{item_id}/step/{step_id}/session-log?run_number={n}` — returns an HTML fragment with rendered log content for the specified step's latest (or specified) run
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: `dashboard/templates/fragments/session_log_popup_content.html` — popup modal with rendered log view; htmx polling when in_progress
- **Modified components**: `dashboard/templates/fragments/item_steps_table.html` — new Logs column header + per-row icon button

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00065_CR_Design.md` | Design | This document |
| `CR-00065_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00065_S01_Database_prompt.md` | Prompt | Database step |
| `prompts/CR-00065_S02_MigrationCheck_prompt.md` | Prompt | QV migration-check |
| `prompts/CR-00065_S03_Backend_prompt.md` | Prompt | Backend step |
| `prompts/CR-00065_S04_Api_prompt.md` | Prompt | API step |
| `prompts/CR-00065_S05_Frontend_prompt.md` | Prompt | Frontend step |
| `prompts/CR-00065_S06_CodeReview_prompt.md` | Prompt | Code review |
| `prompts/CR-00065_S07_CodeReviewFix_prompt.md` | Prompt | Code review fix |
| `prompts/CR-00065_S08_CodeReviewFinal_prompt.md` | Prompt | Final code review |
| `prompts/CR-00065_S09_CodeReviewFixFinal_prompt.md` | Prompt | Final code review fix |
| `prompts/CR-00065_S10_QvGate_prompt.md` | Prompt | QV integration tests |
| `prompts/CR-00065_S11_BrowserVerification_prompt.md` | Prompt | Browser verification |
| `prompts/CR-00065_S12_SelfAssess_prompt.md` | Prompt | Self-assessment |

## Acceptance Criteria

### AC1: Logs button visible in step table

```
Given a user is viewing any item's detail page
When the step pipeline table renders
Then a "Logs" icon button is visible in a column immediately right of "Status"
  for each step that has at least one run (step_runs row exists)
And the button is absent (or greyed out) for steps with no runs yet (pending, synthetic)
```

### AC2: Popup opens and shows log content for pi run

```
Given a step that ran with the pi runtime
And the step has a session_file path stored in step_runs
When the user clicks the Logs button for that step
Then a modal popup opens
And the popup displays the rendered pi session: assistant messages, tool calls,
  thinking block summaries, and any error events
And raw JSONL is not shown
```

### AC3: Popup shows log content for claude/opencode run

```
Given a step that ran with the claude or opencode runtime
When the user clicks the Logs button for that step
Then the popup displays the captured log file content (ANSI-stripped)
```

### AC4: Live refresh while in_progress

```
Given a step is currently in_progress
When the user opens the Logs popup for that step
Then the popup content refreshes every 3 seconds
And new content appended to the session since the popup opened becomes visible
```

### AC5: session_file stored for pi runs

```
Given a pi step is launched by the daemon
When the daemon's step_monitor runs its next poll cycle (≤ 60s after launch)
Then step_runs.session_file is populated with the absolute path to the pi session .jsonl file
```

### AC6: Completed runs retain session_file

```
Given a pi step that has completed or failed
When the user clicks the Logs button
Then the popup shows the session content (from session_file path)
And session_file is not NULL in the step_runs row
```

## Rollback Plan

- **Database**: `alembic downgrade -1` drops the `session_file` column. No data loss — column is nullable and new.
- **Code**: Revert the merge commit. No feature flags needed.
- **Data**: No data loss on rollback; `session_file` values are re-derivable from the pi session directory if needed.

## Dependencies

- **Depends on**: None
- **Blocks**: CR-00066 (context window progress bar — that CR also adds columns to the StepRun model and the item steps table; sequential execution recommended to avoid merge conflicts)

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/daemon/step_monitor.py`
- `orch/daemon/session_reader.py`
- `dashboard/routers/items.py`
- `dashboard/templates/fragments/item_steps_table.html`
- `dashboard/templates/fragments/session_log_popup_content.html`
- `dashboard/static/styles.css`
- `tests/integration/test_step_run_session_file.py`
- `tests/dashboard/test_items_session_log.py`

## TDD Approach

- **Unit tests**: `session_reader` parsing logic — valid JSONL with assistant/tool/thinking entries; malformed lines; empty file; non-pi run falls back to log_file.
- **Integration tests**: `test_step_run_session_file.py` — Alembic migration round-trip; `session_file` column readable/writable via ORM.
- **Integration tests**: `test_items_session_log.py` — GET endpoint returns 200 with rendered fragment; pi mock with JSONL fixture; claude/opencode mock with log_file fixture; 404 for unknown step.
- **Updated tests**: Any existing tests that construct `StepRun` objects may need the new nullable column (should be backward-compatible).

## Notes

- The pi session slug is derived from the worktree path: `path.replace("/", "-")`, e.g. `/home/user/.../CR-00065` → `--home-user---CR-00065--`. `step_monitor` can reconstruct this from `StepRun.worktree_path` without storing it separately.
- Pi sessions are stored under `~/.pi/agent/sessions/{slug}/`. The daemon process running as the same user as pi will have read access. In a future per-worktree-container model, this path may need to be configurable.
- The session JSONL uses `type: "compaction"` entries as context-reset markers. The renderer should show a visual divider at compaction points.
- For `claude` runs: consider using `log_content` (DB column) instead of re-reading from disk, to avoid file I/O on every poll.
- The `pi -p` (print mode) never writes a final stdout line because it dies before completing on context overflow — the JSONL is the only record of what happened.
