# F-00060 S12 QV Fix Cycle 2/5

Quality gate S12 for work item F-00060 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 1 unit test failed: test_citation_events_emitted_after_reading_docs — LanceDB unavailable causing citation events not to be emitted

**Command output**:
```
...(truncated)...
tests/unit/test_qa_engine.py:723: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
    async for token in engine.answer_stream(
  Enable tracemalloc to get traceback where the object was allocated.
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
FAILED tests/unit/test_qa_engine_phase_events.py::TestPhaseEventSequence::test_citation_events_emitted_after_reading_docs
================= 1 failed, 1410 passed, 27 warnings in 11.53s =================
make: *** [Makefile:36: test-unit] Error 1
[0m
**FAIL** - 1 failed, 1410 passed.

The failing test is `test_citation_events_emitted_after_reading_docs` in `tests/unit/test_qa_engine_phase_events.py:247`. The test expects citation events but none were emitted — likely due to "LanceDB unavailable, skipping retrieval" shown in the logs.
[0m$ [0mmkdir -p ai-dev/active/F-00060/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00060/reports/F-00060_S12_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00060 --step S12 --reason "1 unit test failed: test_citation_events_emitted_after_reading_docs — LanceDB unavailable causing citation events not to be emitted"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00060 step S12: 1 unit test failed: test_citation_events_emitted_after_reading_docs — LanceDB unavailable causing citation events not to be emitted
[0m
**FAIL** — `make test-unit` returned exit code 1.

1 failure: `test_citation_events_emitted_after_reading_docs` (LanceDB unavailable, skipping retrieval — no citation events emitted). Report written and step-fail recorded.

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
