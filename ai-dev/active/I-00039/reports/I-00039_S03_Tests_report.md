# I-00039 S03 Tests Report

## What was done

Created `tests/dashboard/test_jobs_filter_ui.py` with 3 tests that verify the I-00039 fix (drop color-coded Type chips, replace filter checkboxes with multi-select dropdowns).

## Files changed

- `tests/dashboard/test_jobs_filter_ui.py` — **NEW** (3 tests)

## Test results

```
uv run pytest tests/dashboard/test_jobs_filter_ui.py -v
3 passed

make test-unit
1547 passed, 0 failed
```

## Test semantics (RED verification)

| Test | Would FAIL on pre-fix code because |
|------|----------------------------------|
| `test_jobs_type_cell_is_plain_text_no_color_chip` | Pre-fix HTML contains `bg-blue-100`, `bg-purple-100`, `bg-orange-100`, `bg-teal-100`, `bg-emerald-100` from `type_chip` macro — each assertion would raise `AssertionError` |
| `test_jobs_filter_uses_multiselect_dropdown_not_checkbox_groups` | Pre-fix HTML has flat `<input type="checkbox" name="type"` at the form level (not inside a `data-multi-select-panel` wrapper); the regex extracting the panel content finds nothing, so `type_panel_content` is empty and `<inputtype="checkbox"name="type"` is NOT found inside it — causing the assertion to fail |
| `test_jobs_filter_multiple_types_still_filters` | Pre-fix code already passes this (query-string contract unchanged) — regression guard only |

## Implementation notes

- Reused `_seed_all_sources` from `tests/integration/test_jobs_api.py` for consistent seeding
- Created a local `client` fixture in the test file rather than importing from dashboard conftest, to avoid fixture scope issues with the testcontainer session
- The multi-select checkboxes live INSIDE the `data-multi-select-panel` div (correct by design) — the test uses regex to locate the panel boundaries and verifies checkboxes appear only within those bounds

## Blockers

None.
