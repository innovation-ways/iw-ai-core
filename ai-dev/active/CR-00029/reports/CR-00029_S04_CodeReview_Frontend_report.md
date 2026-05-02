# CR-00029_S04_CodeReview_Frontend_report

## Work Item
**CR-00029** — Add Restart button to the synthetic Worktree Setup (S00) row

## Step
**S04** — Code review of S03 (frontend-impl)

## What Was Reviewed

Reviewed the frontend implementation (S03) against the design doc (CR-00029_CR_Design.md), checking:
1. Macro definition (`restart_setup_button`)
2. Template conditional placement and logic
3. No regressions in existing button branches
4. Accessibility
5. Confirm-dialog URL wiring
6. Pre-review lint/format gate and unit tests

## Files Changed (S03)

| File | Change |
|------|--------|
| `dashboard/templates/components/action_button.html` | Added `restart_setup_button` macro |
| `dashboard/templates/fragments/item_overview.html` | Added import + conditional branch for S00 restartable |
| `dashboard/routers/actions.py` | Added `restart-setup` to `_ITEM_ACTION_LABELS`; extracted `_reset_item_to_approved` helper; added `restart_setup` endpoint; S01 backend work visible in this branch |
| `dashboard/routers/items.py` | Added `restartable: bool` to `StepDetail`; `_synthetic_setup_step` computes it from `BatchItem.status ∈ {setup_failed,failed} AND all steps pending` |

## Macro Definition (`restart_setup_button`) — PASS

- Structurally identical to `restart_merge_button`; same `bg-secondary text-secondary-foreground` classes
- `title` attribute present: "Restart setup (delete worktree, reset all steps)"
- `write_button_attrs(request)` macro applied (DB-guard pattern)
- `hx-get` URL `/project/{project_id}/api/confirm-item/restart-setup/{item_id}` matches:
  - The generic `confirm_item_dialog` dispatcher at `/confirm-item/{action}/{item_id}` (actions.py:700)
  - The `_ITEM_ACTION_LABELS["restart-setup"]` entry registered at line 123
  - The POST endpoint at `/project/{project_id}/api/item/{item_id}/restart-setup` (actions.py:1176)

## Conditional Placement (`item_overview.html`) — PASS

The new branch at line 95 (`{% elif step.is_synthetic and step.step_id == 'S00' and step.restartable %}`) is **above** `{% elif not step.is_synthetic %}`, so it matches before the synthetic-exclusion rule.

Branch order verified:
1. `step.step_id == 'MERGE' and step.status == 'failed'` → restart_merge_button
2. `step.is_synthetic and step.step_id == 'S00' and step.restartable` → restart_setup_button ← NEW
3. `not step.is_synthetic` → non-synthetic buttons (restart/skip/kill)
4. (implicit else) → no button

Macro is imported at line 3 with `with context`.

## No-Regression Matrix — PASS

| Case | Expected button | Verified |
|------|----------------|----------|
| MERGE row, status=failed | `restart_merge_button` | ✓ |
| MERGE row, other status | no button | ✓ |
| Synthetic S00, restartable=True | `restart_setup_button` | ✓ (new) |
| Synthetic S00, restartable=False | no button | ✓ |
| Other synthetic rows | no button | ✓ |
| Non-synthetic, status=failed/needs_fix | restart + skip | ✓ |
| Non-synthetic, status=in_progress | kill | ✓ |
| Non-synthetic, other status | no button | ✓ |

## Accessibility — PASS

- Button has `title` attribute ("Restart setup (delete worktree, reset all steps)")
- Text label "↻ Restart Setup" is readable; `↻` is decorative, text carries meaning
- Color not sole signal (text label + icon)
- Real `<button>` element (not `<div>` with `onclick`)

## Confirm-Dialog Flow — PASS

Manual trace:
1. User clicks button → `hx-get /project/{proj}/api/confirm-item/restart-setup/{item_id}` → `confirm_item_dialog` dispatcher
2. Dispatcher looks up `_ITEM_ACTION_LABELS["restart-setup"]` → title "Restart setup?", description, confirm_label "Restart Setup"
3. Renders `confirm_action.html` fragment with `confirm_url = /project/{proj}/api/item/{item_id}/restart-setup`
4. User clicks confirm → POST to `/project/{proj}/api/item/{item_id}/restart-setup`
5. `restart_setup` handler validates preconditions, calls `_reset_item_to_approved`, returns `_action_response(..., reload=True)` which reloads the item-overview fragment

`hx-target="#confirm-dialog"` and `hx-swap="innerHTML"` are correctly set on all action buttons.

## Pre-Review Gate

- **lint**: 5 errors — all in `ai-dev/active/I-00055/I-00058/I-00059/e2e_fixtures/` (pre-existing, unrelated to CR-00029 changed files)
- **format**: 3 files would be reformatted — same pre-existing e2e fixture files
- **test-unit**: `2264 passed, 2 skipped, 5 xfailed, 1 xpassed, 48 warnings` — all CR-00029 tests pass

New violations in changed files: **none**.

## Test Results

```
make lint  →  5 errors (pre-existing unrelated files only)
make format →  3 files would be reformat (pre-existing unrelated files only)
make test-unit  →  2264 passed, 2 skipped, 5 xfailed, 1 xpassed
```

## Observations

- `make css` was not run — no new Tailwind classes introduced (all classes already used by `restart_merge_button`)
- `restart_setup` endpoint shares `_reset_item_to_approved` with `full_restart_item` — DRY, no duplication of state-mutation logic
- `restart_setup` preconditions (BatchItem in setup_failed/failed + no step progressed past pending) are correctly validated before calling `_reset_item_to_approved`
- `confirm_item_dialog` dispatcher correctly handles the `restart-setup` action without a custom GET handler (the `_ITEM_ACTION_LABELS` entry at line 123 suffices)
- The `restartable` field on `StepDetail` defaults to `False`, correctly excluding non-restartable synthetic rows

## Verdict

**PASS** — S03 frontend implementation is correct and complete. All checklist items verified. No mandatory fixes.

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00029",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2264 passed, 2 skipped, 5 xfailed, 1 xpassed",
  "notes": "Lint/format errors are pre-existing in unrelated e2e fixtures (I-00055/58/59), not in CR-00029 changed files. All CR-00029 implementation correct."
}
```