# F-00072 S10 QV Fix Cycle 1/5

Quality gate S10 for work item F-00072 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 3 integration tests failed: test_ac3_baselines_created_at_setup, test_baseline_empty_passing_gate_persists_sentinel_row, test_project_doc_fts_full_text_search (1158 passed, 11 skipped)

**Command output**:
```
...(truncated)...
oject_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00072/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7c6e809cbc50> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7c6e809c8920>
    db_session.flush()

tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00072/tests/integration/test_project_oss_job_migration.py:244: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_step_monitor_lifecycle.py::test_full_lifecycle_emits_single_warn_then_idempotent
  /usr/lib/python3.12/weakref.py:454: RuntimeWarning: coroutine 'sleep' was never awaited
    def __contains__(self, key):
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/daemon/test_baseline_qv_pipeline.py::TestAC3::test_ac3_baselines_created_at_setup
FAILED tests/integration/daemon/test_baseline_qv_pipeline.py::TestBaselineBoundary::test_baseline_empty_passing_gate_persists_sentinel_row
FAILED tests/integration/test_project_docs.py::test_project_doc_fts_full_text_search
===== 3 failed, 1158 passed, 11 skipped, 154 warnings in 286.63s (0:04:46) =====
make: *** [Makefile:48: allure-integration] Error 1
EXIT_CODE: 0
[0m
**FAIL** — 3 tests failed, 1158 passed, 11 skipped.

Failing tests:
1. `TestAC3::test_ac3_baselines_created_at_setup`
2. `TestBaselineBoundary::test_baseline_empty_passing_gate_persists_sentinel_row`
3. `test_project_doc_fts_full_text_search`
[0m$ [0mmkdir -p ai-dev/active/F-00072/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00072/reports/F-00072_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00072 --step S10 --reason "3 integration tests failed: test_ac3_baselines_created_at_setup, test_baseline_empty_passing_gate_persists_sentinel_row, test_project_doc_fts_full_text_search (1158 passed, 11 skipped)"
Failed F-00072 step S10: 3 integration tests failed: test_ac3_baselines_created_at_setup, test_baseline_empty_passing_gate_persists_sentinel_row, test_project_doc_fts_full_text_search (1158 passed, 11 skipped)
[0m
**FAIL** — `make allure-integration` completed with 3 failures:

- `TestAC3::test_ac3_baselines_created_at_setup`
- `TestBaselineBoundary::test_baseline_empty_passing_gate_persists_sentinel_row`
- `test_project_doc_fts_full_text_search`

(1158 passed, 11 skipped, 154 warnings, ~4m46s)

Report written to `ai-dev/active/F-00072/reports/F-00072_S10_QvGate_report.md` and step marked as failed.

```


## Gate Command

The quality gate that failed runs:
```bash
make allure-integration
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
