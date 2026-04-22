# CR-00016 S12 QV Fix Cycle 1/5

Quality gate S12 for work item CR-00016 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 2 integration test errors: KeyError 'oss_scan' in oss_engine fixture for test_oss_persistence.py and test_oss_scanner.py - pre-existing OSS table registration issue

**Command output**:
```
...(truncated)...
client.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
    warnings.warn(

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00016/tests/integration/test_oss_migration.py:218: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00016/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7a1636048b60> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7a1636048dd0>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/integration/test_oss_persistence.py::TestPersistFindings::test_persist_findings_round_trip
ERROR tests/integration/test_oss_scanner.py::TestOssScannerRunScan::test_run_scan_creates_oss_scan_row
======= 749 passed, 7 skipped, 30 warnings, 2 errors in 84.00s (0:01:23) =======
make: *** [Makefile:39: test-integration] Error 1
[0m
**FAIL** - 749 passed, 7 skipped, 30 warnings, **2 errors**

Both errors are `KeyError: 'oss_scan'` in OSS-specific test fixtures (`test_oss_persistence.py:122` and `test_oss_scanner.py:123`) — the `oss_scan` table is not registered in `Base.metadata` at test setup time. These appear to be pre-existing infrastructure issues unrelated to CR-00016.

Let me mark the step as failed:
[0m$ [0muv run iw step-fail CR-00016 --step S12 --reason "2 integration test errors: KeyError 'oss_scan' in oss_engine fixture for test_oss_persistence.py and test_oss_scanner.py - pre-existing OSS table registration issue"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00016 step S12: 2 integration test errors: KeyError 'oss_scan' in oss_engine fixture for test_oss_persistence.py and test_oss_scanner.py - pre-existing OSS table registration issue
[0m
**FAIL** — 749 passed, 7 skipped, 30 warnings, **2 errors**

Errors in `test_oss_persistence.py` and `test_oss_scanner.py`: both have a session-scoped `oss_engine` fixture that fails at setup with `KeyError: 'oss_scan'` — the OSS tables aren't registered in `Base.metadata` at the time the fixture runs. This is a pre-existing test infrastructure issue unrelated to CR-00016 changes.

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
