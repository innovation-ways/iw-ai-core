# F-00056_S07_Frontend_prompt

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Step**: S07
**Agent**: frontend-impl

---

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- Design document. **READ the entire "Gantt Chart Strategy" section** — it is normative; every rule there must be implemented exactly.
- `ai-dev/active/F-00056/reports/F-00056_S06_CodeReview_report.md` -- S06 verdict
- `dashboard/templates/pages/project/item_detail.html` -- tab bar (add one button)
- `dashboard/templates/pages/project/batch_detail.html` -- pure-CSS timeline precedent (read and mirror its CSS approach)
- `dashboard/templates/fragments/item_fix_cycles.html` -- reference fragment pattern
- `dashboard/templates/fragments/item_reports.html` -- reference fragment pattern
- `dashboard/templates/layouts/base.html` -- base layout used by standalone pages
- `orch/daemon/execution_report.py` -- `ExecutionReportData` and nested dataclasses (the template context shape)
- `dashboard/CLAUDE.md` -- dashboard conventions

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S07_Frontend_report.md` -- Step report

## Context

You are building the Execution Report UI: a tab fragment, a standalone page, and a pure-CSS Gantt chart. The backend (`assemble_execution_report`) is already done and passes a fully-shaped `ExecutionReportData` to your templates. Your job is presentation only — no business logic belongs in templates. The Gantt spec in the design doc is normative; deviations require re-opening the design.

## Requirements

### 1. Fragment template: `dashboard/templates/fragments/item_execution_report.html`

Sections in order:

1. **Summary card** — a bordered card at the top with:
   - Verdict badge (emoji + word) using `data.verdict_badge`.
   - `Started`, `Completed` (or "—"), `Total duration` (human format like "2h 14m 08s").
   - **Retry hotspots** block: if `data.hotspots` is empty, render "No retries — clean run." Otherwise render a bullet list `<ul>`; each `<li>` shows `<strong>S{NN}</strong> <code>{display_label}</code> × {retry_count} <span class="muted">(final: {final_status})</span>`. Sort order comes pre-computed from the backend — do not re-sort in the template.

2. **Gantt chart** — per the normative spec. Implementation outline:
   - Time-axis header row with 4 ticks at 25/50/75/100% showing `Xm Ys` (if `total_duration_secs <= 3600`) or `Xh Ym` (if `> 3600`).
   - One row per `StepRow` in `data.steps` in `step_number` order.
   - Each row has a fixed 220px left column (step label as `<a href="#timeline-{step_id}">S{NN} {display_label}</a>`) and a flex-1 right column (the time track).
   - Inside the time track, render one `<div class="gantt-bar gantt-bar--{gantt_class}">` per `StepRunSegment` with inline `style="left: {segment.left_pct}%; width: {segment.width_pct}%;"` and `title="S{NN} run {run_number}: {status}, {duration_secs}s{error_snippet}"`. `left_pct` and `width_pct` are precomputed by the backend (`orch/daemon/execution_report.py`, `StepRunSegment`); the template does NO arithmetic — emit the numbers verbatim with a `|round(2)` filter for safety. Minimum-width / per-row-sum invariants are enforced by the backend; templates are presentation-only.
   - Between two retry segments of the same step, emit a `<div class="gantt-fix-marker">` per `FixCycleEntry` with inline `style="left: {fix_cycle.left_pct}%; width: {fix_cycle.width_pct}%;"` (also precomputed by the backend).
   - QV-gate rows get the `gantt-row--qv-gate` class (detect by `step_row.step_type == "quality_validation"` or by `agent == "qv-gate"` — check which signal the backend provides; `step_type.value` should work).
   - All bars are wrapped in `<button>` or `<a>` with `aria-label` matching the `title` for a11y (Invariant: a11y).

3. **Retry timeline** — a `<details>/<summary>` accordion list, one `<details>` per `StepRow` where `is_hotspot` is True. Inside each:
   - Summary: `S{NN} {display_label} — {retry_count} attempts, final: {final_status}`.
   - Body: a chronological list, one entry per `StepRunSegment` in `run_number` order showing timestamp, duration, `error_message` (if any), and a link to `report_file` if present. Below the runs, iterate `fix_cycles`; for each `FixCycleEntry` render the cycle metadata and the `fix_summary` as a `<blockquote>`. If `fix_summary` is empty/None, render `<blockquote><em>no fix summary captured (pre-F-00056)</em></blockquote>`.
   - Each `<details>` has `id="timeline-{step_id}"` so Gantt-row anchors scroll to the right entry.

### 2. Inline CSS or scoped stylesheet

Put the Gantt styles in a `<style>` block at the top of the fragment OR in a new file `dashboard/static/execution_report.css` — choose whichever matches the convention used by `item_fix_cycles.html` and siblings. If siblings use inline `<style>`, do inline; if they use external CSS via `<link>`, do external. Do not mix.

Palette (from the design doc — normative):

- `.gantt-bar--completed { background: #10b981; }`
- `.gantt-bar--failed { background: #ef4444; }`
- `.gantt-bar--retry { background: #f59e0b; }`
- `.gantt-bar--skipped { background: #9ca3af; }`
- `.gantt-bar--in-progress { background: repeating-linear-gradient(45deg, #f59e0b, #f59e0b 6px, #d97706 6px, #d97706 12px); }`
- `.gantt-row--qv-gate { background: rgb(248 250 252 / 0.6); }` (light slate tint)
- `.gantt-fix-marker { background: #fbbf24; height: 4px; border-radius: 2px; }`

Layout rules:

- Use CSS Grid or Flexbox. No tables.
- Rows are 28px tall by default, 24px in compact mode (≤720px).
- Bars are 18px tall, centered vertically in the row.
- Horizontal grid lines at each 25% tick, drawn via `background-image: linear-gradient(...)`.
- Responsive breakpoint at 720px; below that, the label column wraps but the time track remains in the viewport.

### 3. Standalone page: `dashboard/templates/pages/project/item_execution_report.html`

A thin wrapper over the fragment:

```jinja
{% extends "layouts/base.html" %}
{% block title %}Execution Report — {{ data.work_item_id }}{% endblock %}
{% block content %}
  <h1>{{ data.work_item_id }} — {{ data.work_item_title }}</h1>
  {% include "fragments/item_execution_report.html" %}
{% endblock %}
```

Exact block names must match the existing `base.html`; inspect that file first to get them right.

### 4. Tab button in `dashboard/templates/pages/project/item_detail.html`

Find the existing tab-button block. Add one new button immediately after the last existing tab (Fix Cycles), matching the exact HTML/attribute style of the other tabs:

```jinja
<button hx-get="/project/{{ project_id }}/item/{{ work_item_id }}/tab/execution-report"
        hx-target="#tab-content" hx-swap="innerHTML">
  Execution Report
</button>
```

Copy the surrounding `class=` attributes from sibling tabs exactly — do not invent a new class. Invariant 7 requires existing tabs to produce byte-for-byte-identical HTML before/after this feature; therefore do not reorder, reindent, or otherwise touch any other tab button.

### 5. No JS

This feature introduces no JavaScript. Hover tooltips use native `title=`. The `<details>/<summary>` accordion is native HTML. If a sibling fragment requires an htmx `hx-trigger` or similar, match it; otherwise, emit static HTML.

## Project Conventions

Read `dashboard/CLAUDE.md` for:

- Jinja2 patterns used (autoescape, safe filters, include vs import)
- CSS conventions (Tailwind utility classes vs custom CSS)
- htmx patterns for fragment loading

Match existing fragments rigorously. If the existing fragments use Tailwind utility classes, use Tailwind for layout and keep the status-color custom classes as a small island.

## TDD Requirement

Frontend changes are verified by:

1. S09 integration test against the rendered route (HTML structure assertions).
2. S18 browser verification (visual and interaction checks).

For this step you must manually verify by starting the dashboard and opening F-00055 post-S09-backfill — but because S09 runs after S07, just ensure the template syntax is valid (no Jinja parse errors) and the HTML structure matches the assertions you expect S09 to make.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration`
3. `uv run ruff check .`
4. `uv run mypy orch/ dashboard/`
5. Manually start the dashboard (`make dashboard-start`) and confirm that `/project/iw-ai-core/item/F-00055` loads without template syntax errors (the new tab will 404 until the route is hit — that's fine; the page itself must not error).

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "frontend-impl",
  "work_item": "F-00056",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/item_execution_report.html",
    "dashboard/templates/pages/project/item_execution_report.html",
    "dashboard/templates/pages/project/item_detail.html",
    "dashboard/static/execution_report.css"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "note whether CSS went inline or external, and which sibling fragment's style was mirrored"
}
```
