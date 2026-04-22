# CR-00016 S12 QV Fix Cycle 2/5

Quality gate S12 for work item CR-00016 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Integration test suite failed: 1/751 tests failed - test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row - RuntimeError: Event loop is closed (pre-existing asyncio infrastructure issue, not CR-00016 related)

**Command output**:
```
...(truncated)...
test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00016/tests/integration/test_oss_migration.py:218: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00016/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7db5e2038c80> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7db5527ffd70>
    db_session.flush()

tests/integration/test_project_docs.py::test_project_doc_fts_full_text_search
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00016/.venv/lib/python3.12/site-packages/sqlalchemy/sql/visitors.py:134: RuntimeWarning: coroutine 'run_scan' was never awaited
    meth = getter(visitor)
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row
======= 1 failed, 750 passed, 7 skipped, 31 warnings in 82.96s (0:01:22) =======
make: *** [Makefile:39: test-integration] Error 1
[0m
[0m$ [0mmkdir -p ai-dev/active/CR-00016/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/CR-00016/reports/CR-00016_S12_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00016 --step S12 --reason "Integration test suite failed: 1/751 tests failed - test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row - RuntimeError: Event loop is closed (pre-existing asyncio infrastructure issue, not CR-00016 related)"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00016 step S12: Integration test suite failed: 1/751 tests failed - test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row - RuntimeError: Event loop is closed (pre-existing asyncio infrastructure issue, not CR-00016 related)
[0m
**FAIL** — 1 failed, 750 passed, 7 skipped.

The single failure (`test_run_scan_creates_oss_scan_row`) is a pre-existing asyncio event loop bug in the OSS scanner test infrastructure, unrelated to CR-00016 changes.

Report written to `ai-dev/active/CR-00016/reports/CR-00016_S12_QvGate_report.md`.

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
