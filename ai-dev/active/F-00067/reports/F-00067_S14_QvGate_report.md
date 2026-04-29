# F-00067 S14 QvGate Report: typecheck

## What was done

Ran `make typecheck` (mypy) against the codebase. Initial run failed with 2 errors in `dashboard/routers/code_qa.py`.

## Issue Found

```
dashboard/routers/code_qa.py:67: error: All conditional function variants must have identical signatures
dashboard/routers/code_qa.py:70: error: All conditional function variants must have identical signatures
```

The fallback stub functions `render_mermaid` and `render_d2` (lines 67-71) used parameter name `_dsl` while the real imports in the try block use `dsl`. mypy requires all conditional variants to have identical signatures.

## Fix Applied

Renamed `_dsl` to `dsl` in both stub functions (`code_qa.py:67,70`).

## Test Results

After fix: **PASS** — `Success: no issues found in 197 source files`

## Files Changed

- `dashboard/routers/code_qa.py` — 2 lines (parameter rename in fallback stubs)