# QV Gate Report: lint (S07)

## What was done
Ran `make lint` (ruff + JS syntax check).

## Result
**FAIL** — Exit code 1.

## Issues Found (8 errors)

| File | Line | Code | Description |
|------|------|------|-------------|
| executor/scope_gate.py | 75 | T201 | `print` found (should be removed) |
| orch/db/migrations/versions/1fb2eb17b580_add_functional_doc_columns_to_work_items.py | 9 | I001 | Import block is un-sorted or un-formatted |
| orch/db/migrations/versions/1fb2eb17b580_add_functional_doc_columns_to_work_items.py | 11 | UP035 | Import `Sequence` from `collections.abc` |
| orch/db/migrations/versions/1fb2eb17b580_add_functional_doc_columns_to_work_items.py | 24 | UP007 | Use `X \| Y` for type annotation |
| orch/db/migrations/versions/1fb2eb17b580_add_functional_doc_columns_to_work_items.py | 25 | UP007 | Use `X \| Y` for type annotation |
| orch/db/migrations/versions/1fb2eb17b580_add_functional_doc_columns_to_work_items.py | 26 | UP007 | Use `X \| Y` for type annotation |
| tests/integration/test_oss_dashboard_templates_extras.py | 429 | PT018 | Assertion should be broken down into multiple parts |
| tests/integration/test_oss_dashboard_templates_extras.py | 479 | PT018 | Assertion should be broken down into multiple parts |

## Observations
- 5 errors are auto-fixable via `ruff check . --fix`
- 3 errors require manual changes (PT018 assertions, T201 print statement)
- All issues are in migration files and test files, not new implementation code
