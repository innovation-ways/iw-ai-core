# I-00052 S10 QV Fix Cycle 2/5

Quality gate S10 for work item I-00052 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: make allure-integration timed out after 300s (exit 143) at test_worktree_reaper_real_containers.py

**Command output**:
```
...(truncated)...
FTS::test_update_title_regenerates_search PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_gin_index_query_returns_row PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_independence_from_design_doc_search PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_bulk_insert_search_vectors PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_gin_index_used_for_search_query PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocMigrationRoundTrip::test_functional_doc_migration_round_trip PASSED [ 99%]
tests/integration/test_worktree_reaper_real_containers.py::test_reaper_classifies_and_reaps_orphan make: *** [Makefile:48: allure-integration] Error 143


<bash_metadata>
bash tool terminated command after exceeding timeout 300000 ms. If this command is expected to take longer and is not waiting for interactive input, retry with a larger timeout value in milliseconds.
</bash_metadata>
[0m
[0m$ [0mls -la allures/ 2>/dev/null || echo "No allures dir"
No allures dir
[0m
[0m$ [0mmkdir -p ai-dev/active/I-00052/reports && cat > ai-dev/active/I-00052/reports/I-00052_S10_QvGate_report.md << 'EOF'
# S10 Quality Gate Report — integration-tests

**Gate**: `make allure-integration`
**Result**: FAIL (timeout)

## What was done
Ran `make allure-integration` to execute the full integration test suite with Allure reporting.

## Output Summary
- Exit code: 143 (SIGTERM — command timed out after 300s)
- 99% of tests passed (460+ tests passed, 1 skipped)
- The test run was terminated at `tests/integration/test_worktree_reaper_real_containers.py::test_reaper_classifies_and_reaps_orphan`

## Failure Reason
The `test_worktree_reaper_real_containers.py` test uses real containers and appears to hang, causing the entire `make allure-integration` target to exceed the 300s timeout.

## Files Changed
None — this was a test execution gate only.

## Observations
- All other integration tests passed (including OSS boundary tests, job aggregation, project docs, RAG, migrations, etc.)
- The worktree reaper container test is the only hanging test
- The gate failed due to timeout, not a test assertion failure
EOF
(no output)
[0m
[0m$ [0muv run iw step-fail I-00052 --step S10 --reason "make allure-integration timed out after 300s (exit 143) at test_worktree_reaper_real_containers.py"
Failed I-00052 step S10: make allure-integration timed out after 300s (exit 143) at test_worktree_reaper_real_containers.py
[0m
**FAIL** — `make allure-integration` timed out after 300s (exit 143).

The test `test_worktree_reaper_real_containers.py::test_reaper_classifies_and_reaps_orphan` uses real containers and appears to hang, causing the entire suite to exceed the timeout. All other ~460+ tests passed. Report written to `ai-dev/active/I-00052/reports/I-00052_S10_QvGate_report.md`.

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
