# CR-00028_S05_Frontend_prompt

**Work Item**: CR-00028 -- Don't cascade merge-time failures to dependent items
**Step**: S05
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute Docker mutating commands. Allowed: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00028 --json`
- `ai-dev/active/CR-00028/CR-00028_CR_Design.md` — design
- `ai-dev/active/CR-00028/reports/CR-00028_S03_Backend_report.md` — backend implementation
- `ai-dev/active/CR-00028/reports/CR-00028_S04_CodeReview_Backend_report.md` — backend review

## Output Files

- `dashboard/templates/components/status_badge.html` — add `merge_failed` color mapping
- `dashboard/templates/components/action_button.html` — add `abandon_merge_button` macro; possibly extend `restart_merge_button`
- `dashboard/templates/fragments/item_overview.html` — extend the synthetic-MERGE-step button condition to cover the new recoverable statuses
- `dashboard/routers/items.py` — extend `_merge_status()` to map `merge_failed` / `migration_invalid` / `migration_rebase_failed` to a recognized display status
- `dashboard/static/styles.css` — regenerated via `make css` IF you add new Tailwind classes
- `ai-dev/active/CR-00028/reports/CR-00028_S05_Frontend_report.md` — step report

## Context

You are implementing the dashboard UI for **CR-00028**. Read the design doc first. Read `CLAUDE.md` and `dashboard/CLAUDE.md` — the dashboard is FastAPI + Jinja2 + htmx + prebuilt Tailwind CSS.

Three operator-recoverable BatchItem statuses now need:
1. A distinct visual badge (different from generic `failed`)
2. Two action buttons per row: "Retry merge" (calls existing `restart-merge`) and "Abandon" (calls new `abandon-merge` endpoint added in S03)

The statuses are: `merge_failed` (NEW), `migration_invalid` (existing), `migration_rebase_failed` (existing).

## Requirements

### 1. Add `merge_failed` to the status-badge macro

Edit `dashboard/templates/components/status_badge.html`. The existing macro is a flat dict mapping `status` → Tailwind classes. Add an entry that is **visually distinct from `failed`**:

```jinja
'merge_failed': 'bg-warning text-warning-foreground',
```

`failed` currently uses `bg-destructive text-destructive-foreground` (red). Re-using `bg-warning` (the same token already used by `timeout`, `stalled`, `needs_fix`) communicates "recoverable" without introducing a new Tailwind utility — pick a token that is already in the macro to avoid a `make css` regeneration. If you find that `bg-warning` is too similar to other warning states and you need a new hue (e.g. amber), document that in the report and run `make css`.

Do NOT duplicate the macro or add separate entries for `migration_invalid` / `migration_rebase_failed` — those statuses pre-date this CR and are already rendered (the dict's `.get(status, fallback)` line falls back to muted; if you want them to share the new "recoverable-merge" color, add them to the dict as well, but flag this in the report so reviewers know it's an intentional visual change).

Add `aria-label` only if the existing macro supports it. The current macro renders the raw status string as text, which is sufficient for screen readers; do not add ARIA churn.

### 2. Update `_merge_status` in `dashboard/routers/items.py`

The synthetic MERGE step on the item-overview page maps `BatchItemStatus → display string` via `_merge_status()` (`dashboard/routers/items.py:550-559`). Today it only recognizes `merging`, `completed`, `failed`. Extend it so the new and existing recoverable statuses produce a recognizable display value:

```python
RECOVERABLE_MERGE_STATUSES = {
    BatchItemStatus.merge_failed,
    BatchItemStatus.migration_invalid,
    BatchItemStatus.migration_rebase_failed,
}
...
if bi.status in RECOVERABLE_MERGE_STATUSES:
    return "merge_failed"   # display value used by the badge + button condition
