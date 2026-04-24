# I-00037 S11 QV Fix Cycle 1/5

Quality gate S11 for work item I-00037 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 3 test failures in test_scope_gate.py: executor/scope_gate.py writes violations to stderr but tests assert on stdout

**Command output**:
```
...(truncated)...
qa_engine_phase_events.py::TestPhaseEventSequence::test_composing_phase_contains_render_id
  /usr/lib/python3.12/inspect.py:265: RuntimeWarning: coroutine 'TestPhaseEventSequence.test_citation_events_emitted_after_reading_docs.<locals>.mock_classify' was never awaited
    return dict(ann)
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/unit/test_qa_engine_render_cache.py::TestRenderCache::test_cache_put_and_get
  /usr/lib/python3.12/unittest/mock.py:2188: RuntimeWarning: coroutine 'TestPhaseEventSequence.test_composing_phase_contains_render_id.<locals>.mock_classify' was never awaited
    def __init__(self, name, parent):
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/unit/executor/test_scope_gate.py::TestExactPath::test_exact_path_mismatch_flags_as_violation
FAILED tests/unit/executor/test_scope_gate.py::TestDirStarStar::test_dir_double_star_blocks_siblings
FAILED tests/unit/executor/test_scope_gate.py::TestViolationListing::test_violation_listing_preserves_input_order
================= 3 failed, 1392 passed, 19 warnings in 16.20s =================
make: *** [Makefile:36: test-unit] Error 1
[0m
**FAIL** - 3 failures in `tests/unit/executor/test_scope_gate.py`. The tests expect violations in `stdout`, but `executor/scope_gate.py` writes them to `stderr`.

Let me write the report and mark the step as failed.
[0m$ [0mmkdir -p ai-dev/active/I-00037/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/I-00037/reports/I-00037_S11_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail I-00037 --step S11 --reason "3 test failures in test_scope_gate.py: executor/scope_gate.py writes violations to stderr but tests assert on stdout"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed I-00037 step S11: 3 test failures in test_scope_gate.py: executor/scope_gate.py writes violations to stderr but tests assert on stdout
[0m
**FAIL** — `make test-unit` returned exit code 1.

3 failures in `tests/unit/executor/test_scope_gate.py`:
- `test_exact_path_mismatch_flags_as_violation`
- `test_dir_double_star_blocks_siblings`  
- `test_violation_listing_preserves_input_order`

**Root cause**: `executor/scope_gate.py` outputs violations to `stderr` but the tests check `stdout`. The scope gate logic itself works correctly (exit code 1 on violations is proper) — only the output stream is wrong.

Report written to `ai-dev/active/I-00037/reports/I-00037_S11_QvGate_report.md`.

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
