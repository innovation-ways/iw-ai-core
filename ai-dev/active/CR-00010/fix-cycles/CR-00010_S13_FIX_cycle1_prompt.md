# CR-00010 S13 QV Fix Cycle 1/5

Quality gate S13 for work item CR-00010 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 8 integration tests failed in TestGlobalSearch (test_doc_polish.py)

**Command output**:
```
...(truncated)...
information.
    warnings.warn(

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00010/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x74a385d8d0d0> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x74a384308320>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_doc_polish.py::TestGlobalSearch::test_global_search_page_200
FAILED tests/integration/test_doc_polish.py::TestGlobalSearch::test_global_search_returns_cross_project_results
FAILED tests/integration/test_doc_polish.py::TestGlobalSearch::test_global_search_excludes_archived
FAILED tests/integration/test_doc_polish.py::TestGlobalSearch::test_global_search_filter_by_doc_type
FAILED tests/integration/test_doc_polish.py::TestGlobalSearch::test_global_search_snippet_highlighted
FAILED tests/integration/test_doc_polish.py::TestGlobalSearch::test_global_search_empty_results
FAILED tests/integration/test_doc_polish.py::TestGlobalSearch::test_global_search_groups_by_project
FAILED tests/integration/test_doc_polish.py::TestGlobalSearch::test_global_search_empty_query_returns_empty
================= 8 failed, 513 passed, 21 warnings in 36.09s ==================
[0m
[0m$ [0mmake test-integration 2>&1 | tail -5; echo "EXIT_CODE: $?"
FAILED tests/integration/test_doc_polish.py::TestGlobalSearch::test_global_search_empty_results
FAILED tests/integration/test_doc_polish.py::TestGlobalSearch::test_global_search_groups_by_project
FAILED tests/integration/test_doc_polish.py::TestGlobalSearch::test_global_search_empty_query_returns_empty
================= 8 failed, 513 passed, 21 warnings in 33.54s ==================
make: *** [Makefile:32: test-integration] Error 1
EXIT_CODE: 0
[0m
**FAIL** - 8 failed (all `TestGlobalSearch`), 513 passed.

The `make test-integration` command exited with code 1 due to the 8 failing tests in `TestGlobalSearch`.
[0m$ [0mmkdir -p ai-dev/active/CR-00010/reports
[0m
[0m← [0mWrite ai-dev/active/CR-00010/reports/CR-00010_S13_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00010 --step S13 --reason "8 integration tests failed in TestGlobalSearch (test_doc_polish.py)"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00010 step S13: 8 integration tests failed in TestGlobalSearch (test_doc_polish.py)
[0m
**FAIL**

Integration tests: 513 passed, **8 failed** (all `TestGlobalSearch` tests in `test_doc_polish.py`).

Step marked as failed. Report written to `ai-dev/active/CR-00010/reports/CR-00010_S13_QvGate_report.md`.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
