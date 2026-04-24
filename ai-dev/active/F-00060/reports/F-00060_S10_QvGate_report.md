# QV Gate Report: Format (ruff)

## What was done
Ran `uv run ruff format --check .` to check code formatting compliance.

## Files changed
7 files were reformatted:
- `orch/daemon/doc_index_poller.py`
- `tests/integration/test_boundary_behavior_f00060.py`
- `tests/integration/test_doc_index_poller.py`
- `tests/integration/test_invariants_f00060.py`
- `tests/integration/test_qa_v2_code_only_regression.py`
- `tests/unit/test_qa_v2_prompt_layout.py`
- `tests/unit/test_qa_v2_relevance_filter_eval.py`

## Test results
N/A (format check only)

## Issues or observations
Initial check showed 7 files needed reformatting. Applied `uv run ruff format .` to fix. Recheck passed with 339 files already formatted.