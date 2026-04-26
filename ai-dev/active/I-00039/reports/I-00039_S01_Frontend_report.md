# I-00039 S01 Frontend Report

## What was done

1. **Deleted `type_chip` macro from both files** — removed from `jobs_table.html` (lines 21–32) and `jobs.html` (lines 21–32).
2. **Replaced Type cell call site** — `jobs_table.html:68` now renders plain text `{{ row.job_type.value }}` in `text-xs text-foreground` class (matching Title cell pattern).
3. **Created `components/multi_select.html`** — reusable Jinja macro with `data-multi-select` wrapper, `data-multi-select-btn` button, `data-multi-select-panel` popover, ARIA attributes, and `hidden` default.
4. **Created `static/multi_select.js`** — vanilla JS ~50 lines: open/close toggle, aria-expanded, "(N selected)" label, Escape key, click-outside close.
5. **Replaced filter blocks in `jobs.html`** — Type and Status checkbox groups replaced with `{{ multi_select(...) }}` calls; date inputs and Filter/Clear unchanged.
6. **Added `<script src="/static/multi_select.js" defer>`** to `jobs.html` end of content block.
7. **Ran `make css`** — `styles.css` regenerated successfully.

## Files changed

| File | Change |
|------|--------|
| `dashboard/templates/fragments/jobs_table.html` | Deleted `type_chip` macro; Type cell now plain text |
| `dashboard/templates/pages/project/jobs.html` | Deleted `type_chip` macro; replaced checkbox groups with `multi_select` calls; added script include |
| `dashboard/templates/components/multi_select.html` | **NEW** reusable multi-select dropdown macro |
| `dashboard/static/multi_select.js` | **NEW** vanilla JS popover behaviour |
| `dashboard/static/styles.css` | Regenerated via `make css` |

## Test results

- `make lint`: **passed** (All checks passed!)
- `uv run ruff format --check .`: **passed** (376 files already formatted)
- `make css`: **passed** (Done in 4524ms)
- `make test-unit`: **1545 passed, 2 failed** — failures are pre-existing in `test_safe_migrate.py` (unrelated, DNS resolution issue in test fixture)

The 2 test failures existed before this change (verified by stashing changes and re-running).

## Notes

- `jobs_table.html` type cell uses `text-xs text-foreground` to match the Title cell's `text-xs text-foreground` class, per the design spec.
- The `multi_select` macro uses `data-multi-select="{{ name }}"` on the wrapper div and `data-multi-select-panel="{{ name }}"` on the popover — the JS and S03 tests assert on these attributes.
- The `type_chip` macro in `jobs_table.html` was previously the **invoked** one (called at line 68); the `jobs.html` copy was dead code. Both are now deleted.
- The popover panel is `hidden` by default and shown/hidden via the JS toggle.
