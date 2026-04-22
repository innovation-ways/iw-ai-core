# CR-00015 S11 QV Fix Cycle 1/5

Quality gate S11 for work item CR-00015 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 5 unit tests failed in test_item_report_cli.py - item_report() got an unexpected keyword argument 'archive_dir'

**Command output**:
```
...(truncated)...
urce-warnings for more info.

tests/unit/test_qa_engine_phase_events.py::TestPhaseEventSequence::test_composing_phase_contains_render_id
  /usr/lib/python3.12/unittest/mock.py:2188: RuntimeWarning: coroutine 'TestPhaseEventSequence.test_citation_events_emitted_after_reading_docs.<locals>.mock_classify' was never awaited
    def __init__(self, name, parent):
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/unit/test_qa_engine_render_cache.py::TestRenderCache::test_cache_put_and_get
  /usr/lib/python3.12/unittest/mock.py:2188: RuntimeWarning: coroutine 'TestPhaseEventSequence.test_composing_phase_contains_render_id.<locals>.mock_classify' was never awaited
    def __init__(self, name, parent):
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/unit/test_item_report_cli.py::TestItemReportCli::test_exit_code_0_on_success
FAILED tests/unit/test_item_report_cli.py::TestItemReportCli::test_exit_code_2_on_path_resolution_failure
FAILED tests/unit/test_item_report_cli.py::TestItemReportCli::test_stdout_flag_prints_markdown
FAILED tests/unit/test_item_report_cli.py::TestItemReportCli::test_project_flag_respected
FAILED tests/unit/test_item_report_cli.py::TestItemReportCliNoDiskWrite::test_stdout_does_not_write_file
================= 5 failed, 1177 passed, 18 warnings in 13.78s =================
make: *** [Makefile:36: test-unit] Error 1
[0m
**FAIL** - 5 tests failed due to `item_report()` receiving an unexpected keyword argument `archive_dir`. All 5 failures are in `tests/unit/test_item_report_cli.py` - the test mocks don't match the actual `item_report` command signature.

1177 passed, 5 failed.
[0m$ [0mmkdir -p ai-dev/active/CR-00015/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/CR-00015/reports/CR-00015_S11_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00015 --step S11 --reason "5 unit tests failed in test_item_report_cli.py - item_report() got an unexpected keyword argument 'archive_dir'"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00015 step S11: 5 unit tests failed in test_item_report_cli.py - item_report() got an unexpected keyword argument 'archive_dir'
[0m
**FAIL**

5 unit tests failed in `test_item_report_cli.py` — all with the same error: `item_report() got an unexpected keyword argument 'archive_dir'`. This indicates the CLI command signature has an `archive_dir` parameter that the tests don't provide. 1177 tests passed.

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
