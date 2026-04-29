# QV Gate Report: S10 — typecheck

## What was done
Ran `make typecheck` (mypy) on the codebase.

## Files changed
- `dashboard/routers/code_qa.py` — Fixed parameter name mismatch in fallback stubs for `render_mermaid` and `render_d2`. Changed `_dsl` → `dsl` to match the real implementation signatures.

## Result
**PASS** — No mypy errors found (196 source files checked).

## Issue resolved
Mypy requires all conditional function variants to have identical signatures. The fallback stubs used `_dsl` but the real implementations in `orch/diagram/render.py` use `dsl`.
