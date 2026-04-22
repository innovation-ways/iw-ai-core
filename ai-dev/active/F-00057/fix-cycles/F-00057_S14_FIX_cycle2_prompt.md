# F-00057 S14 QV Fix Cycle 2/5

Quality gate S14 for work item F-00057 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 6 test failures + 2 setup errors in integration tests; 724 passed

**Command output**:
```
...(truncated)...
e_names():

tests/integration/test_code_sse.py::TestCodeSSEStream::test_sse_returns_idle_when_no_running_job
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00057/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
    warnings.warn(

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00057/tests/integration/test_oss_migration.py:218: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00057/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x72419d3671a0> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x72419d3640b0>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_code_qa_findusages.py::test_findusages_symbol_hint_passed_to_retrieval
FAILED tests/integration/test_code_qa_routes.py::test_qa_streams_tokens - ass...
FAILED tests/integration/test_code_qa_routes.py::test_qa_streams_error_event_on_ollama_down
FAILED tests/integration/test_code_qa_routes.py::test_qa_empty_conversation_history
FAILED tests/integration/test_code_qa_routes.py::test_post_qa_with_module_name_forwards_to_engine
FAILED tests/integration/test_dashboard_pages.py::test_recent_activity_unknown_entity_type_falls_back_to_item_route
ERROR tests/integration/test_oss_persistence.py::TestPersistFindings::test_persist_findings_round_trip
ERROR tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row
== 6 failed, 724 passed, 7 skipped, 25 warnings, 2 errors in 82.94s (0:01:22) ==
make: *** [Makefile:39: test-integration] Error 1
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00057/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00057/reports/F-00057_S14_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00057 --step S14 --reason "6 test failures + 2 setup errors in integration tests; 724 passed"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00057 step S14: 6 test failures + 2 setup errors in integration tests; 724 passed
[0m

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
