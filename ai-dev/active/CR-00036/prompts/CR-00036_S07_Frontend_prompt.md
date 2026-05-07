# CR-00036_S07_Frontend_prompt

**Work Item**: CR-00036 -- Batch-level auto_merge toggle with operator-approved manual merge
**Step**: S07
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00036/CR-00036_CR_Design.md`
- `ai-dev/work/CR-00036/reports/CR-00036_S05_API_report.md` and `CR-00036_S06_CodeReview_report.md` (for the exact endpoint URLs).
- `dashboard/templates/components/action_button.html` — existing macros (`restart_merge_button`, `abandon_merge_button`).
- `dashboard/templates/fragments/item_overview.html:90-115` — existing MERGE row branching.
- `dashboard/templates/pages/project/batch_detail.html:50-67` — existing max-parallel control on Plan tab.
- `dashboard/templates/fragments/batch_detail_header.html` — header summary line.
- The "create batch from selection" form — locate via `grep -rn "auto_publish\|max_parallel.*5" dashboard/templates/`.
- `dashboard/static/styles.css` — append plain CSS rules here when needed (per `CLAUDE.md` workaround for I-00067).
- Pre-state evidence screenshots: `ai-dev/active/CR-00036/evidences/pre/`.

## Output Files

- `ai-dev/work/CR-00036/reports/CR-00036_S07_Frontend_report.md`

## Context

You are implementing the dashboard UI for CR-00036. All backend and API plumbing exists. Your job is the templates, macros, and any CSS adjustments.

Read the design doc, especially "Desired Behavior" (2, 3, 5) and AC3, AC4, AC5 (UI part), AC11.

## Requirements

### 1. `approve_merge_button` macro

In `dashboard/templates/components/action_button.html`, add a new macro after `restart_merge_button`:

```jinja
{% macro approve_merge_button(project_id, item_id) %}
  <button
    type="button"
    hx-post="/actions/item/{{ item_id }}/approve-merge"
    hx-target="..."
    hx-swap="..."
    class="..."
    title="Approve and trigger the squash-merge to main">
    Merge
  </button>
{% endmacro %}
```

Match the style/classes/htmx wiring of `restart_merge_button` exactly — same target, same swap, same toast pattern. Use the visible word **Merge** (not "Approve Merge") so the operator sees a clean call to action.

Pick a button style that signals primary action (positive intent) — green/success colour like `bg-success` if such a class exists, otherwise reuse `bg-primary`. Confirm by reading sibling macros.

### 2. Render the button on the MERGE row

In `dashboard/templates/fragments/item_overview.html` (around line 90-97), extend the MERGE branching:

```jinja
{% if step.step_id == 'MERGE' and step.status == 'awaiting_approval' %}
  <div class="flex items-center justify-end gap-1">
    {{ approve_merge_button(item.project_id, item.id) }}
  </div>
{% elif step.step_id == 'MERGE' and step.status in ('failed', 'merge_failed') %}
  ...existing...
{% endif %}
```

Place the new branch **before** the existing failed/merge_failed branch.

Import the new macro at the top of the file (it currently imports `restart_merge_button` etc.). Add `approve_merge_button` to the import list.

### 3. Status badge for `awaiting_approval`

Look at `dashboard/templates/components/status_badge.html` and find how it renders various step statuses. Add support for the `awaiting_approval` value:

- A neutral/info-coloured badge with the label "Awaiting approval" (or similar — match the verbosity of sibling labels).
- Title attribute: "Item finished its workflow steps and is waiting for an operator to approve the merge."

If the badge component uses CSS classes that the Tailwind build doesn't pick up, append the necessary plain CSS rules to `dashboard/static/styles.css` (per the CLAUDE.md I-00067 workaround) and verify rendering by inspecting the file diff.

### 4. Plan tab `auto-merge` toggle

In `dashboard/templates/pages/project/batch_detail.html`, after the max-parallel control block (currently around line 53-67), add a sibling control for `auto-merge`:

```jinja
<div class="flex items-center gap-3">
  <label for="auto-merge-toggle" class="text-sm text-muted-foreground">Auto-merge:</label>
  <input id="auto-merge-toggle"
         type="checkbox"
         name="auto_merge"
         {% if batch.auto_merge %}checked{% endif %}
         hx-post="/project/{{ current_project.id }}/api/batch/{{ batch.id }}/auto-merge"
         hx-trigger="change"
         hx-swap="none"
         hx-on::after-request="htmx.trigger('#batch-header-sse-trigger', 'batch-header-refresh')"
         {% if batch_status not in ('planning', 'approved', 'paused') %}disabled{% endif %}
         class="..." />
  <span class="text-xs text-muted-foreground">When off, each item waits for an operator to approve the merge.</span>
</div>
```

Match the disable rule to the max-parallel select exactly.

### 5. Batch header summary

In `dashboard/templates/fragments/batch_detail_header.html`, add an Auto-merge line near the existing `Max parallel: {{ batch.max_parallel }}`:

```jinja
<span class="text-xs text-muted-foreground">Auto-merge: {{ 'yes' if batch.auto_merge else 'no' }}</span>
```

Place it next to `Max parallel` so the two settings sit together visually.

### 6. Create-batch-from-selection toggle

Locate the "create batch from selection" form (search the dashboard templates for the route URL of the create-batch-from-selection endpoint, or for `max_parallel` form fields). Add a toggle:

```jinja
<label class="flex items-center gap-2 text-sm">
  <input type="checkbox"
         name="auto_merge"
         {% if project_auto_merge_default %}checked{% endif %} />
  Auto-merge each item when it succeeds
</label>
```

The pre-fill value MUST come from the current project's `auto_merge_default`. If the route doesn't currently expose that to the template, S05 should have added it; if not, raise a blocker (do NOT hardcode `True`).

### 7. CSS

Run `make css` to regenerate Tailwind. If the build reports "Nothing to be done" or fails (per the I-00067 workaround note in `CLAUDE.md`), append the plain CSS rules directly to `dashboard/static/styles.css`.

### 8. Visual verification (pre-flight)

After implementation, manually open the dashboard and verify:

```bash
playwright-cli kill-all
playwright-cli open http://localhost:9900/project/iw-ai-core/batches
playwright-cli screenshot
# Confirm rendering matches expectations.
```

This is a sanity check, not the formal qv-browser step (S17 covers that). It exists to catch obvious template/macro mistakes before the per-agent review.

## Project Conventions

Read `dashboard/CLAUDE.md`:

- Tailwind is **prebuilt**; avoid dynamic class construction that breaks JIT purging. When new utility classes appear in a freshly added template, run `make css`.
- htmx fragment templates MUST NOT extend `base.html`.
- For htmx forms, use `hx-on::after-request` to trigger SSE refreshes.

## TDD Requirement

Frontend tests go in `tests/dashboard/`:

- `test_item_overview_awaiting_merge.py` — render the item overview with a BatchItem in `awaiting_merge_approval` and assert the HTML contains the Merge button and does NOT contain Restart Merge / Abandon Merge.
- `test_batch_detail_auto_merge_toggle.py` — render the Plan tab and assert the toggle is enabled (and pre-checked according to batch.auto_merge) when batch is in `planning|approved|paused`, disabled otherwise.

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`

Lint includes `make lint-js` which `node --check`s every dashboard JS file — keep it clean.

## Test Verification

`make test-unit`, `make test-integration`, and `make test-dashboard` MUST pass.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "frontend-impl",
  "work_item": "CR-00036",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
