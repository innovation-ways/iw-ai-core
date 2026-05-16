# I-00086_S03_Frontend_prompt

**Work Item**: I-00086 -- Runtime override controls give no UI feedback
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy. Allowed exceptions: testcontainer fixtures, read-only `docker ps`/`docker inspect`/`docker logs`, `./ai-core.sh` and `make` targets.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this step.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00086 --json`.
- `ai-dev/active/I-00086/I-00086_Issue_Design.md` — design document (READ FIRST)
- `ai-dev/active/I-00086/reports/I-00086_S01_API_report.md` — S01 step report (read the `notes` field — it tells you which render approach S01 used and whether `fragments/item_steps_table.html` already exists as a stub).
- `dashboard/templates/fragments/item_overview.html` — file you will MODIFY
- `dashboard/templates/pages/project/item_detail.html` — toast hook lives here at line 158-167; verify it still wraps the overview correctly (READ-ONLY).
- `dashboard/templates/components/toast.html` — toast component (READ-ONLY; do not touch).
- `dashboard/routers/runtime_overrides.py` — already modified by S01; read to understand what fragment it renders.
- `dashboard/routers/items.py` — context around line 1237 for understanding render variables passed to `item_overview.html`.

## Output Files

- `ai-dev/active/I-00086/reports/I-00086_S03_Frontend_report.md` — Step report

## Context

You are fixing the **frontend** half of incident **I-00086**. S01 already changed the API endpoints to return an HTML fragment (`fragments/item_steps_table.html`) + an `HX-Trigger.showToast` header. Your job is to:

1. Create the `fragments/item_steps_table.html` template that the API renders.
2. Update `fragments/item_overview.html` to `{% include %}` the new sub-fragment.
3. Wire the per-step `<select>` and the bulk Apply button to swap the steps-table fragment in place.

Read the design document `ai-dev/active/I-00086/I-00086_Issue_Design.md` first — especially **Acceptance Criteria** and the **Notes** section (the `hx-disabled-elt="this"` constraint is critical).

## Requirements

### 1. Extract `dashboard/templates/fragments/item_steps_table.html`

If S01 left a stub there with a placeholder include, **replace** it. The new file must:

- NOT extend `base.html` (per `dashboard/CLAUDE.md`).
- Contain the steps `<table>` block AND the bulk "Apply to remaining steps:" footer that currently live in `fragments/item_overview.html` lines 50-199 (approx — the exact line range will shift; use the surrounding markers as anchors).
- Wrap the table in a `<div id="item-steps-table">` (or set the id on the table itself — pick one and be consistent).
- Receive the same template context as `item_overview.html` (`item`, `steps`, `runtime_options`, and any locals like `run_count`). Do NOT add new context variables; everything you need is already supplied by S01's render helper.
- Preserve EVERY existing column, every per-row badge, every macro call (`status_badge`, `approve_merge_button`, `restart_button`, `restart_merge_button`, `skip_button`, `kill_button`, `abandon_merge_button`, `restart_setup_button`), every conditional branch, AND the lazy-loaded `<div id="step-runs-{{ step.step_id }}" class="step-runs-container">` container.

### 2. Update `dashboard/templates/fragments/item_overview.html`

- Replace the extracted block with `{% include "fragments/item_steps_table.html" %}`.
- Leave EVERY other section untouched: the header, the cascade history include (`{% include "fragments/cascade_history.html" %}`), the Impacted Paths block, etc.
- Keep the surrounding `<div>` wrapper that the include lives inside.

### 3. Wire the per-step `<select>` (CRITICAL — preserve `hx-disabled-elt`)

The select currently looks like (from `item_overview.html:83-93`):

```html
<select
  class="text-xs ..."
  hx-patch="/project/{{ item.project_id }}/api/item/{{ item.id }}/step/{{ step.step_id }}/runtime-override"
  hx-swap="none"
  hx-disabled-elt="this"
  name="option_id">
  ...
</select>
```

Change to:

```html
<select
  class="text-xs ..."
  hx-patch="/project/{{ item.project_id }}/api/item/{{ item.id }}/step/{{ step.step_id }}/runtime-override"
  hx-target="#item-steps-table"
  hx-swap="outerHTML"
  hx-disabled-elt="this"
  name="option_id">
  ...
