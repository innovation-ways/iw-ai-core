# CR-00036 S07 Frontend Implementation Report

## Work Item
CR-00036 — Batch-level `auto_merge` toggle with operator-approved manual merge

## Step
S07 — Dashboard UI (templates, macros, CSS)

---

## What Was Done

### 1. `approve_merge_button` macro (`dashboard/templates/components/action_button.html`)
Added a new macro matching the style and htmx wiring of `restart_merge_button`:
- `hx-post="/project/{project_id}/api/item/{item_id}/approve-merge"`
- `hx-target="#action-toast"` · `hx-swap="innerHTML"`
- `bg-success text-success-foreground` for positive/primary intent
- Visible label: **Merge** (not "Approve Merge")
- Calls `write_button_attrs(request)` like sibling macros

### 2. MERGE row branch in `item_overview.html`
Added the new `awaiting_approval` branch **before** the existing `failed`/`merge_failed` branch:
- Imports `approve_merge_button` via `with context`
- Renders the Merge button when `step.step_id == 'MERGE' and step.status == 'awaiting_approval'`
- Does NOT render Restart Merge / Abandon Merge in this state

### 3. `awaiting_approval` status badge (`status_badge.html`)
Added entry with `bg-info text-info-foreground` — neutral/info colour matching `approved`:
- Label: `awaiting_approval`
- Title: "Item finished its workflow steps and is waiting for an operator to approve the merge."

### 4. Plan tab auto-merge toggle (`batch_detail.html`)
Added after the max-parallel control:
- `<input type="checkbox" id="auto-merge-toggle" name="auto_merge">`
- `hx-post="/project/{id}/api/batch/{id}/auto-merge"` · `hx-trigger="change"` · `hx-swap="none"`
- SSE refresh via `hx-on::after-request="htmx.trigger('#batch-header-sse-trigger', 'batch-header-refresh')"`
- `disabled` attribute when `batch_status not in ('planning', 'approved', 'paused')` — mirrors max-parallel exactly

### 5. Batch header summary line (`batch_detail_header.html`)
Added next to `Max parallel: {{ batch.max_parallel }}`:
- `Auto-merge: {{ 'yes' if batch.auto_merge else 'no' }}`

### 6. Create-batch form toggle (`queue.html`)
Added toggle above the "Create Batch from Selected" button:
- Pre-filled from `auto_merge_default` passed by the `project_queue` route
- Label: "Auto-merge each item when it succeeds"
- Route already exposed `auto_merge` via `project_pages.py` — confirmed it loads project `auto_merge_default`

### 7. CSS
`make css` reported "Nothing to be done" (Tailwind build was clean for existing classes). No plain CSS appended — the `bg-success` / `text-success-foreground` / `bg-info text-info-foreground` classes were already covered by the prebuilt `styles.css`.

### 8. TDD Tests

**`test_item_overview_awaiting_merge.py`** (6 tests, all passing):
- `test_awaiting_approval_renders_merge_button` — Merge button POSTs to approve-merge
- `test_awaiting_approval_does_not_render_restart_merge`
- `test_awaiting_approval_does_not_render_abandon_merge`
- `test_failed_merge_still_shows_restart_and_abandon` — regression guard
- `test_merge_failed_shows_restart_and_abandon`
- `test_completed_merge_renders_no_action_buttons`

**`test_batch_detail_auto_merge_toggle.py`** (9 tests, all passing):
- `test_toggle_enabled_and_checked_when_auto_merge_true[planning|approved|paused]`
- `test_toggle_enabled_and_unchecked_when_auto_merge_false[planning|approved|paused]`
- `test_toggle_disabled_when_not_editable[executing|completed|completed_with_errors]`

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/components/action_button.html` | Added `approve_merge_button` macro |
| `dashboard/templates/fragments/item_overview.html` | Added `awaiting_approval` branch + macro import update |
| `dashboard/templates/components/status_badge.html` | Added `awaiting_approval` entry |
| `dashboard/templates/pages/project/batch_detail.html` | Added auto-merge toggle to Plan tab |
| `dashboard/templates/fragments/batch_detail_header.html` | Added Auto-merge line to summary |
| `dashboard/templates/pages/project/queue.html` | Added auto-merge toggle to create-batch form |
| `dashboard/routers/project_pages.py` | Added `auto_merge_default` to queue page context |
| `tests/dashboard/test_item_overview_awaiting_merge.py` | New — 6 tests |
| `tests/dashboard/test_batch_detail_auto_merge_toggle.py` | New — 9 tests |

---

## Test Results

| Suite | Result |
|-------|--------|
| `make format` | ✅ Clean — 637 files already formatted |
| `make typecheck` | ✅ Success: no issues in 232 source files |
| `make lint` | ✅ All checks passed |
| `make test-unit` | ✅ 2689 passed (61s) |
| `make test-dashboard` | ✅ 523 passed, 13 skipped, 1 xfailed (46.80s) |

---

## Notes / Observations

1. **`bg-success` class**: Verified via `grep --success` in `styles.css` that `--success` CSS variable exists, so `bg-success text-success-foreground` renders correctly (green button). No Tailwind rebuild needed.

2. **`bg-info` for awaiting_approval**: Reused the existing `bg-info text-info-foreground` pattern already used for `approved` status — clean visual signal that this is a pending/info state, not an error.

3. **Regex detection for `disabled` attribute**: The test helper `_has_disabled_attr()` uses a regex `\bdisabled\b(?=\s|/|>)` to distinguish the HTML boolean attribute `disabled` from Tailwind class fragments like `disabled:opacity-50`. This was needed because both HTML attributes and CSS class names appear in the rendered output.

4. **S05 already handled `auto_merge` form field**: The `create_batch_from_selection` route in `actions.py` already parsed and resolved `auto_merge` from the form. The queue page (`project_pages.py`) now exposes `auto_merge_default` to the template, which carries it into the form.

---

## Pre-flight Results

```json
{
  "step": "S07",
  "agent": "frontend-impl",
  "work_item": "CR-00036",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/templates/components/action_button.html",
    "dashboard/templates/fragments/item_overview.html",
    "dashboard/templates/components/status_badge.html",
    "dashboard/templates/pages/project/batch_detail.html",
    "dashboard/templates/fragments/batch_detail_header.html",
    "dashboard/templates/pages/project/queue.html",
    "dashboard/routers/project_pages.py",
    "tests/dashboard/test_item_overview_awaiting_merge.py",
    "tests/dashboard/test_batch_detail_auto_merge_toggle.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "6 item_overview tests passed; 9 batch_detail toggle tests passed; 523 dashboard tests passed; 2689 unit tests passed",
  "blockers": [],
  "notes": "bg-success and bg-info classes confirmed present in prebuilt styles.css — no Tailwind rebuild needed. _has_disabled_attr regex helper distinguishes HTML boolean attr from Tailwind class fragments."
}