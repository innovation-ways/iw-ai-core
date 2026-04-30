# F-00072 S10 QV Fix Cycle 4/5

Quality gate S10 for work item F-00072 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: integration-tests gate failed: 1 pre-existing test failure (test_project_doc_fts_full_text_search) — plainto_tsquery('API') returns all 3 docs instead of 1 due to English stemming on acronym

**Command output**:
```
...(truncated)...
on.rollback()

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00072/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x72264101eb10> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x72264101da60>
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
FAILED tests/integration/test_project_docs.py::test_project_doc_fts_full_text_search
===== 1 failed, 1160 passed, 11 skipped, 154 warnings in 279.87s (0:04:39) =====
make: *** [Makefile:48: allure-integration] Error 1
[0m
**FAIL**

Exit code 1. 1 failed (`test_project_doc_fts_full_text_search`), 1160 passed, 11 skipped.

The failing test queries for `'API'` using `plainto_tsquery` and expects exactly 1 result (`module-auth`), but gets 3 results (all docs contain 'API' in their content). This appears to be a pre-existing test issue — the FTS query is matching words containing 'API' as substrings across all three documents.
[0m$ [0mmkdir -p ai-dev/active/F-00072/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00072/reports/F-00072_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00072 --step S10 --reason "integration-tests gate failed: 1 pre-existing test failure (test_project_doc_fts_full_text_search) — plainto_tsquery('API') returns all 3 docs instead of 1 due to English stemming on acronym"
Failed F-00072 step S10: integration-tests gate failed: 1 pre-existing test failure (test_project_doc_fts_full_text_search) — plainto_tsquery('API') returns all 3 docs instead of 1 due to English stemming on acronym
[0m
**FAIL** — `make allure-integration` returned exit code 1.

**1160 passed, 1 failed, 11 skipped.** The single failure is `test_project_doc_fts_full_text_search`, a pre-existing issue where `plainto_tsquery('english', 'API')` English stemming matches all 3 documents containing "API"-rooted tokens rather than just the exact acronym. Report written to `ai-dev/active/F-00072/reports/F-00072_S10_QvGate_report.md`.

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
