# CR-00015 S12 QV Fix Cycle 1/5

Quality gate S12 for work item CR-00015 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 2 integration tests failed: test_claude_md_references_policy (CLAUDE.md missing IW_AI_Core_Agent_Constraints link) and test_history_returns_paginated_items (server-side pagination shows page 2 item on page 1 assertion)

**Command output**:
```
...(truncated)...
/starlette/issues/1108 for more information.
    warnings.warn(

tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_finding_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_tool_run_fk_invalid_scan_id
tests/integration/test_oss_migration.py::TestOssFKConstraints::test_oss_scan_fk_invalid_project_id
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00015/tests/integration/test_oss_migration.py:218: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00015/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7abacb7cbef0> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7abacbc918e0>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_agent_constraints_coverage.py::test_claude_md_references_policy[CLAUDE.md]
FAILED tests/integration/test_dashboard_remaining.py::test_history_returns_paginated_items
======= 2 failed, 764 passed, 7 skipped, 25 warnings in 95.21s (0:01:35) =======
make: *** [Makefile:39: test-integration] Error 1
[0m
**FAIL** — 2 failed, 764 passed, 7 skipped.

Failed tests:
1. `test_claude_md_references_policy[CLAUDE.md]` — CLAUDE.md missing `IW_AI_Core_Agent_Constraints` reference
2. `test_history_returns_paginated_items` — "I-00025" not in history response (pagination issue)
[0m$ [0mmkdir -p ai-dev/active/CR-00015/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/CR-00015/reports/CR-00015_S12_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00015 --step S12 --reason "2 integration tests failed: test_claude_md_references_policy (CLAUDE.md missing IW_AI_Core_Agent_Constraints link) and test_history_returns_paginated_items (server-side pagination shows page 2 item on page 1 assertion)"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00015 step S12: 2 integration tests failed: test_claude_md_references_policy (CLAUDE.md missing IW_AI_Core_Agent_Constraints link) and test_history_returns_paginated_items (server-side pagination shows page 2 item on page 1 assertion)
[0m
**FAIL** — 2 integration tests failed:

1. `test_claude_md_references_policy[CLAUDE.md]` — CLAUDE.md missing `IW_AI_Core_Agent_Constraints` reference
2. `test_history_returns_paginated_items` — pagination logic issue (I-00025 on page 2, not page 1)

Report written to `ai-dev/active/CR-00015/reports/CR-00015_S12_QvGate_report.md`. Step marked as failed.

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
