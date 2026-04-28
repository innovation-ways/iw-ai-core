# I-00044 S03 Tests Report

## Summary

Created `tests/dashboard/test_i00044_chat_panel_layout.py` with 7 tests covering both bugs fixed in S01.

## Tests Created

| Test Class | Test Method | Bug | Purpose |
|------------|-------------|-----|---------|
| `TestBug2GridRowConstraint` | `test_page_body_has_grid_rows_1fr` | Bug 2 | Verifies `lg:grid-rows-[1fr]` is present on `#page-body` |
| `TestBug2GridRowConstraint` | `test_page_body_grid_height_preserved` | Bug 2 | Regression guard for `lg:h-[calc(100vh-12rem)]` and `lg:grid-cols-[1fr_var(--chat-width)]` |
| `TestBug1CollapseToggleAffordance` | `test_toggle_tab_has_chat_label` | Bug 1 | "Chat" label must appear inside the toggle tab, not just anywhere on page |
| `TestBug1CollapseToggleAffordance` | `test_toggle_tab_has_aria_label_with_chat` | Bug 1 | `aria-label` on toggle tab must contain "chat" (case-insensitive) and be non-empty |
| `TestBug1CollapseToggleAffordance` | `test_collapsed_state_is_not_bare_chevron_only` | Bug 1 | Toggle tab must have either `<svg>` icon or "Chat" text — the bare pre-fix chevron had neither |
| `TestBug1KeyboardAccessibility` | `test_toggle_tab_is_a_button` | Bug 1 | Toggle tab must be a `<button>`, not `<div>` or `<span>` |
| `TestBug1KeyboardAccessibility` | `test_mobile_elements_unchanged` | Bug 1 | Regression guard for mobile elements: `chat-close-btn`, `chat-drawer-open`, `chat-drawer-backdrop` |

## Test Results

```
tests/dashboard/test_i00044_chat_panel_layout.py::TestBug2GridRowConstraint::test_page_body_has_grid_rows_1fr PASSED
tests/dashboard/test_i00044_chat_panel_layout.py::TestBug2GridRowConstraint::test_page_body_grid_height_preserved PASSED
tests/dashboard/test_i00044_chat_panel_layout.py::TestBug1CollapseToggleAffordance::test_toggle_tab_has_chat_label PASSED
tests/dashboard/test_i00044_chat_panel_layout.py::TestBug1CollapseToggleAffordance::test_toggle_tab_has_aria_label_with_chat PASSED
tests/dashboard/test_i00044_chat_panel_layout.py::TestBug1CollapseToggleAffordance::test_collapsed_state_is_not_bare_chevron_only PASSED
tests/dashboard/test_i00044_chat_panel_layout.py::TestBug1KeyboardAccessibility::test_toggle_tab_is_a_button PASSED
tests/dashboard/test_i00044_chat_panel_layout.py::TestBug1KeyboardAccessibility::test_mobile_elements_unchanged PASSED

7 passed, 1 warning in 0.04s
```

Full `make test-unit`: **1910 passed, 2 skipped, 48 warnings**

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | Fixed (ruff format auto-formatted the file) |
| `make typecheck` | ok (mypy 0 errors on 190 source files) |
| `make lint` | ok (ruff check passed) |
| `make test-unit` | ok (1910 passed) |

## Files Changed

- `tests/dashboard/test_i00044_chat_panel_layout.py` (created)

## Notes

- All tests follow the exact Jinja2 rendering pattern from `tests/dashboard/test_code_layout_fixes.py` (I-00033)
- Tests verify specific element attributes and class values, not just substring existence (per I-003 lesson)
- The `jinja_env` fixture provides all required stubbed filters (`intcomma`, `timeago`, `fmt_ts_time`, `localdt`) and globals (`url_for`, `is_db_stale`)
- `mock_request` is used for templates that reference `request.url.path`
