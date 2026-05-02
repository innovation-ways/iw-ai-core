# CR-00028 S06 CodeReview — Frontend (S05) Report

**Step**: S06
**Agent**: CodeReview
**Work Item**: CR-00028 — Don't cascade merge-time failures to dependent items
**Step Reviewed**: S05 (frontend-impl)
**Date**: 2026-05-02

---

## Summary

S05 adds `merge_failed` badge, recoverable status styling, and `abandon_merge_button` to the dashboard. The implementation is clean and correct. One pre-existing lint violation in `actions.py:1170` (unrelated to this CR). Zero new violations introduced by S05 changes. All quality gates pass.

---

## Files Reviewed

| File | Changes |
|------|---------|
| `dashboard/templates/components/status_badge.html` | Added `merge_failed`, `migration_invalid`, `migration_rebase_failed` → `bg-warning text-warning-foreground` |
| `dashboard/templates/components/action_button.html` | Added `abandon_merge_button` macro with danger styling |
| `dashboard/templates/fragments/item_overview.html` | Extended MERGE-step button condition; renders both buttons for `merge_failed` |
| `dashboard/routers/items.py` | Extended `_merge_status()` with `recoverable_merge_statuses` set |
| `dashboard/routers/actions.py` | Added `abandon-merge` entry in `_ITEM_ACTION_LABELS` (danger=True); added `POST /item/{item_id}/abandon-merge` endpoint |
| `dashboard/routers/sse.py` | Registered `merge_abandoned` event and severity |

---

## Review Checklist

### 1. Visual / Status Badge ✅

- `merge_failed` → `bg-warning text-warning-foreground` (amber/yellow)
- `failed` → `bg-destructive text-destructive-foreground` (red)
- Visually distinct at a glance — amber vs red satisfies the design intent
- `migration_invalid` and `migration_rebase_failed` also use `bg-warning` (intentional per S05 report, consistent with other recoverable statuses)

**Convention check**: Badge spans use `inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-medium` — same shape/size/padding as all existing badges. No rogue styling introduced.

**No `aria-label`** on the `<span>` badge itself. The badge is decorative+text (contains visible status text), not an interactive element — this is acceptable per accessibility guidelines for non-interactive static content.

### 2. Action Buttons (confirm-modal pattern) ✅

- **"Retry merge"** (`restart_merge_button`): `hx-get="/project/{id}/api/confirm-item/restart-merge/{item_id}"` — correct modal route pattern, NOT `hx-post` + `hx-confirm`. ✅
- **"Abandon"** (`abandon_merge_button`): `hx-get="/project/{id}/api/confirm-item/abandon-merge/{item_id}"` — correct modal route pattern. ✅
- **No `hx-confirm`** on either button. The dashboard confirmation pattern is exclusively the modal route. ✅
- **Button condition** (`item_overview.html:91`): `step.step_id == 'MERGE' and step.status in ('failed', 'merge_failed')` — renders both buttons when `step.status == 'merge_failed'`; only Retry when `step.status == 'failed'`. ✅ Back-compat preserved.
- **`abandon_merge_button`** only shown when `step.status == 'merge_failed'` (line 94). ✅
- `_ITEM_ACTION_LABELS["abandon-merge"]` registered with `danger=True` (line 124-129). ✅ Modal will render with correct danger styling.

**Shape/size match**: Both buttons use `px-2 py-1 bg-secondary/... rounded text-xs font-medium` — same padding as existing `restart_merge_button` and other action buttons.

### 3. Surfaces ✅

- **Batch detail page**: `status_badge.html` is a macro used everywhere batch items are rendered — `merge_failed` will display with `bg-warning` on batch detail automatically. No additional changes needed.
- **Item overview**: Verified — `item_overview.html` renders the new badge via `status_badge(step.status)` and the full button set for `merge_failed` rows.

### 4. Tailwind / CSS ✅

- `bg-warning` is an **existing** token used by `timeout`, `stalled`, `needs_fix`. No new utility classes introduced.
- Per `dashboard/CLAUDE.md`, `make css` is only required when new Tailwind classes are added. Not required here.
- No dynamic class construction detected.

### 5. Project Conventions ✅

- **Fragment templates don't extend `base.html`**: Verified — `item_overview.html` is a fragment (renders a `<table>`, no base extend).
- **htmx POSTs return HTML fragments**: `abandon_merge` action returns `_action_response(...)` which is the standard fragment response pattern (same as all other actions in `actions.py`).
- **Jinja2 macros reused**: `restart_merge_button`, `abandon_merge_button`, `status_badge` — no copy-paste duplication of macro internals.

### 6. Accessibility ✅

- **ARIA labels on buttons**: `title="Retry merge"` and `title="Abandon merge"` — adequate for tooltip/hover tooltip purpose.
- **Color is not the only signal**: Button text labels "↻ Retry Merge" and "⚠ Abandon" carry the semantic meaning. Operator can distinguish without color perception.
- **Keyboard-navigable**: Both are real `<button>` elements. ✅

### 7. Browser Smoke Check — Deferred to S15

Dev DB does not have `merge_failed` enum value (migration applies post-merge). Cannot render a live `merge_failed` row in the dev environment. Visual confirmation of the new badge and buttons deferred to S15 (qv-browser).

---

## Pre-Review Lint & Format Gate

```bash
# Lint: 1 pre-existing error in CR-00028 changed files, 0 new
E501 actions.py:1170 — line too long (126 > 100) in restart-setup handler
  Not introduced by S05 — pre-existing violation unrelated to this CR.

# Format: CR-00028 Python files — 0 new violations
dashboard/routers/items.py     ✅ already formatted
dashboard/routers/actions.py  ✅ already formatted
dashboard/routers/sse.py      ✅ already formatted
```

HTML templates are Jinja2 (not ruff-checkable) — verified format-compliant via `make format` hitting non-existent files only.

---

## Test Results

```
===== 2291 passed, 2 skipped, 5 xfailed, 1 xpassed, 48 warnings in 52.14s =====
Required coverage: 46.0%  |  Actual: 52.01%  ✅
```

All tests pass. No regressions.

---

## Findings

| Severity | File | Line | Description | Suggested Fix |
|----------|------|------|-------------|---------------|
| LOW (pre-existing) | `dashboard/routers/actions.py` | 1170 | Line 126 chars (limit 100) — restart-setup handler detail message | Not introduced by S05; tracked separately |

---

## Verdict

```
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "CR-00028",
  "step_reviewed": "S05",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2291 passed, 2 skipped, 5 xfailed, 1 xpassed",
  "notes": "S05 frontend implementation is clean. merge_failed badge distinct from failed (amber vs red). Both buttons use correct hx-get modal pattern (no hx-confirm). _ITEM_ACTION_LABELS['abandon-merge'] registered with danger=True. Legacy failed back-compat preserved. Pre-existing lint violation in actions.py:1170 not introduced by this CR. make css not required (bg-warning token reused). Browser verification of new badge deferred to S15."
}
```