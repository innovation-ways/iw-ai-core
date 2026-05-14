# F-00082_S03_Frontend_report — Dashboard Cancel Buttons: Frontend Layer

## Step: S03
**Agent**: Frontend (`frontend-impl`)
**Work Item**: F-00082 — Dashboard Cancel Buttons (Batch + Work Item)
**Date**: 2026-05-14

---

## What Was Done

### 1. Extended `confirm_dialog` macro with optional `form_html` parameter

**File**: `dashboard/templates/components/confirm_dialog.html`

Added a `form_html=""` parameter (default empty string). When set, the macro wraps the body and action buttons inside a `<form method="post" hx-post="{{ confirm_url }}" hx-swap="none">`. The Cancel dismiss button stays outside the form so dismissing doesn't submit. When `form_html` is empty (default), the macro renders identically to the original — buttons via `hx-{{ confirm_method }}` directly, no `<form>` element.

Existing call sites (approve / pause / resume / kill) pass no `form_html`, so the generated HTML is byte-identical to before. S05's snapshot test will verify this.

### 2. Created `confirm_action_form.html` fragment

**File**: `dashboard/templates/fragments/confirm_action_form.html` (NEW)

This fragment is returned by the confirm-dialog GET endpoint when `action == "cancel"`. It calls `confirm_dialog` with a `form_html` string built from `default_reason`, `reset_field_name`, and `reset_field_label` context variables (exact names from S01 contract):

```jinja
form_html='<label>Reason: <textarea name="reason" ...>' ~ default_reason ~ '</textarea></label>
           <label><input type="checkbox" name="' ~ reset_field_name ~ '" value="true">' ~ reset_field_label ~ '</label>'
```

Tailwind classes on the textarea: `w-full mt-2 px-3 py-2 border border-border rounded text-sm bg-background text-foreground resize-y`. Checkbox container: `mt-3 flex items-center gap-2 text-sm`. Since `cursor-not-allowed` was already used in the codebase, no new Tailwind classes were introduced.

### 3. Expanded cancel button visibility in `batch_detail_header.html`

**File**: `dashboard/templates/fragments/batch_detail_header.html`

Replaced the old if/elif chain (only `planning` → Cancel, `approved` → Cancel) with a single condition:

```jinja
{% if batch_status in ('planning', 'approved', 'executing', 'paused', 'blocked', 'publish_failed') %}
  <button hx-get="/project/{{ current_project.id }}/api/confirm-batch/cancel/{{ batch.id }}" ...>Cancel</button>
{% endif %}
```

Terminal statuses (`completed`, `completed_with_errors`, `publishing`, `published`, `archived`, `cancelled`) render no Cancel button. The `executing`, `blocked`, `publish_failed` statuses are new coverage compared to the original template.

### 4. Added `batch_status` to item detail route context

**File**: `dashboard/routers/items.py`

Added `_get_batch_status()` helper (looks up `Batch.status` by composite key `project_id, batch_id`) and added `batch_status` to the context dict for both `item_detail()` and `item_header_fragment()`. This was needed so the item header can gate the Cancel button on whether the parent batch is in an active status (`_ACTIVE_BATCH_STATUSES`).

### 5. Added cancel button + disabled state to `item_header.html`

**File**: `dashboard/templates/fragments/item_header.html`

For `approved`, `in_progress`, `paused`, `failed` item statuses:
- **If `batch_ref` is set AND `batch_status` is in `_ACTIVE_BATCH_STATUSES`**: render a **disabled** button (`disabled class="cursor-not-allowed opacity-50"`) plus a hint paragraph: `Belongs to active batch BATCH-XXX — cancel the batch instead.` (links to the batch detail page).
- **Otherwise**: render an enabled htmx button that GETs `…/api/confirm-item/cancel/{{ item.id }}`.

CANCELLABLE_WORK_ITEM_STATUSES (`approved`, `in_progress`, `failed`, `paused`) are all covered. The `approved` branch also gained a Cancel button (was missing before).

### 6. Added per-row quick-cancel to `batches.html`

**File**: `dashboard/templates/pages/project/batches.html`

Added an `actions` column header (non-sortable) and per-row cancel icon-button (`✕`) for batches in `CANCELLABLE_BATCH_STATUSES`. For terminal statuses, nothing is rendered. The button uses `onclick="confirm('Cancel {{ batch.id }}? This is destructive.') && htmx.ajax('POST', '…/api/batch/{{ batch.id }}/cancel', {values:{reason:'cancelled from batches list'}, swap:'none'})"`. `event.stopPropagation()` prevents row click navigation when clicking the icon.

### 7. Updated `dashboard/CLAUDE.md`

**File**: `dashboard/CLAUDE.md`