</select>
```

**Critical**: do NOT add an `onchange="this.disabled=true"` handler or remove `hx-disabled-elt="this"`. The inline comment at lines 78-82 of the current file explains why (htmx omits disabled controls from the request body, which drops `option_id` and clears the override instead of setting it). Keep the comment, or move it to the new sub-fragment.

### 4. Wire the bulk Apply button

Current (from `item_overview.html:192-198`):

```html
<button
  class="text-xs ..."
  hx-patch="/project/{{ item.project_id }}/api/item/{{ item.id }}/runtime-override/bulk"
  hx-vals="javascript:{option_id: document.getElementById('bulk-runtime-option').value}"
  hx-swap="none">
  Apply
</button>
```

Change to:

```html
<button
  class="text-xs ..."
  hx-patch="/project/{{ item.project_id }}/api/item/{{ item.id }}/runtime-override/bulk"
  hx-vals="javascript:{option_id: document.getElementById('bulk-runtime-option').value}"
  hx-target="#item-steps-table"
  hx-swap="outerHTML">
  Apply
</button>
```

### 5. Preserve `id="bulk-runtime-option"` inside the swapped fragment

The bulk button's `hx-vals` reads `document.getElementById('bulk-runtime-option').value`. After the swap, that element ID must still resolve — so the `<select id="bulk-runtime-option">` MUST live INSIDE `fragments/item_steps_table.html` (which is the swapped HTML), NOT outside.

If you put the bulk selector outside the swapped region, the bulk control will keep working only by luck; if it's inside (as it is today), keep it that way.

### 6. CSS

You almost certainly do NOT need to touch `dashboard/static/styles.css`. The visual layout doesn't change; only htmx attributes do. If you discover a missing utility class:

- First try the existing Tailwind classes you can already see used in this template.
- Only as a last resort, append a plain CSS rule directly to `dashboard/static/styles.css` per `CLAUDE.md`'s I-00067 mitigation rule. Do NOT run `make css`.

### 7. Do NOT modify

- `dashboard/routers/*.py` — S01 owns router changes.
- `dashboard/templates/pages/project/item_detail.html` — toast hook is already correct.
- `dashboard/templates/components/toast.html` — already supports the JSON shape we emit.
- Anything outside `dashboard/templates/fragments/`.

## Project Conventions

Read `dashboard/CLAUDE.md`:

- Fragment templates MUST NOT extend `base.html`.
- htmx targets resource-scoped APIs (`/api/...`); we already follow that.
- Tailwind is prebuilt — do NOT introduce new utility classes that may not be in the JIT-purged output.
- Clipboard helper rule (irrelevant here — we don't add clipboard buttons).

## TDD Requirement

Frontend template changes are verified by:

1. S05's dashboard tests asserting the rendered HTML contains `id="item-steps-table"`.
2. S14's qv-browser run hitting the live page.

For your own RED evidence: load the page locally before your change (via `curl` against the dashboard) and confirm `id="item-steps-table"` is NOT present; load it again after the change and confirm it IS present. Capture both in `tdd_red_evidence`. The TDD-RED requirement for behaviour-implementing steps is satisfied by this template-level proof.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format
make typecheck   # no python files touched, but run anyway to catch knock-on
make lint        # runs scripts/check_templates.py — catches Jinja2 format-filter pitfalls
```

If `make lint` reports a `str.format`-style `.format()` call in your new template, fix it: use `%`-style format filter (`"%dm%02ds"|format(m, s)`), never `"{}m{}s"|format(m, s)`. This rule is enforced project-wide per `CLAUDE.md`.

## Test Verification (NON-NEGOTIABLE)

Run only the dashboard tests for the affected templates:

```bash
uv run pytest tests/dashboard/ -k "item_overview or runtime_override" -v
```

Do NOT run `make test-integration` or `make test-unit`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "I-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/item_overview.html",
    "dashboard/templates/fragments/item_steps_table.html"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — template-only extraction. RED verified via curl before/after: pre-change response does NOT contain 'id=\"item-steps-table\"'; post-change response contains it.",
  "blockers": [],
  "notes": ""
}
```
