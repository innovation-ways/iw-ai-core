# I-00076 S01 Frontend Implementation Report

## What Was Done

Fixed the per-step CLI/runtime override `<select>` in `dashboard/templates/fragments/item_overview.html` (editable-step branch, lines 78–93).

**Root cause**: The `onchange="this.style.opacity='0.5'; this.disabled=true; htmx.trigger(this, 'change');"` handler was:
1. Setting `this.disabled = true` **before** htmx serialised the request — causing htmx's `shouldInclude()` to drop `option_id` from the body (disabled controls are excluded), so the override was silently cleared instead of set.
2. Redundantly calling `htmx.trigger(this, 'change')` — double-firing the PATCH since `<select>` already triggers htmx on `change` by default.

**Fix applied**:
- Removed the self-disabling `onchange` attribute entirely.
- Added `hx-disabled-elt="this"` — htmx adds `disabled` **after** serialising the form values and re-enables on completion, so `option_id` is always sent.
- Added a Jinja comment explaining why the control must not self-disable.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/fragments/item_overview.html` | Replaced `onchange="…this.disabled…; htmx.trigger…"`, added `hx-disabled-elt="this"` + explanatory comment |

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok — 661 files already formatted |
| `make typecheck` | ok — 0 errors in 239 source files |
| `make lint` | ok — All checks passed |

## Test Results

```bash
uv run pytest tests/dashboard/test_runtime_override_templates.py -q
# 10 passed, 1 warning in 23.45s
# Coverage failure is pre-existing (46% threshold vs 18.72% actual) — unrelated to this template edit.
```

## Observations

- No new Tailwind classes were added, so `make css` was not required.
- The bulk "Apply to remaining steps" button (`hx-vals="javascript:{option_id: ...}"`) was untouched — it is in a different branch of the template and unaffected.
- `dashboard/routers/runtime_overrides.py` was read-only — `patch_step_runtime_override` is correct; no changes needed there.