Updated the `actions.py` router description to clarify the full-teardown semantics:
```
| `actions.py` | htmx endpoints: approve / unapprove / cancel (full teardown via `orch.cancel`) / pause / resume / restart / restart-merge / full-restart item; batch approve/pause/resume/cancel (full teardown)/archive; create batch from selection |
```

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/components/confirm_dialog.html` | Extended macro with `form_html` parameter; non-form branch unchanged |
| `dashboard/templates/fragments/confirm_action_form.html` | **NEW** — form-bearing confirm dialog for cancel actions |
| `dashboard/templates/fragments/batch_detail_header.html` | Expanded cancel button to all CANCELLABLE_BATCH_STATUSES |
| `dashboard/templates/fragments/item_header.html` | Added cancel button + disabled-with-hint state for active-batch items |
| `dashboard/templates/pages/project/batches.html` | Added per-row quick-cancel ✕ icon-button |
| `dashboard/routers/items.py` | Added `_get_batch_status()` + `batch_status` to item_detail + item_header_fragment context |
| `dashboard/CLAUDE.md` | Updated actions.py router description |
| `tests/dashboard/test_confirm_dialog_form.py` | **NEW** — 4 anchor tests |

---

## TDD Evidence

```
tests/dashboard/test_confirm_dialog_form.py::test_confirm_dialog_macro_renders_form_when_form_html_set FAILED
AssertionError: Expected a <form> element when form_html is set

tests/dashboard/test_confirm_dialog_form.py::test_confirm_dialog_macro_byte_identical_when_form_html_empty FAILED
AssertionError: assert 'Approve' in ''

tests/dashboard/test_confirm_dialog_form.py::test_batch_detail_header_renders_cancel_button_for_executing_batch FAILED
NameError: name 'SimpleNamespace' is not defined

tests/dashboard/test_confirm_dialog_form.py::test_item_header_renders_disabled_cancel_when_in_active_batch FAILED
NameError: name 'SimpleNamespace' is not defined
```

RED #1, #2: `template.render(...)` on a macro-only template returns empty string. Macro must be called via `template.module.confirm_dialog(...)`. Fixed by changing to direct macro call.

RED #3, #4: `SimpleNamespace` was imported but `types` module was missing. Added `from types import SimpleNamespace`.

After fixes, all 4 passed:

```
tests/dashboard/test_confirm_dialog_form.py::test_confirm_dialog_macro_renders_form_when_form_html_set PASSED
tests/dashboard/test_confirm_dialog_form.py::test_confirm_dialog_macro_byte_identical_when_form_html_empty PASSED
tests/dashboard/test_confirm_dialog_form.py::test_batch_detail_header_renders_cancel_button_for_executing_batch PASSED
tests/dashboard/test_confirm_dialog_form.py::test_item_header_renders_disabled_cancel_when_in_active_batch PASSED
```

---

## Test Results

```
4 passed in 0.05s
```

---

## Preflight

| Check | Result |
|-------|--------|
| `make format` | ok (ruff format applied to test file) |
| `make typecheck` | ok (0 mypy errors) |
| `make lint` | ok (0 errors — ruff + check_templates.py) |
| `make css` | Nothing to be done (no new Tailwind classes added; `cursor-not-allowed` already existed) |

---

## Notes

- **`make css`**: No new Tailwind classes were introduced. The disabled cancel button uses `cursor-not-allowed` and `opacity-50` which were already used in `project_selector.html`, `dashboard.html`, `batch_detail.html`, and `oss.html`. No `make css` was needed in this step.
- **Route change — `item_detail()` and `item_header_fragment()`**: Added `batch_status` to the context dict so the template can gate cancel on active batch status without making a separate DB call per render.
- **Duplicate `item_header_fragment` function**: During editing, a stray duplicate appeared (line 1198) due to merge conflict. Removed the duplicate, verified no-redef with `make typecheck`.
- **`cursor-not-allowed` existing usage**: Confirmed via grep that `cursor-not-allowed` is already used in 16 places across the codebase — no risk of JIT purge.

---

## Blockers

None.

---

## Files List for S03 Completion

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "F-00082",
  "completion_status": "complete",
  "files_changed": [
    "dashboard/templates/components/confirm_dialog.html",
    "dashboard/templates/fragments/confirm_action_form.html",
    "dashboard/templates/fragments/batch_detail_header.html",
    "dashboard/templates/fragments/item_header.html",
    "dashboard/templates/pages/project/batches.html",
    "dashboard/routers/items.py",
    "dashboard/CLAUDE.md",
    "tests/dashboard/test_confirm_dialog_form.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "4 passed in 0.05s",
  "tdd_red_evidence": "tests/dashboard/test_confirm_dialog_form.py::test_confirm_dialog_macro_renders_form_when_form_html_set — AssertionError: Expected a <form> element when form_html is set",
  "blockers": [],
  "notes": "All 4 anchor tests pass. make css was no-op (no new Tailwind classes). make lint clean."
}
```