# F-00057 S14 QV Fix Cycle 1/5

Quality gate S14 for work item F-00057 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 11 tests failed, 2 errors in integration tests. Root causes: oss_scan table not registered in Base.metadata (fixture setup error), F-00055 seed produces 0 steps (expected 18), code QA SSE streaming returns 0 token events.

**Command output**:
```
...(truncated)...
_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_code_qa_findusages.py::test_findusages_symbol_hint_passed_to_retrieval
FAILED tests/integration/test_code_qa_routes.py::test_qa_streams_tokens - ass...
FAILED tests/integration/test_code_qa_routes.py::test_qa_streams_error_event_on_ollama_down
FAILED tests/integration/test_code_qa_routes.py::test_qa_empty_conversation_history
FAILED tests/integration/test_code_qa_routes.py::test_post_qa_with_module_name_forwards_to_engine
FAILED tests/integration/test_dashboard_pages.py::test_recent_activity_unknown_entity_type_falls_back_to_item_route
FAILED tests/integration/test_f00055_workflow_fixture.py::test_fixture_seeds_18_workflow_steps_for_f00055
FAILED tests/integration/test_f00055_workflow_fixture.py::test_fixture_encodes_correct_retry_counts
FAILED tests/integration/test_f00055_workflow_fixture.py::test_fixture_seeds_fix_cycles_for_retry_steps
FAILED tests/integration/test_f00055_workflow_fixture.py::test_execution_report_returns_expected_hotspots
FAILED tests/integration/test_f00055_workflow_fixture.py::test_seed_is_idempotent
ERROR tests/integration/test_oss_persistence.py::TestPersistFindings::test_persist_findings_round_trip
ERROR tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row
= 11 failed, 719 passed, 7 skipped, 25 warnings, 2 errors in 85.72s (0:01:25) ==
make: *** [Makefile:39: test-integration] Error 1
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00057/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00057/reports/F-00057_S14_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00057 --step S14 --reason "11 tests failed, 2 errors in integration tests. Root causes: oss_scan table not registered in Base.metadata (fixture setup error), F-00055 seed produces 0 steps (expected 18), code QA SSE streaming returns 0 token events."
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00057 step S14: 11 tests failed, 2 errors in integration tests. Root causes: oss_scan table not registered in Base.metadata (fixture setup error), F-00055 seed produces 0 steps (expected 18), code QA SSE streaming returns 0 token events.
[0m
**FAIL** — `make test-integration` returned exit code 1.

Results: **11 failed, 2 errors, 719 passed, 7 skipped**

Key failure clusters:
- **OSS fixture error**: `KeyError: 'oss_scan'` — OSS tables not registered in `Base.metadata` at test setup
- **F-00055 seed**: `+ 0 per-item fixture(s)` — seed produces 0 steps (expected 18)  
- **Code QA SSE**: 0 token events returned (mocked `answer_stream` not being called correctly)

Report written to `ai-dev/active/F-00057/reports/F-00057_S14_QvGate_report.md`.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
