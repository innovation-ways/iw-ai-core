# CR-00042 S05 — Tests Implementation Report

## Summary

Completed test coverage for CR-00042 (Fix Broken "Open full docs" Links in Help Popups).

## Files Changed

- `tests/dashboard/test_system_docs_route.py` — Added `TestSystemDocsSlugMapping` class with 3 new tests (T5, T6, T4)
- `tests/dashboard/test_help_router.py` — Added `test_help_fragment_docs_link_points_to_system_docs` parameterized test

## Tests Added

### `test_system_docs_route.py` — `TestSystemDocsSlugMapping`

| Test | What it verifies |
|------|-----------------|
| `test_slug_to_doc_all_values_point_to_system_docs` (T5) | Every value in `_SLUG_TO_DOC` starts with `/system/docs/` |
| `test_slug_to_doc_covers_all_help_slugs` (T6) | All 22 known help slugs are present in `_SLUG_TO_DOC` |
| `test_toc_extension_generates_heading_ids` (T4) | The `toc` markdown extension generates `id=` attributes in rendered HTML |

### `test_help_router.py` — `test_help_fragment_docs_link_points_to_system_docs`

Parameterized over `["queue", "batches", "status", "code"]`. Verifies:
- Response contains `href="/system/docs/"`
- Response does **not** contain `href="/docs/"` (the old broken path)
- Response does **not** contain `href="/orch/"` (another old broken path)

## Test Results

```
53 passed, 0 failed
```

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok |
| `make typecheck` | ok |
| `make lint` | ok |

## Notes

- All 6 required tests from the step prompt are implemented and passing.
- The `test_help_fragment_docs_link_points_to_system_docs` test uses anchored negative assertions (`href="/docs/"` not `"/docs/"`) to avoid false positives from legitimate substrings inside `/system/docs/IW_AI_Core_...`.
- T1 (rendered HTML vs raw markdown) was already covered by existing `test_valid_doc_slug_returns_200` which asserts `prose-doc` class presence.
- T2 (unknown slug → 404) was already covered by existing `test_nonexistent_slug_returns_404`.
- T3 (path traversal → 404) was already covered by existing `test_path_traversal_returns_404` and `test_path_traversal_raw_returns_404`.