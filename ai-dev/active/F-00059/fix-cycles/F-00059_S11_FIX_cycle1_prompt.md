# F-00059 S11 QV Fix Cycle 1/5

Quality gate S11 for work item F-00059 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 1 failed + 4 errors in test_f00055_workflow_fixture.py due to e2e_seed production guardrail (IW_CORE_EXPECTED_INSTANCE_ID set without IW_E2E_SEED=1); 964 passed otherwise

**Command output**:
```
...(truncated)...
orktrees/F-00059/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7bf67d6d59d0> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7bf67d502420>
    db_session.flush()

tests/integration/test_project_oss_job_migration.py::TestProjectOssJobFKConstraints::test_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00059/tests/integration/test_project_oss_job_migration.py:224: SAWarning: transaction already deassociated from connection
    transaction.rollback()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_f00055_workflow_fixture.py::test_seed_is_idempotent
ERROR tests/integration/test_f00055_workflow_fixture.py::test_fixture_seeds_18_workflow_steps_for_f00055
ERROR tests/integration/test_f00055_workflow_fixture.py::test_fixture_encodes_correct_retry_counts
ERROR tests/integration/test_f00055_workflow_fixture.py::test_fixture_seeds_fix_cycles_for_retry_steps
ERROR tests/integration/test_f00055_workflow_fixture.py::test_execution_report_returns_expected_hotspots
= 1 failed, 964 passed, 10 skipped, 35 warnings, 4 errors in 156.32s (0:02:36) =
make: *** [Makefile:39: test-integration] Error 1
[0m
**FAIL**

964 passed, 1 failed, 4 errors.

The single failure (`test_seed_is_idempotent`) and 4 errors are all caused by the `e2e_seed` production guardrail triggering in the test environment — `IW_CORE_EXPECTED_INSTANCE_ID` is set but `IW_E2E_SEED` is not. This is an environment configuration issue, not a code defect. All other tests (964) passed cleanly.
[0m$ [0mmkdir -p ai-dev/active/F-00059/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00059/reports/F-00059_S11_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00059 --step S11 --reason "1 failed + 4 errors in test_f00055_workflow_fixture.py due to e2e_seed production guardrail (IW_CORE_EXPECTED_INSTANCE_ID set without IW_E2E_SEED=1); 964 passed otherwise"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00059 step S11: 1 failed + 4 errors in test_f00055_workflow_fixture.py due to e2e_seed production guardrail (IW_CORE_EXPECTED_INSTANCE_ID set without IW_E2E_SEED=1); 964 passed otherwise
[0m
**FAIL** — `make test-integration` returned exit code 1.

**Summary**: 964 passed, 1 failed, 4 errors. All failures are in `test_f00055_workflow_fixture.py` where the `e2e_seed.seed()` production guardrail fires because `IW_CORE_EXPECTED_INSTANCE_ID` is set in the environment without `IW_E2E_SEED=1`. The test tries to patch `get_session` but the guardrail fires before the patch is applied. The remaining 964 tests pass cleanly.

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
