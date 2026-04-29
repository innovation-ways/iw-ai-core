# F-00068 S01 Backend Report

## What was done

Added callout syntax and structured-response guidance to `QAEngine.RENDERING_CAPABILITIES_BLOCK` in `orch/rag/qa.py`. The block now instructs the LLM to use GitHub-style `[!NOTE]/[!TIP]/[!WARNING]/[!DANGER]` blockquote callouts and H2 headings + bullet lists for multi-section answers.

This is purely additive — existing Mermaid/D2/table/code lines are unchanged.

## Files changed

- `orch/rag/qa.py` — appended Callouts and Structure sections to `RENDERING_CAPABILITIES_BLOCK` (lines 203–214)
- `tests/unit/test_qa_system_prompt.py` — new test file (3 tests)

## Test results

```
tests/unit/test_qa_system_prompt.py::TestRenderingCapabilitiesBlock::test_rendering_capabilities_block_includes_callouts PASSED
tests/unit/test_qa_system_prompt.py::TestRenderingCapabilitiesBlock::test_rendering_capabilities_block_includes_structure_guidance PASSED
tests/unit/test_qa_system_prompt.py::TestRenderingCapabilitiesBlock::test_system_prompt_includes_capabilities PASSED
3 passed, 0 failed
```

## Pre-flight

- `make format` — ok (only unrelated file `tests/unit/test_code_ui_routes.py` flagged by broader run; changes are quote-style normalization, not from this step)
- `make typecheck` — ok (196 source files, no issues)
- `make lint` — ok for `orch/rag/qa.py` and `tests/unit/test_qa_system_prompt.py`; 2 pre-existing lint errors in `dashboard/routers/code_qa.py` unrelated to this change
- `make test-unit` — 3 passed

## Notes

- The pre-existing lint errors in `dashboard/routers/code_qa.py` (ARG001 unused args) existed before this step and are outside scope
- The broader `make format` run would reformat `test_code_ui_routes.py` (single-quote → double-quote on `<code>` assertions) — this is a pre-existing style drift in that file, not caused by this step