```

Returning the literal `"merge_failed"` ensures both the `status_badge` lookup (Step 1) and the action-button condition in `item_overview.html` (Step 4) trip on the same value.

### 3. Add an `abandon_merge_button` macro and (re-)use the existing confirm-modal pattern

The dashboard does NOT use `hx-confirm`. It uses a confirm-modal pattern: the action button does `hx-get` to `/project/{project_id}/api/confirm-item/<action>/<item_id>`, which renders `fragments/confirm_action.html`, which in turn POSTs to `/project/{project_id}/api/item/<item_id>/<action>`. The label/description for the modal lives in `actions.py:_ITEM_ACTION_LABELS` (registered in S03 step 3c).

Edit `dashboard/templates/components/action_button.html`:

- The existing `restart_merge_button(project_id, item_id)` macro at lines 38-48 already does this for `restart-merge`. **Re-use it** for the recoverable-status rows; do NOT inline a different button shape.
- Add a parallel `abandon_merge_button(project_id, item_id)` macro using `hx-get="/project/{{ project_id }}/api/confirm-item/abandon-merge/{{ item_id }}"`, `bg-destructive text-destructive-foreground` styling (matches the danger semantic from `_ITEM_ACTION_LABELS`'s `danger=True`), and a label like `⚠ Abandon`.

Do **NOT** put `hx-confirm` on the buttons — the irreversibility warning is rendered inside the confirm modal via the `description` field already wired up in S03's `_ITEM_ACTION_LABELS` entry.

### 4. Surface the buttons in `item_overview.html`

Today, `dashboard/templates/fragments/item_overview.html:91` shows the Retry-merge button only when:

```jinja
{% if step.step_id == 'MERGE' and step.status == 'failed' %}
  {{ restart_merge_button(item.project_id, item.id) }}
{% elif not step.is_synthetic %}
  ...
```

Extend the first arm to also cover the recoverable display status (`'merge_failed'` returned by Step 2's `_merge_status`) AND render BOTH buttons there (Retry + Abandon):

```jinja
{% if step.step_id == 'MERGE' and step.status in ('failed', 'merge_failed') %}
  <div class="flex items-center justify-end gap-1">
    {{ restart_merge_button(item.project_id, item.id) }}
    {% if step.status == 'merge_failed' %}
      {{ abandon_merge_button(item.project_id, item.id) }}
    {% endif %}
  </div>
```

**Why both?** A legacy `failed` row (notes startswith "Merge failed") still gets only Retry — the operator can drop a row to legacy-cascade behavior by NOT retrying. The Abandon button is meaningful only for the new non-cascading statuses.

### 5. Surfaces (other than item_overview)

- **Batch detail page** (`dashboard/templates/pages/project/batch_detail.html`): the per-row table currently has only a "View" link in the action column. Adding inline Retry/Abandon there is optional; the badge change alone is sufficient because the operator can click "View" → item-overview → use the buttons there. Do NOT add inline buttons to the batches table in this CR — keep scope focused.
- **Confirm dialog**: the existing `fragments/confirm_action.html` template should already render any action registered in `_ITEM_ACTION_LABELS` — verify by reading the template, no edit needed if it accepts the labels generically.

### 6. Tailwind regeneration

If you introduce **new** Tailwind classes that aren't already in any template (`bg-amber-100` etc.), run:

```bash
make css
```

This regenerates `dashboard/static/styles.css`. Stage the output. If you reuse classes already present in the codebase (the recommended path — see Step 1's note about `bg-warning`), skip this step.

### 7. Smoke-check the rendering

Use the dev dashboard at `http://localhost:9900` (already running per `./ai-core.sh status`). The browser verification (S15) covers full E2E, but a quick visual sanity check is useful:

```bash
playwright-cli kill-all
playwright-cli open http://localhost:9900/project/iw-ai-core/batches
playwright-cli screenshot
```

Note: the dev dashboard runs against the live DB (port 5433). It will not have any `merge_failed` rows yet (the DB enum value won't exist until the migration applies post-merge). You can simulate by temporarily inserting a row in a scratch test DB, or leave deep verification to S15.

## Project Conventions

- Tailwind CSS prebuilt — see `dashboard/CLAUDE.md` "Build step"
- htmx POSTs return HTML fragments
- Fragment templates do NOT extend `base.html`
- Jinja2 macros in `dashboard/templates/components/`
- No JS hand-written; htmx attributes only

## TDD Requirement

Frontend smoke tests are usually integration-level (rendered HTML assertions). For S05:

1. If there are existing template-rendering tests under `tests/dashboard/`, add the minimum needed to assert the new badge variant renders for `merge_failed`.
2. Full E2E lives in S15.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint` — also runs `node --check` on `dashboard/static/**/*.js` per `CLAUDE.md`

## Test Verification (NON-NEGOTIABLE)

`make test-unit` must pass.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "CR-00028",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/...",
    "dashboard/static/styles.css"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Surfaces touched, Tailwind classes introduced, whether make css was run"
}
```
