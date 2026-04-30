# F-00071 S06 Quality Gate Report

## Gate: lint

**Command**: `make lint`
**Result**: FAIL

## Issues Found

Two lint errors in `dashboard/routers/code_qa.py`:

1. **Line 67**: Unused function argument `dsl` in `render_mermaid()`
2. **Line 70**: Unused function argument `dsl` in `render_d2()`

Both are stub implementations that don't use the `dsl` parameter.

## Fix Required

Remove the unused `dsl` parameter from both stub functions, or prefix with underscore (`_dsl`) if the parameter is intentionally kept for future implementation.