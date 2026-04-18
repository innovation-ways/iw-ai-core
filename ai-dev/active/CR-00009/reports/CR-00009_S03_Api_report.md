# CR-00009 S03 API Report

## What was done

Added `module_name: str | None = None` to `QARequest` in `dashboard/routers/code_qa.py` and threaded it through to `QAEngine.answer_stream`.

Changes:
1. **`QARequest`** (line 43): added `module_name: str | None = None` after `module_path`
2. **`_run_qa_in_thread`** (line 80): added `module_name: str | None` parameter, forwarded to `engine.answer_stream` (line 98)
3. **`_sse_generator`** (line 123): added `module_name: str | None` parameter, forwarded to `_run_qa_in_thread` (line 142)
4. **`code_qa`** (line 203): added `module_name=request.module_name` to `_sse_generator` call

## Files changed

- `dashboard/routers/code_qa.py`

## Test results

- `make test-unit`: **795 passed, 0 failed**
- `uv run ruff check dashboard/routers/code_qa.py`: **All checks passed**
- `uv run mypy dashboard/routers/code_qa.py`: **Success: no issues found**
- `tests/integration/test_code_qa_routes.py`: **8 passed, 0 failed** (all code_qa route tests pass; 8 pre-existing failures in `test_doc_polish.py::TestGlobalSearch` are unrelated to this change)

## TDD note

No inline failing test was added to `test_code_qa_routes.py` in this step. The TDD RED phase is deferred to S07 (tests-impl), which will add a spy-based test verifying `module_name` is forwarded to `QAEngine.answer_stream`. AC7 (backwards compatibility — POST without `module_name` succeeds) is satisfied by the Pydantic default of `None`.

## Issues or observations

None.