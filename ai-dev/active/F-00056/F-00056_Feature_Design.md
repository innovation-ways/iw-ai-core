# F-00056: Work Item Execution Report — Retry Pattern & Pain-Point Visibility

**Type**: Feature
**Priority**: Medium
**Created**: 2026-04-20
**Status**: Draft

---

## Description

Generates a per-work-item execution report that surfaces retry patterns, failure hot-spots, and fix-cycle rationale so the operator can identify systemic issues in the implementation process (e.g., F-00055 lint failed 3×, code review failed 2×, unit tests failed 2× — today that signal is buried across logs and reports). Delivered in two surfaces: an auto-generated markdown file at `ai-dev/archive/<id>/<id>_execution_report.md` (also regeneratable via `iw item-report <id>`) and a dashboard page with a summary card, a pure-CSS step Gantt chart, and an expandable retry timeline. One schema addition (`fix_cycles.fix_summary`) captures the fix agent's "what I changed and why" so the timeline tells a story instead of just linking log files.

## Project Context

Read the project's `CLAUDE.md`, `orch/CLAUDE.md`, and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules. Key references used during design:

- `orch/db/models.py:380-571` — `WorkflowStep`, `StepRun`, `FixCycle` models (data sources for the report)
- `orch/daemon/batch_manager.py:626-658` — `_complete_item()` hook point for auto-generation
- `dashboard/routers/items.py:823-1024` — existing item-detail tab routes (pattern to mirror)
- `dashboard/templates/pages/project/item_detail.html` — tab bar location
- `dashboard/templates/pages/project/batch_detail.html` — pure-CSS timeline precedent (no JS chart lib in repo)
- `orch/archive/archiver.py:26-100` — archive dir resolution
- `orch/cli/item_commands.py:460-576` — CLI command pattern

## Scope

### In Scope

