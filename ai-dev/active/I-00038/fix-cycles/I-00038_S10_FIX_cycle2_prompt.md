# I-00038 S10 QV Fix Cycle 2/5

Quality gate S10 for work item I-00038 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: test_item_detail_has_sse_script expects 'EventSource' but page uses iwSSE wrapper

**Command output**:
```
...(truncated)...
ormation.
    warnings.warn(

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00038/tests/integration/test_oss_migration.py:230: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00038/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7857e9716630> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x785765bf7680>
    db_session.flush()

tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00038/tests/integration/test_project_oss_job_migration.py:229: SAWarning: transaction already deassociated from connection
    transaction.rollback()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_dashboard_pages.py::test_item_detail_has_sse_script
====== 1 failed, 969 passed, 10 skipped, 35 warnings in 157.68s (0:02:37) ======
make: *** [Makefile:39: test-integration] Error 1
[0m
The test failed. Let me investigate the failing test to understand the issue:
[0m✱ [0mGrep "test_item_detail_has_sse_script"[90m 1 match[0m
[0m→ [0mRead tests/integration/test_dashboard_pages.py[90m [offset=605, limit=30][0m
The test `test_item_detail_has_sse_script` expects `EventSource` in the response but the page uses an `iwSSE` wrapper instead. This appears to be a test that wasn't updated when the SSE implementation changed.
[0m
[0m$ [0mmkdir -p ai-dev/active/I-00038/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/I-00038/reports/I-00038_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail I-00038 --step S10 --reason "test_item_detail_has_sse_script expects 'EventSource' but page uses iwSSE wrapper"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed I-00038 step S10: test_item_detail_has_sse_script expects 'EventSource' but page uses iwSSE wrapper
[0m
**FAIL** — 969 passed, 1 failed, 10 skipped.

The failing test `test_item_detail_has_sse_script` expects the literal string `EventSource` but the item detail page uses an `iwSSE` JavaScript wrapper. Report written to `ai-dev/active/I-00038/reports/I-00038_S10_QvGate_report.md`.

```


## Gate Command

The quality gate that failed runs:
```bash
make test-integration
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
