# F-00070 S06 QvGate Report

## Gate: lint
**Command**: `make lint`
**Result**: PASS

## What was done
Fixed 2 ruff ARG001 violations (unused function arguments `dsl`) in `dashboard/routers/code_qa.py:67` and `dashboard/routers/code_qa.py:70`.

## Files changed
- `dashboard/routers/code_qa.py` — prefixed unused params with `_`

## Notes
The stub functions `render_mermaid` and `render_d2` are fallback implementations when the diagram rendering library is unavailable. The `dsl` parameters are required by the function signatures but are unused in the stub implementations.