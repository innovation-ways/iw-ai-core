# F-00081_S05_Frontend_prompt

**Work Item**: F-00081 -- Per-Item / Per-Step Agent + Model Override
**Step**: S05
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers in pytest are exempt.

## ⛔ Migrations: agents generate, daemon applies

Not your concern. Frontend only.

## Input Files

- `uv run iw item-status F-00081 --json`.
- `ai-dev/active/F-00081/F-00081_Feature_Design.md` (especially Frontend Changes, AC4, AC8).
- `ai-dev/active/F-00081/evidences/pre/F-00081-batch-items-before.png` and `F-00081-item-detail-before.png` — current UI for reference.
- `ai-dev/active/F-00081/reports/F-00081_S04_API_report.md` — exact endpoint URLs and form-field names you must call.
- Existing files you will modify:
  - `dashboard/templates/components/step_pipeline.html` — current strip macro (32px circles).
  - `dashboard/templates/fragments/batch_items_rows.html` — current items-tab row template.
  - `dashboard/templates/fragments/item_overview.html` — current item-detail steps table.
  - `dashboard/static/styles.css` — append CSS rules here per the I-00067 mitigation.
- Read for patterns:
  - `dashboard/templates/components/status_badge.html` — badge component shape.
  - `dashboard/templates/components/multi_select.html` — existing dropdown pattern (if any).
  - `dashboard/CLAUDE.md` — htmx + Tailwind + clipboard helper rules.

## Output Files

- `ai-dev/active/F-00081/reports/F-00081_S05_Frontend_report.md`.
- Edits to the three templates listed above and `dashboard/static/styles.css`.
- Possibly a small new component template (e.g. `components/runtime_dropdown.html`) if it improves reuse between the batch-items and item-detail views.

## Context

You are building the UI surface of F-00081. Two areas:
1. **Batch items tab** (`/project/<p>/batch/<b>?tab=items`) — compress the per-step strip and add CLI / Model columns at the item level.
2. **Item detail** (`/project/<p>/item/<id>`) — add per-step CLI / Model dropdowns, locked when the step is no longer editable.

Read AC8 carefully — the strip must respect a width budget for any reasonable step count. AC4 dictates the lock semantics (only `pending | failed | paused` are editable). Read the user's stated motivation in the design's Description: the existing strip is too wide and a single circle would lose information — your replacement must keep the per-step status visible while shrinking horizontally.

## Requirements

### 1. Compressed step strip — `components/step_pipeline.html`

Replace the 32px circles + 16px connectors with a horizontal sequence of slim segments:

- Each segment: ~6px wide × ~14px tall.
- Color mapping unchanged (success / in-progress with pulse / failed / skipped / pending).
- Tooltip preserved on each segment (`title="..."` covers `step_id agent_label: status: duration`).
- Connector lines removed — segments are adjacent (with ~1px gap). Total strip width ≤ 120px for an item with ≤ 12 steps.
- Container element exposes a `data-step-count` attribute for the no-regressions test.

The CSS (in `dashboard/static/styles.css`):

```css
.iw-step-strip { display: flex; gap: 1px; align-items: center; }
.iw-step-seg   { width: 6px; height: 14px; border-radius: 1px; }
.iw-step-seg--completed   { background: var(--success); }
.iw-step-seg--in-progress { background: var(--primary); animation: pulse 1.4s ease-in-out infinite; }
.iw-step-seg--failed      { background: var(--destructive); }
.iw-step-seg--skipped     { background: var(--muted); }
.iw-step-seg--pending     { background: var(--secondary); }
@keyframes pulse { 0%,100% {opacity:1} 50% {opacity:.55} }
```

(Match the exact CSS-variable names already used in `styles.css`.)

### 2. Batch items tab columns — `fragments/batch_items_rows.html`

Add two new `<td>` columns after the title cell: **CLI** and **Model**.

- Source from the item's `agent_runtime_option_id`. If NULL, render `(default)` in muted text. If non-NULL, render `cli_label` and `model_label` as small badges.
- If any step under the item has its own override, render a small dot (`●`) after the badge with a `title` listing the step IDs that override it. Pass this from the router/view layer (cheap aggregate query: `SELECT bool_or(agent_runtime_option_id IS NOT NULL) FROM workflow_steps WHERE …` plus a separate query for the step-id list, or compute server-side once per item).
- The CLI column header is a `<select>` lookalike — clicking opens an inline dropdown (htmx `hx-get` to a fragment that renders the dropdown options, then htmx `hx-patch` to the API on `change`). Use `dashboard/static/clipboard.js`-style scoped JS sparingly; prefer pure-htmx.

If the existing items-tab row is too crowded, drop the `execution_group` column and surface its value as a tooltip on the item ID. Discuss the trade-off in your report.

### 3. Item detail — `fragments/item_overview.html`

Add **CLI** and **Model** columns after the existing **Agent** column:

- For steps in `pending | failed | paused`: render `<select>` with options sourced via Jinja from the catalogue (pre-rendered server-side; the catalogue is small). On `change`, fire htmx `hx-patch="/project/{p}/api/item/{iid}/step/{sid}/runtime-override"` with `option_id` form param. The response is a fragment that swaps the row.
- For other statuses: render the read-only badge sourced from `step_runs.agent_runtime_option_id` (the most recent run). If no run yet (e.g., skipped step), render `(default)`.
- Add an "Apply to all remaining" button at the table footer — htmx PATCH to the bulk endpoint with the currently selected option (use a small inline form with a hidden `option_id` input populated from a row-level dropdown the user just changed; or, simpler, present an explicit dropdown next to the button). Choose the cleanest interaction and document it in your report.

### 4. Tooling fallback (I-00067)

If `make css` reports "Nothing to be done" or fails (Tailwind toolchain), append plain CSS to `dashboard/static/styles.css` directly. Do not modify Tailwind config.

### 5. Tests

Add dashboard TestClient tests at `tests/dashboard/test_runtime_override_templates.py`:

- Render the batch items tab for a batch with one item that has 8 steps; assert the strip element has 8 segments and width ≤ 120px (you can assert via class names + count rather than computed CSS).
- Render the item detail page for an item with mixed step statuses; assert `<select>` is present only on rows with editable status.
- Assert the "(default)" placeholder renders when the item has no override.

## Project Conventions

Read `dashboard/CLAUDE.md`:

- Tailwind classes are JIT-purged; avoid dynamically constructed class names.
- Plain CSS in `styles.css` is served as-is — safe path for these segment classes.
- Fragment templates do NOT extend `base.html`.
- Use `window.iwClipboard.copy(...)` if you ever need clipboard, NEVER `navigator.clipboard.writeText(...)` directly — but this feature should not need clipboard.

## TDD Requirement

Tests first for the rendering assertions (you can write them against the fragment templates with the TestClient calling the route that includes them).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format` → `make typecheck` → `make lint`. Note `make lint` runs `node --check` on `dashboard/static/**/*.js`, so any new JS file must parse.

## Test Verification (NON-NEGOTIABLE)

`make test-frontend` (= `make test-dashboard`).

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "F-00081",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/components/step_pipeline.html",
    "dashboard/templates/fragments/batch_items_rows.html",
    "dashboard/templates/fragments/item_overview.html",
    "dashboard/static/styles.css",
    "tests/dashboard/test_runtime_override_templates.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": "Document the chosen 'Apply to all remaining' interaction here."
}
```