- **Schema addition** — new nullable `fix_cycles.fix_summary TEXT` column; Alembic migration; `FixCycle.fix_summary` mapped field.
- **Report assembly service** — `orch/daemon/execution_report.py` (new) queries `WorkflowStep` + `StepRun` + `FixCycle` for an item and returns a structured `ExecutionReportData` dataclass containing: item metadata, ordered step rows (each with run-attempts and nested fix cycles), retry-hotspot summary, total duration, success flag.
- **Markdown renderer** — pure function `render_execution_report_markdown(data: ExecutionReportData) -> str` producing a single self-contained markdown document with four sections: (1) header + verdict, (2) retry hotspots, (3) step timeline, (4) fix-cycle details with `fix_summary` quotes. Writes to `{active_or_archive_dir}/<id>_execution_report.md`.
- **CLI command** — `iw item-report <item_id> [--project <pid>] [--stdout]` regenerates the report from current DB state. Writes to disk by default; `--stdout` prints instead.
- **Daemon auto-trigger** — extend `_complete_item()` in `orch/daemon/batch_manager.py` to call the report generator synchronously before the archive step runs, so the markdown file is captured in the `.tar.zst` archive.
- **Fix-agent contract** — the fix-cycle-executing agent must write a 1-3 bullet summary (what changed, why) to its result payload. Daemon's fix-cycle completion handler (`orch/daemon/fix_cycle.py`) parses the summary from the agent's report and writes it to `FixCycle.fix_summary`. Fix prompt templates are updated to require this.
- **Dashboard tab** — new tab "Execution Report" on the item-detail page at `/project/{pid}/item/{iid}/tab/execution-report`, served by `dashboard/routers/items.py` and rendered via a new `dashboard/templates/fragments/item_execution_report.html` fragment (htmx-loaded, matching the pattern of existing tabs). Also accessible as a standalone full-page route `/project/{pid}/item/{iid}/execution-report` for deep-link sharing.
- **Summary card** — above the Gantt, a header card with: overall verdict badge (✓ completed / ✗ failed / ⏸ stalled), total wall-clock duration (first step start → last step end), retry-hotspot list formatted as "S13 `ruff lint` × 3, S10 `Code Review` × 2, S16 `Unit Tests` × 2". Hotspots are rows where `max(run_number) >= 2`, sorted by run count desc.
- **Gantt chart** — pure-CSS horizontal bar chart (no JS chart library; matches `batch_detail.html` precedent). Full spec in [Gantt Chart Strategy](#gantt-chart-strategy) below.
- **Retry timeline** — vertical list under the Gantt, one accordion row per step that retried (`max(run_number) >= 2`). Each row header shows step ID + label + retry count + final status. Expanded body renders a chronological list of `StepRun` attempts: timestamp, duration, `error_message`, link to `report_file` (rendered inline if stored in `report_content`), and the triggered `FixCycle.fix_summary` quoted as a block-quote. Fix cycles with `fix_summary IS NULL` (pre-F-00056 data) render the placeholder "_no fix summary captured (pre-F-00056)_".
- **Backfill** — one-off CLI invocation of `iw item-report` for F-00055 and the two most recently completed work items prior to F-00055 in the `iw-ai-core` project. Reports are written to each item's active or archive directory; `fix_summary` fields are NULL, so the timeline shows the placeholder gracefully. No data migration; the generator tolerates NULLs by construction.
- **No-regression guarantee** — existing item-detail tabs (Overview, Design Doc, Reports, Artifacts, Logs, Fix Cycles, Evidences) remain unchanged in behavior and layout.

### Out of Scope

- **Cross-item aggregation dashboard** — "across last 30 items, which `step_label`s retry most, and what's the avg retry count". Deferred; data already supports it once more items have `fix_summary` populated.
- **Cost / token / latency metrics per retry** — not captured today and intentionally deferred.
- **Structured failure-category enum on `StepRun`** — categorization is derived from the existing tuple `(step_type, step_label, opencode_agent)`; no new enum column.
- **Agent consumption of reports** — future work; the markdown format is designed to be agent-consumable but no agent workflow in this feature reads prior reports.
- **Full-migration backfill** — only F-00055 + 2 priors are backfilled for visual validation; older items remain unreported.
- **JavaScript chart libraries** — d3, chart.js, etc. are not introduced; repo currently has none.
- **Streaming/SSE updates during step execution** — the report is generated on completion, not live.
- **Editing / annotating the report** — the report is read-only; any notes go in the design doc.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add `fix_summary TEXT NULL` column to `fix_cycles`; `FixCycle.fix_summary` mapped field in `orch/db/models.py`; Alembic migration under `orch/db/migrations/versions/` | — |
| S02 | code-review-impl | Review S01 (schema + migration correctness, naming, comments) | — |
| S03 | backend-impl | Report assembly service `orch/daemon/execution_report.py`; markdown renderer; `iw item-report` CLI in `orch/cli/item_commands.py`; daemon completion hook in `orch/daemon/batch_manager.py`; fix-cycle summary ingestion in `orch/daemon/fix_cycle.py`; edit fix prompt templates (`CodeReview_FIX_Prompt_Template.md`, `CodeReview_FIX_Final_Prompt_Template.md`, `QualityValidation_FIX_Prompt_Template.md`) to require `fix_summary` in the agent result contract | — (after S02) |
| S04 | code-review-impl | Review S03 (service layering, CLI pattern, hook placement, template contract changes) | — |
| S05 | api-impl | New tab route `GET /project/{pid}/item/{iid}/tab/execution-report` and standalone page route `GET /project/{pid}/item/{iid}/execution-report` in `dashboard/routers/items.py`; both call the report assembly service and render the fragment template | — (after S04) |
| S06 | code-review-impl | Review S05 (route conventions, session handling, error paths) | — |
| S07 | frontend-impl | New fragment template `dashboard/templates/fragments/item_execution_report.html`; tab button addition in `dashboard/templates/pages/project/item_detail.html`; pure-CSS Gantt styles (scoped CSS block inside the fragment or new `dashboard/static/execution_report.css`); standalone page template `dashboard/templates/pages/project/item_execution_report.html` wrapping the fragment in `base.html` | — (after S06) |
| S08 | code-review-impl | Review S07 (template conventions, a11y, CSS scoping, visual correctness) | — |
| S09 | tests-impl | Unit tests (report assembly, markdown renderer, retry-hotspot detection, Gantt data shaping, CLI, fix-summary ingestion parsing); integration tests (full end-to-end: seed an item with retries in a testcontainer PG, invoke daemon completion hook, assert markdown file written, assert dashboard route renders, assert backfill works for a seeded "F-00055-like" item with NULL summaries); execute backfill command for F-00055 + 2 priors on live DB via the CLI | — (after S08) |
| S10 | code-review-impl | Review S09 (test coverage vs AC, test isolation, no live-DB connections in unit tests) | — |
| S11 | code-review-final-impl | Global cross-agent review: database ↔ backend ↔ api ↔ frontend ↔ tests integration, AC coverage, no regressions to existing item-detail tabs | — (after S10) |
| S12 | code-review-fix-final-impl | Fix CRITICAL and HIGH findings from S11 | — (after S11) |
| S13 | qv-gate | `uv run ruff check .` | — |
| S14 | qv-gate | `uv run ruff format --check .` | — |
| S15 | qv-gate | `uv run mypy orch/ dashboard/` | — |
| S16 | qv-gate | `make test-unit` | — |
| S17 | qv-gate | `make test-integration` | — |
| S18 | qv-browser | Browser verification in isolated worktree stack: open F-00055's execution-report page, verify summary card shows 3×/2×/2× hotspots, verify Gantt renders, verify timeline expands | — |

### Database Changes

- **New tables**: None.
- **Modified tables**: `fix_cycles` — add nullable `fix_summary TEXT` column with comment `"Fix agent's 1-3 bullet summary of what changed and why; NULL for pre-F-00056 cycles"`.
- **Migration notes**: Additive only, safe forward and backward. Alembic auto-generate is acceptable; verify the `downgrade()` correctly drops the column. No data migration — pre-existing rows keep NULL and the UI handles that path.

### API Changes

- **New endpoints**:
  - `GET /project/{project_id}/item/{work_item_id}/tab/execution-report` — returns the fragment HTML (htmx-loaded by the tab bar; returns 404 if the item does not exist).
  - `GET /project/{project_id}/item/{work_item_id}/execution-report` — returns the standalone full page wrapped in `base.html`.
- **Modified endpoints**: None. The item-detail page template gains a new tab button that loads the fragment via the existing htmx pattern; no schema changes to existing endpoints.
- **Breaking changes**: None (additive routes only).

### Frontend Changes

- **New components**:
  - `dashboard/templates/fragments/item_execution_report.html` — fragment with three sections: summary card, Gantt, retry timeline.
  - `dashboard/templates/pages/project/item_execution_report.html` — standalone page wrapping the fragment in `base.html` for deep-link sharing.
  - `dashboard/static/execution_report.css` — scoped CSS for the Gantt grid, bar segments, status colors, and timeline accordion. Created only if the styles do not fit inline in the fragment's `<style>` block; fragment-inline is acceptable for consistency with other fragments.
- **Modified components**:
  - `dashboard/templates/pages/project/item_detail.html` — add one tab button ("Execution Report") in the existing tab-nav block.

## Gantt Chart Strategy

This section is normative. The implementation must match these rules exactly; deviations require re-opening the design.

### Rendering technology

- **Pure CSS + HTML only.** No JavaScript chart library (d3, chart.js, recharts, etc.). This matches the existing `dashboard/templates/pages/project/batch_detail.html` timeline precedent and keeps the dashboard footprint zero-JS-dependency.
- Rendered via Jinja2 loop emitting `<div>` grid cells with inline `style="left: …%; width: …%;"` attributes; the class hierarchy carries status colors.
- Must render correctly with CSS alone when JavaScript is disabled in the browser (progressive enhancement; hover tooltips may require JS but are not essential).

### Layout

- Horizontal layout. One row per `WorkflowStep` in `step_number` order, top-down.
- Left column (fixed 220px width): step label in the format `S{NN} {step_label or agent}` (e.g., `S13 ruff lint`, `S02 CodeReview_Backend`). Clickable — anchors to the corresponding timeline entry below.
- Right column (flex): the time track, rendered as a single-row CSS grid whose total width maps to the item's wall-clock duration.

### Time mapping

- Item's total duration = `max(step_runs.completed_at) - min(step_runs.started_at)` across all runs of all steps of the item.
- Each `StepRun` bar's `left` offset = `(run.started_at - item_start) / total_duration * 100` percent.
- Each bar's `width` = `max((run.completed_at - run.started_at) / total_duration * 100, 0.5)` percent. Minimum 0.5% enforces a visible bar for sub-second runs.
- Runs with `completed_at IS NULL` (in-progress, cancelled, or killed) render with `width = (now - started_at) / total_duration * 100` and a striped pattern via `background-image: repeating-linear-gradient(...)`.

### Retry visualization (core requirement)

- A step with N `StepRun` rows renders N segments on its row, in `run_number` order.
- Segments for run 1..N-1 of a retried step use the **failed** palette (see below) regardless of their final DB status, because if a retry followed them they did not satisfy the gate.
- The final segment (run N) uses the status palette matching its actual `StepRun.status` (completed = green, failed = red).
- A thin connecting line between segments is rendered via CSS `::after` on each non-final segment to make the retry chain visually obvious.
- For a step like F-00055 S13 (lint, 3 runs), the row shows three red-ish bars followed by a final green bar — four segments total.

### Color palette (CSS classes)

| Class | Hex | Meaning |
|-------|-----|---------|
| `.gantt-bar--completed` | `#10b981` (emerald-500) | StepRun finished successfully on the final attempt |
| `.gantt-bar--failed` | `#ef4444` (red-500) | StepRun is the final attempt and failed (terminal failure) |
| `.gantt-bar--retry` | `#f59e0b` (amber-500) | Non-final StepRun of a retried step (triggered a fix cycle) |
| `.gantt-bar--skipped` | `#9ca3af` (gray-400) | Step skipped |
| `.gantt-bar--in-progress` | striped amber | `completed_at IS NULL` for an active run |
| `.gantt-row--qv-gate` | (row tint) | Rows for `agent="qv-gate"` steps get a light-slate background to distinguish QV from implementation |

### Fix cycles on the Gantt

- Fix cycles do NOT get their own row on the Gantt (they are step-internal).
- Between two retry segments of the same step, an amber `.gantt-fix-marker` thin bar is drawn inline indicating the fix cycle's own duration (`FixCycle.started_at → completed_at`). This shows how much wall-clock the fix agent consumed between two implementation attempts.

### Hover and tooltips

- Each bar has `title="..."` with: step ID, `run_number`, `status`, duration in seconds, first 120 chars of `error_message` if failed. `title` works without JS.
- A lightweight CSS-only tooltip (`:hover + popover`) is acceptable; a JS tooltip is not required.

### Axis and grid

- A horizontal time-axis header above the Gantt shows elapsed minutes ticks at 25%, 50%, 75%, 100% of total duration, labeled in `Xm Ys` format.
- Vertical grid lines at each tick render via CSS gradients on the row background.

### Responsive behavior

- Min width 720px. Below that, wrap step labels and show a compact mode where each row is 24px tall.
- Horizontal scrolling is permitted on very long items (20+ steps) but the default must fit the dashboard content area (1280px) without scrolling for a typical 18-step item.

### Accessibility

- Each bar is an `<a>` or `<button>` with `aria-label` matching the `title` content for screen readers.
- Color alone does not convey status — the bar's status is also text-labeled in the hover tooltip and icon-prefixed in the timeline below.

## File Manifest

All files for this work item live under `ai-dev/active/F-00056/`.

| File | Type | Purpose |
|------|------|---------|
| `F-00056_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `evidences/pre/F-00056-item-detail-before.png` | Evidence | Pre-implementation screenshot of F-00055's item detail page |
| `prompts/F-00056_S01_Database_prompt.md` | Prompt | S01 — schema + migration |
| `prompts/F-00056_S02_CodeReview_prompt.md` | Prompt | S02 — review S01 |
| `prompts/F-00056_S03_Backend_prompt.md` | Prompt | S03 — report service + CLI + daemon hook + fix-summary ingestion + template edits |
| `prompts/F-00056_S04_CodeReview_prompt.md` | Prompt | S04 — review S03 |
| `prompts/F-00056_S05_API_prompt.md` | Prompt | S05 — dashboard routes |
| `prompts/F-00056_S06_CodeReview_prompt.md` | Prompt | S06 — review S05 |
| `prompts/F-00056_S07_Frontend_prompt.md` | Prompt | S07 — fragment + standalone page + Gantt CSS + tab button |
| `prompts/F-00056_S08_CodeReview_prompt.md` | Prompt | S08 — review S07 |
| `prompts/F-00056_S09_Tests_prompt.md` | Prompt | S09 — unit + integration + backfill |
| `prompts/F-00056_S10_CodeReview_prompt.md` | Prompt | S10 — review S09 |
| `prompts/F-00056_S11_CodeReview_Final_prompt.md` | Prompt | S11 — global cross-agent review |
| `prompts/F-00056_S12_CodeReview_Fix_Final_prompt.md` | Prompt | S12 — fix CRITICAL/HIGH findings |
| `prompts/F-00056_S18_BrowserVerification_prompt.md` | Prompt | S18 — browser verification |

### Files to Create or Modify in Implementation

**Create**:
- `orch/db/migrations/versions/{next_rev}_add_fix_summary_to_fix_cycles.py`
- `orch/daemon/execution_report.py` — assembly service + markdown renderer
- `dashboard/templates/fragments/item_execution_report.html`
- `dashboard/templates/pages/project/item_execution_report.html`
- `tests/unit/test_execution_report_assembly.py`
- `tests/unit/test_execution_report_markdown.py`
- `tests/unit/test_execution_report_retry_hotspots.py`
- `tests/unit/test_execution_report_gantt_data.py`
- `tests/unit/test_item_report_cli.py`
- `tests/unit/test_fix_summary_ingestion.py`
- `tests/integration/test_execution_report_auto_generation.py`
- `tests/integration/test_execution_report_dashboard_route.py`

**Modify**:
- `orch/db/models.py` — add `FixCycle.fix_summary` mapped column
- `orch/daemon/batch_manager.py` — call report generator in `_complete_item()`
- `orch/daemon/fix_cycle.py` — parse fix agent's summary from its report and persist to `FixCycle.fix_summary`
- `orch/cli/item_commands.py` — new `item-report` command
- `orch/cli/main.py` — register the new command if the pattern requires explicit registration
- `dashboard/routers/items.py` — two new routes (tab fragment + standalone page)
- `dashboard/templates/pages/project/item_detail.html` — add one tab button
- `ai-dev/templates/CodeReview_FIX_Prompt_Template.md` — require `fix_summary` in result contract
- `ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md` — same
- `ai-dev/templates/QualityValidation_FIX_Prompt_Template.md` — same

## Acceptance Criteria

### AC1: Markdown report auto-generated on completion

```
Given a work item whose last step just transitioned to status "completed" in the daemon loop
When _complete_item() fires
Then a markdown file is written to ai-dev/active/<id>/<id>_execution_report.md (or archive dir if already archived)
And the file contains the four sections: header + verdict, retry hotspots, step timeline, fix-cycle details
And the verdict line reads "Verdict: ✓ Completed"
And the file is included in the subsequent .tar.zst archive
```

### AC2: Dashboard tab renders for F-00055 after backfill

```
Given F-00055 has been backfilled via `iw item-report F-00055`
When the user navigates to /project/iw-ai-core/item/F-00055 and clicks the "Execution Report" tab
Then the tab fragment loads via htmx with HTTP 200
And the summary card shows overall verdict "✓ Completed"
And the retry-hotspot list contains entries matching {S13 × 3, S10 × 2, S16 × 2} in retry-count-descending order
And the Gantt chart renders with one row per workflow step
And S13's row shows exactly four segments (three retry-colored + one completed)
```

### AC3: Fix summary captured going forward

```
Given a new work item created after F-00056 deploys
When any step triggers a fix cycle and the fix agent completes successfully
Then the fix agent's result payload contains a non-empty fix_summary field (1-3 bullets)
And the daemon's fix-cycle completion handler writes that value to FixCycle.fix_summary in the database
And a subsequent item-report for that item displays the summary as a block-quote under the corresponding retry timeline entry
```

### AC4: CLI regenerates on demand

```
Given any work item exists in the database (completed, failed, or in-progress)
When the user runs `iw item-report F-00055` (or `--project` if outside the default)
Then the markdown report is regenerated from the current DB state
And written to the item's active or archive directory under <id>_execution_report.md
And the command exits with code 0
And --stdout flag prints the markdown to stdout instead of writing to disk
```

### AC5: Graceful placeholder for missing summaries

```
Given a backfilled item has one or more FixCycle rows with fix_summary IS NULL (pre-F-00056 data)
When the report (markdown or dashboard) is rendered
Then each affected fix cycle displays "no fix summary captured (pre-F-00056)" in italics
And the Gantt chart and timeline still render fully from the existing StepRun / FixCycle rows
And no exceptions are raised
```

### AC6: Retry hotspots surface the right entries

```
Given an item has one or more steps with max(run_number) >= 2
When the summary card is rendered
Then each such step appears as a hotspot entry formatted "S{NN} `{step_label or agent}` × {max_run_number}"
And entries are sorted by max_run_number descending, then by step_number ascending
And steps with max(run_number) == 1 do NOT appear
And an item with zero hotspots renders "No retries — clean run."
```

### AC7: Gantt retry visualization matches the normative spec

```
Given a step with exactly three StepRun rows (run_number 1, 2, 3) where runs 1 and 2 triggered fix cycles and run 3 is status=completed
When the Gantt chart renders for the item
Then the step's row contains exactly three segments in run_number order
And the run 1 and run 2 segments carry the .gantt-bar--retry class
And the run 3 segment carries the .gantt-bar--completed class
And the title attribute on each segment contains the run_number and status
And the total width of the three segments does not exceed 100% of the row width
```

### AC8: No regressions to existing item-detail tabs

```
Given a user opens /project/iw-ai-core/item/F-00055 before and after F-00056 deploys
When they click each of the existing tabs (Overview, Design Doc, Reports, Artifacts, Evidences, Logs, Fix Cycles)
Then each tab loads with HTTP 200 and renders content identical in structure to the pre-F-00056 state
And no console errors are emitted
And the new "Execution Report" tab is the only visible change to the tab bar
```

### AC9: Backfill delivers reports for F-00055 + 2 priors

```
Given F-00056 has been deployed and the backfill step executes
When `iw item-report` is invoked for F-00055 and the two most recently completed items prior to F-00055
Then each of those three items has a <id>_execution_report.md file in its active or archive directory
And each corresponding dashboard /execution-report page renders with HTTP 200
And the three markdown files collectively document at least six retry events (F-00055 alone contributes three hotspots)
```

### AC10: Standalone page supports deep linking

```
Given F-00055 has been backfilled
When the user opens the direct URL /project/iw-ai-core/item/F-00055/execution-report in a new browser tab
Then the page loads with HTTP 200 wrapped in the base.html chrome
And the same summary card, Gantt, and timeline are visible as in the item-detail tab
And the URL is shareable (bookmarkable) without losing state
```

## Boundary Behavior

Define edge cases. **Every row becomes a mandatory test case.**

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Item with zero retries | every step has exactly one StepRun | Hotspot list reads "No retries — clean run."; Gantt renders one segment per row; no timeline entries |
| Item with `FixCycle.fix_summary` NULL for all cycles | Pre-F-00056 data or aborted fix agent | Placeholder "_no fix summary captured (pre-F-00056)_" renders under each affected timeline entry; layout unbroken |
| Item still in progress (no `completed_at`) | some StepRun has `completed_at IS NULL` | Gantt bar uses striped/in-progress style; width uses `now - started_at`; no auto-generation triggered; `iw item-report --stdout` still works |
| Item with zero StepRun rows | registered but never started | Report generates with empty timeline and hotspot list; verdict = "⏸ Not started"; no crashes |
| StepRun with `duration_secs IS NULL` | Completed run without recorded duration | Fallback: `completed_at - started_at`; if both missing, skip width calculation and render a 0.5% minimum bar |
| Step with `step_label IS NULL` | Older steps or manually registered items | Fall back to `agent_label`, then to `opencode_agent`, then to the literal step_id (e.g., `S13`) |
| Fix agent result missing `fix_summary` key | Agent ignored the new contract (cycle 1-2 of migration period) | Daemon writes NULL (not empty string) to `fix_cycles.fix_summary`; ingestion does not raise; UI shows the placeholder |
| Fix agent emits a multi-paragraph summary | Over-length output | Store up to 20000 chars verbatim (hard safety cap; well above the 2000-char guidance given to agents); UI clips at 10 lines with a "show more" expander; markdown file keeps the full stored text (identical to DB content) |
| Report regeneration while daemon is mid-write | `iw item-report` runs concurrently with `_complete_item` | Each writer uses a fresh `with open(...)` call; last writer wins; no locking required (idempotent render) |
| Dashboard route for non-existent item | `GET /project/xyz/item/NOPE/execution-report` | Return 404 with a short message; do not crash the template |
| Item archived to `.tar.zst` already | `ai-dev/archive/<id>/` exists | `iw item-report` writes to the active dir if it exists, else to the archive dir next to the tarball (alongside the existing uncompressed files, if any); does NOT attempt to mutate the tarball |
| `step_type = quality_validation` with `run_number == 1` | Failed QV gate on first try | Counted as a hotspot only if `max(run_number) >= 2`; single-run failures surface in the Gantt's terminal-red but not in the hotspot card |
| Long `error_message` in title tooltip | 5000-char stack trace | Truncate to first 120 chars in `title`, full text available in the timeline accordion |
| Item spans > 24 hours wall-clock | Long-running item with many retries | Gantt still renders at 100% width; axis ticks switch to `Xh Ym` format when total_duration > 3600 seconds |
| Project directory resolution fails | `design_doc_path` NULL and archive dir absent | `iw item-report` exits code 2 with a clear error "unable to locate target directory for <id>"; auto-generation logs a warning but does not fail the completion transition |

## Invariants

Conditions that must hold true after implementation. Each maps to a test.

1. Every `StepRun` row for an item appears as exactly one segment on exactly one Gantt row; no segment is duplicated or missing.
2. The sum of segment widths on any Gantt row does not exceed 100% of the row's time-track width (rounded to nearest integer percent); minimum per-segment width is 0.5%.
3. Retry-hotspot entries contain exactly the set of steps where `max(run_number) >= 2`; no false positives, no omissions.
4. `FixCycle.fix_summary` is NULL for every fix cycle completed before F-00056 deploys and MAY be non-NULL for every fix cycle completed after.
5. Markdown report file path equals `{active_or_archive_dir}/<id>_execution_report.md` with no alternative paths or filenames used anywhere in the codebase.
6. Dashboard route `/project/{pid}/item/{iid}/tab/execution-report` returns HTTP 200 for any existing item and HTTP 404 for any non-existent item; no 500s under any boundary condition listed in the Boundary Behavior table.
7. Existing item-detail tabs (Overview, Design Doc, Reports, Artifacts, Evidences, Logs, Fix Cycles) produce byte-for-byte-identical HTML before and after F-00056 deploys for the same DB state (verified by snapshot test).
8. `iw item-report --stdout` produces exactly the same markdown as is written to disk when `--stdout` is omitted; no branching logic diverges the two outputs.
9. Color classes in the Gantt are drawn from the exact 5-entry palette in this doc; no ad-hoc inline colors appear in the final rendered HTML.
10. The auto-generation hook in `_complete_item()` runs before the archive step, so the markdown file is included in the archive's `.tar.zst` payload for completed items.
11. The `FixCycle.fix_summary` column is nullable in the database; no migration or default value forces a non-NULL constraint in this feature.
12. Per-project isolation: the report assembly service never returns `StepRun` or `FixCycle` rows from a different `project_id` than the one queried. `WorkflowStep` and `StepRun` carry `project_id` directly (scoped by composite key `(project_id, work_item_id)`); `FixCycle` has no direct `project_id` column and is scoped transitively via `FixCycle.step_id → WorkflowStep.id` — the assembly query must JOIN `workflow_steps` and filter on `workflow_steps.project_id` to guarantee isolation.

## Dependencies

- **Depends on**: None. Uses only the `WorkflowStep`, `StepRun`, `FixCycle`, and `WorkItem` tables already in `orch/db/models.py` and infrastructure merged to `main`.
- **Blocks**: Future cross-item aggregation dashboard (out of scope); future "agents consume past-item reports" workflow (out of scope).

## TDD Approach

- **Unit tests** (`tests/unit/`):
  - `test_execution_report_assembly.py` — assembly service returns `ExecutionReportData` with correct ordering, retry counts, fix-cycle nesting; handles zero-retry items, NULL durations, NULL step_labels.
  - `test_execution_report_markdown.py` — renderer produces the four sections in order; placeholder line for NULL `fix_summary`; verdict logic for completed/failed/stalled/not-started.
  - `test_execution_report_retry_hotspots.py` — hotspot detection and sort order; empty set when max(run_number) == 1 for all steps; tie-breaking by step_number.
  - `test_execution_report_gantt_data.py` — segment generation per `StepRun`, class assignment (retry vs completed vs failed), minimum-width enforcement, total-percent invariant.
  - `test_item_report_cli.py` — `iw item-report` writes to the right path, `--stdout` prints the same content, exit codes for missing items and resolution failures.
  - `test_fix_summary_ingestion.py` — parses `fix_summary` field out of a fix agent's JSON report payload; stores NULL when missing; truncates at 2000 chars; never raises on malformed input.
- **Integration tests** (`tests/integration/`):
  - `test_execution_report_auto_generation.py` — seeds a PostgreSQL testcontainer with a work item containing F-00055-like retries; invokes the daemon `_complete_item()` hook; asserts markdown file written to the expected path, with the expected content signatures (hotspot list, verdict, four sections).
  - `test_execution_report_dashboard_route.py` — seeds the same item; starts the FastAPI test client; GETs both `/tab/execution-report` and `/execution-report`; asserts HTTP 200, template selectors present (summary card, Gantt row count, timeline accordion), and 404 for non-existent items.
- **Edge cases** (covered across unit + integration):
  - Zero-retry clean run.
  - All-NULL `fix_summary` (pre-F-00056 backfill).
  - In-progress item (no `completed_at`).
  - Multi-project isolation — two items in two projects with colliding IDs; each report returns only its own project's rows.
  - Fix agent result missing `fix_summary` key — ingestion writes NULL, no crash.
  - Existing tabs byte-identical before/after (snapshot test of all 7 existing fragments).

Test fixtures go in `tests/fixtures/` where reusable across tests; otherwise inline in the test. Do not mock the database in integration tests (see project CLAUDE.md). Unit tests that exercise only the renderer can use plain dataclasses without a DB session.

## Notes

### Why derived categorization over a new enum

Initial design considered a `failure_category` enum on `StepRun`. During review it became clear that `WorkflowStep` already carries `step_type` (enum), `step_label` (human string), and `opencode_agent` (slug). The tuple `(step_type, step_label, opencode_agent)` is a richer and already-populated signal than a hand-curated enum would be, and it survives workflow-template evolution. No new enum is added. Future cross-item aggregation (out of scope here) will group by `step_label`.

### Why pure-CSS Gantt over a JS library

The dashboard currently has zero client-side chart dependencies (verified during design; `batch_detail.html` uses pure CSS). Introducing d3 or chart.js for this single chart would pull in a large dependency and diverge from the project's zero-JS-chart convention. The normative Gantt spec above is fully expressible with CSS flex/grid + inline percentage widths and has been validated against a paper prototype of F-00055's retry shape.

### Why auto-generate before archive

Running the report generator synchronously inside `_complete_item()` (before the archive step) ensures the markdown file is captured in the `.tar.zst` payload, so the full execution story travels with the archive. Running it after archive would require a second archive pass or a sidecar file.

### Fix-summary rollout

For the first 1-2 items after deploy, fix agents may not yet reliably emit `fix_summary` (prompt templates change but agent adherence varies). The ingestion path tolerates missing/empty summaries (writes NULL, no crash) and the UI placeholder handles NULL gracefully, so the rollout is graceful.

### Risks

- **Gantt clutter on items with many QV gates** — an 18-step item with 10 QV gates can produce 18 rows. Mitigation: the `.gantt-row--qv-gate` tint visually groups QV rows; compact mode kicks in below 720px. Cross-item aggregation (future) will be the primary surface for pattern analysis across items.
- **Fix agent prompt drift** — the three fix prompt templates now require `fix_summary` in the result payload; if the orchestrator's JSON-parsing path is strict about unknown keys, earlier-style agent reports could fail parsing. Mitigation: the ingestion is defensive (treats missing key as NULL, catches JSON errors).
- **Performance of report assembly** — for items with 100+ step runs the assembly is a few SQL queries; well within request-response budget. No caching layer is introduced in v1.

### Browser evidence

- **Pre-implementation screenshot**: captured at `ai-dev/active/F-00056/evidences/pre/F-00056-item-detail-before.png` showing the F-00055 item-detail page before the new "Execution Report" tab exists.
- **Post-implementation screenshots**: captured by S18 (qv-browser) in `ai-dev/active/F-00056/evidences/post/` covering: summary card, Gantt chart with S13 retry segments visible, timeline accordion expanded on S13, standalone deep-link page, and no-regressions check on existing tabs.
