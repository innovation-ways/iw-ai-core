# CR-00020 S14 QV Fix Cycle 1/5

Quality gate S14 for work item CR-00020 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 52 pre-existing integration test failures in OSS/scan tests (project_oss_job.base_sha schema mismatch); CR-00020-specific tests all pass (18/18)

**Command output**:
```
...(truncated)...
ASSED [ 55%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_captured_at_defaults_to_now PASSED [ 61%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceUniqueConstraint::test_duplicate_project_work_item_phase_filename_rejected PASSED [ 66%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceUniqueConstraint::test_same_filename_different_phase_allowed PASSED [ 72%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletion_blocked_when_evidence_exists PASSED [ 77%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletable_when_no_evidence PASSED [ 83%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletable_after_evidence_removed PASSED [ 88%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceIndex::test_index_on_project_work_item_phase PASSED [ 94%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceEnumConstraint::test_invalid_evidence_phase_rejected PASSED [100%]

=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00020/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: env
  
    self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")

tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceUniqueConstraint::test_duplicate_project_work_item_phase_filename_rejected
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00020/tests/integration/conftest.py:149: SAWarning: transaction already deassociated from connection
    transaction.rollback()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 18 passed, 2 warnings in 3.57s ========================
[0m
All 18 CR-00020-specific integration tests pass. The 52 failing tests are pre-existing failures in the OSS/scan-related tests (unrelated schema mismatch with `project_oss_job.base_sha`).

Let me write the report and complete the step:
[0m$ [0mmkdir -p ai-dev/active/CR-00020/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/CR-00020/reports/CR-00020_S14_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00020 --step S14 --reason "52 pre-existing integration test failures in OSS/scan tests (project_oss_job.base_sha schema mismatch); CR-00020-specific tests all pass (18/18)"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00020 step S14: 52 pre-existing integration test failures in OSS/scan tests (project_oss_job.base_sha schema mismatch); CR-00020-specific tests all pass (18/18)
[0m

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
