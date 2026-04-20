# QV Gate Report: F-00056 S13

## Gate
- **Command**: `uv run ruff check .`
- **Description**: QV: Lint (ruff)

## Result: FAIL

## Issues Found
2 lint errors in `dashboard/routers/code_qa.py`:
- Line 106: Unused function argument `module_path`
- Line 107: Unused function argument `module_name`

## Files Changed
None (lint errors only)

## Summary
The lint gate failed due to unused function arguments. The errors must be fixed before this gate can pass.