# I-00092_S02_CodeReview_report

## Work Item
I-00092 — Auto-merge filter chip never highlights the active filter

## Step Reviewed
S01 (frontend-impl)

## Review Result: PASS ✓

---

## Summary

S01 correctly fixed the filter chip active-state comparison in the auto-merge events table fragment. The implementation is minimal, correct, and complete.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/fragments/auto_merge_events_table.html` | Fixed comparison logic + added accessibility attributes |

**Diff**: 3 insertions, 1 deletion in 1 file.

---

## Pre-Flight Checks

| Check | Result |
|-------|--------|
| `make lint` | ✓ All checks passed |
| `make format` | ✓ 750 files already formatted |
| `uv run pytest tests/dashboard/test_auto_merge_routes.py -v` | ✓ 25 passed |

Coverage warning (20% < 50%) is **pre-existing** and unrelated to this change.

---

## Checklist Verification

### 1. Comparison logic ✓
- Old (broken): `{% if type_filter == key %}` — compared `"merge_auto_resolved"` to `"resolved"`, always False
- New (fixed): `{% set _is_active = (mapped is none and not request.query_params.get('type')) or (mapped is not none and type_filter == mapped) %}` — compares `type_filter` to `mapped` (the actual URL value)
- `all` chip's special case (no `type` param) is preserved: `mapped is none and not request.query_params.get('type')`

### 2. Attributes ✓
- `title="{{ mapped or 'all event types' }}"` — present on every chip (line 18)
- `aria-pressed="{{ 'true' if _is_active else 'false' }}"` — present on every chip (line 19)
- Exactly one chip is active per render — `_is_active` is mutually exclusive

### 3. No regression ✓
- Labels, URLs, layout, pagination, and events table structure are **unchanged**
- Only the active-chip class branch was modified

### 4. Jinja2 `format` filter discipline ✓
- No `| format` filter usage in the changed template (confirmed by grep)

### 5. Class names ✓
- Only existing Tailwind classes used: `px-2 py-1 rounded border text-xs bg-primary text-primary-foreground border-primary border-border text-muted-foreground`
- No new class names introduced

### 6. No new `<script>` blocks ✓
- No `<script>` tags in the template

### 7. Test placement ✓
- S01 correctly did **not** add tests (tests belong in S03 per the plan)

### TDD RED Evidence
`n/a — template-only edit` (correct per the step instructions)

---

## Acceptance Criteria Review

| AC | Status |
|----|--------|
| AC1: Selected filter chip is highlighted | ✓ Implemented — `_is_active` correctly highlights the active chip |
| AC2: "all" chip active when no type param | ✓ Implemented — special case `mapped is none and not request.query_params.get('type')` |
| AC3: Each chip has tooltip + aria-pressed | ✓ Implemented — `title` and `aria-pressed` on every chip |

---

## Findings

**None.** The implementation is correct and complete.

---

## Mandatory Fix Count
0

---

## Notes
The fix is a single, focused template edit that correctly resolves the root cause: comparing `type_filter` to `mapped` (the actual event_type string like `merge_auto_resolved`) instead of `key` (the short label like `resolved`). The `all` chip's special case is correctly preserved. Accessibility attributes (`title`, `aria-pressed`) are correctly applied.
