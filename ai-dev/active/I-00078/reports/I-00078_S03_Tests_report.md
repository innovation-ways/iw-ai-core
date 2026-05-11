# I-00078 S03 Tests-impl Report

## Summary

Wrote 8 reproduction + regression tests for I-00078 in `tests/dashboard/test_i00078_layout.py`. All tests pass against the fixed code.

## Files Changed

- `tests/dashboard/test_i00078_layout.py` — rewritten from S01's minimal 5-test seed to a full 8-test suite covering all 4 acceptance criteria.

## Tests Added

| Test | Acceptance Criteria | What It Checks |
|------|---------------------|----------------|
| `test_i00078_footer_is_full_width_sibling_of_sidebar` | AC3, AC4 | `<footer>` appears after `</aside>`; footer tag has `w-full` class; old `flex h-screen overflow-hidden` shell wrapper is absent |
| `test_i00078_theme_toggle_in_footer_not_sidebar` | AC4 | `toggleDarkMode()` is NOT in sidebar HTML slice; IS in footer HTML slice |
| `test_i00078_theme_toggle_outside_htmx_swap_target` | AC4 (regression guard) | `toggleDarkMode()` is not inside the element carrying `hx-swap="innerHTML"` — prevents poll-wipes-toggle failure mode |
| `test_i00078_shell_uses_dynamic_viewport_height` | AC3 | `h-dvh` or `100dvh` token present in HTML; old `h-screen` shell absent |
| `test_i00078_only_main_is_the_scroller` | AC3 | `<main>` carries `overflow-y-auto`; `<body>` carries `overflow-hidden` |
| `test_i00078_pipeline_strip_has_scrollbar_spacing` | AC2 | `.iw-pipeline-strip` block in `styles.css` declares `padding-bottom` with a non-zero value |
| `test_i00078_dark_scrollbar_high_contrast_thumb` | AC1 | `::-webkit-scrollbar-thumb` block does NOT contain `var(--border)`; `:hover` rule exists; `scrollbar-color` and `scrollbar-width` exist; `--scrollbar-thumb` CSS var defined in both `:root` and `.dark` |
| `test_i00078_theme_toggle_still_wired` | AC4 | Footer contains `<button onclick="toggleDarkMode()">`; exactly one `id="theme-icon"` in the page |

## Test Results

```
tests/dashboard/test_i00078_layout.py::test_i00078_footer_is_full_width_sibling_of_sidebar PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_theme_toggle_in_footer_not_sidebar PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_theme_toggle_outside_htmx_swap_target PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_shell_uses_dynamic_viewport_height PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_only_main_is_the_scroller PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_pipeline_strip_has_scrollbar_spacing PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_dark_scrollbar_high_contrast_thumb PASSED
tests/dashboard/test_i00078_layout.py::test_i00078_theme_toggle_still_wired PASSED
========================= 8 passed in 6.25s =========================
```

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | `ruff format` auto-fixed the test file |
| `make typecheck` | `Success: no issues found in 240 source files` |
| `make lint` | All checks passed (PT018 assertions broken down into multiple parts) |

## Notes

- The `client` fixture was reimplemented in the test file (not imported from `conftest.py`) to avoid the `LiveDbConnectionRefusedError` collection-time error — this pattern matches all other dashboard test files (e.g., `test_docs_running_jobs.py`, `test_jobs_filter_ui.py`).
- The `test_i00078_theme_toggle_outside_htmx_swap_target` test walks the DOM tree to correctly isolate the element carrying `hx-swap="innerHTML"` and its subtree, ensuring the toggle button is a static sibling — this guards against a regression where the htmx poll target is accidentally moved back to `<footer>`.
- The `test_i00078_only_main_is_the_scroller` test confirms the sidebar `<aside>` also has `overflow-y-auto` (which is fine and intentional) — it only asserts `<main>` has `overflow-y-auto` and `<body>` has `overflow-hidden`.
- No changes to production code were made.
