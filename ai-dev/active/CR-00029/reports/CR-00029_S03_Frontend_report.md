# CR-00029_S03_Frontend_report

## Work Item
**CR-00029** — Add Restart button to the synthetic Worktree Setup (S00) row

## Step
**S03** — Frontend implementation

## What Was Done

### 1. Added `restart_setup_button` macro to `action_button.html`

Added a new Jinja2 macro mirroring `restart_merge_button`, pointing at the generic dispatcher endpoint for `restart-setup`:

```jinja
{% macro restart_setup_button(project_id, item_id) %}
  <button
    hx-get="/project/{{ project_id }}/api/confirm-item/restart-setup/{{ item_id }}"
    hx-target="#confirm-dialog"
    hx-swap="innerHTML"
    class="px-2 py-1 bg-secondary text-secondary-foreground rounded text-xs font-medium hover:opacity-90 transition-opacity"
    title="Restart setup (delete worktree, reset all steps)"
    {{ write_button_attrs(request) }}>
    ↻ Restart Setup
  </button>
{% endmacro %}
```

URL: `/project/{project_id}/api/confirm-item/restart-setup/{item_id}` — matches the generic `confirm_item_dialog` dispatcher registered on the actions router (same prefix as `restart-merge`).

### 2. Updated `item_overview.html`

- Added `restart_setup_button` to the existing import from `components/action_button.html`
- Inserted a new conditional branch before `{% elif not step.is_synthetic %}`:

```jinja
{% elif step.is_synthetic and step.step_id == 'S00' and step.restartable %}
  <div class="flex items-center justify-end gap-1">
    {{ restart_setup_button(item.project_id, item.id) }}
  </div>
```

### 3. No regression in existing button flows

| Condition | Button rendered |
|-----------|-----------------|
| `step.step_id == 'MERGE' and step.status == 'failed'` | `restart_merge_button` (unchanged) |
| `step.is_synthetic and step.step_id == 'S00' and step.restartable` | `restart_setup_button` (**NEW**) |
| `step.is_synthetic and step.step_id == 'S00' and not step.restartable` | no button (unchanged) |
| Other synthetic rows (e.g. MERGE with status != failed) | no button (unchanged) |
| Non-synthetic with `status in (failed, needs_fix)` | restart + skip buttons (unchanged) |
| Non-synthetic with `status == in_progress` | kill button (unchanged) |

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/components/action_button.html` | Added `restart_setup_button` macro |
| `dashboard/templates/fragments/item_overview.html` | Added import + conditional branch for S00 restartable |

## Test Results

```
make test-unit  →  2264 passed, 2 skipped, 5 xfailed, 1 xpassed
make typecheck  →  Success: no issues found
make lint       →  5 errors — all in pre-existing unrelated e2e fixtures (I-00055, I-00058, I-00059), not in changed files
make format     →  3 files would be reformatted — pre-existing unrelated e2e fixtures, not in changed files
```

## Observations

- `make lint` and `make format` failures are in `ai-dev/active/I-00055/I-00058/I-00059/e2e_fixtures/` — these are pre-existing issues in files unrelated to this CR
- All Tailwind classes used (`bg-secondary`, `text-secondary-foreground`) are already used by `restart_merge_button` and `restart_button`, so no `make css` regeneration was needed
- The URL `/project/{project_id}/api/confirm-item/restart-setup/{item_id}` is consistent with the existing `restart_merge_button` URL pattern and matches the backend dispatcher registered in S01
