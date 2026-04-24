# F-00060 S12 QV Fix Cycle 3/5

Quality gate S12 for work item F-00060 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 1 test failure: test_code_only_emits_no_phase_events - mock classify_query returns str instead of coroutine

**Command output**:
```
...(truncated)...
 allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_when_module_filter_nonempty
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00060/tests/unit/test_qa_engine.py:819: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    async for token in engine.answer_stream(
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_for_architecture_context
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00060/tests/unit/test_qa_engine.py:905: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    async for token in engine.answer_stream(
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/unit/test_qa_engine_phase_events.py::TestPhaseEventSequence::test_code_only_emits_no_phase_events
================= 1 failed, 1410 passed, 27 warnings in 11.94s =================
make: *** [Makefile:36: test-unit] Error 1
[0m
**FAIL** - 1 test failed: `test_code_only_emits_no_phase_events` in `tests/unit/test_qa_engine_phase_events.py`.

The test has a bug: the `mock_classify` function returns a string `"code_only"` directly, but `classify_query` is called with `await` at `orch/rag/qa.py:518`, so it expects a coroutine. This is a pre-existing test issue.

Exit code: 1
[0m$ [0muv run iw step-fail F-00060 --step S12 --reason "1 test failure: test_code_only_emits_no_phase_events - mock classify_query returns str instead of coroutine"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00060 step S12: 1 test failure: test_code_only_emits_no_phase_events - mock classify_query returns str instead of coroutine
[0m
**FAIL** — Unit tests gate failed.

Exit code: 1 (1 failure out of 1411 tests)

**Failed test**: `tests/unit/test_qa_engine_phase_events.py::TestPhaseEventSequence::test_code_only_emits_no_phase_events`

**Root cause**: The mock `classify_query` is patched to return a plain `str` ("code_only"), but `QAEngine.answer_stream_v2()` calls it with `await classify_query(...)` expecting a coroutine. `TypeError: object str can't be used in 'await' expression`

**Fix needed**: The test's mock function needs to be an `async def` so it can be awaited. See `orch/rag/qa.py:518`.

Reported failure via `iw step-fail`.

```


## Gate Command

The quality gate that failed runs:
```bash
make test-unit
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
