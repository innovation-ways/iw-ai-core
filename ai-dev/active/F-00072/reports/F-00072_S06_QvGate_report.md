# F-00072 S06 QvGate Report — lint

## What was done
Ran `make lint` quality gate.

## Result
**FAIL** — 2 errors found.

## Issues Found
1. `dashboard/routers/code_qa.py:67` — `render_mermaid(dsl: str)` has unused argument `dsl`
2. `dashboard/routers/code_qa.py:70` — `render_d2(dsl: str)` has unused argument `dsl`

Both functions have placeholder implementations that don't use the `dsl` parameter, triggering ruff's ARG001 (unused function argument) rule.

## Files Changed
None — issues are pre-existing.

## Recommendation
Fix the unused arguments by either:
- Using the `dsl` parameter in the function body
- Prefixing with `_` (e.g., `_dsl`) if intentionally unused
