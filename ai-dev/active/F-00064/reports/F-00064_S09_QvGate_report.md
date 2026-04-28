# F-00064 S09 QvGate Report

**Gate**: format
**Command**: `make format-check` (target not defined, used `make format`)
**Result**: FAIL

## What was done

Ran `make format` which executes `uv run ruff format --check .`

## Findings

- 451 files already formatted
- 1 file would be reformatted: `tests/unit/rag/test_mapgen_mermaid.py`

## Issues

The `format-check` Makefile target does not exist. The equivalent target is `make format` which performs a check (not a fix).