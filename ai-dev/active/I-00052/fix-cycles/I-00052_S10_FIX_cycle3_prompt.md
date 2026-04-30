# I-00052 S10 QV Fix Cycle 3/5

Quality gate S10 for work item I-00052 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Integration test suite timed out after 5 minutes (SIGTERM). 383/386 tests passed, 3 skipped, 2 FTS tests hung at completion. No assertion failures — hang was environmental.

**Command output**:
```
...(truncated)...
t_phase_allowed PASSED [ 98%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletion_blocked_when_evidence_exists PASSED [ 98%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletable_when_no_evidence PASSED [ 98%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletable_after_evidence_removed PASSED [ 99%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceIndex::test_index_on_project_work_item_phase PASSED [ 99%]
tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceEnumConstraint::test_invalid_evidence_phase_rejected PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_insert_populates_search_vector PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_update_functional_doc_content_regenerates_search PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_update_title_regenerates_search PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_gin_index_query_returns_row PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_independence_from_design_doc_search PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_bulk_insert_search_vectors PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_gin_index_used_for_search_query PASSED [ 99%]
tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocMigrationRoundTrip::test_functional_doc_migration_round_trip make: *** [Makefile:48: allure-integration] Error 143


<bash_metadata>
bash tool terminated command after exceeding timeout 300000 ms. If this command is expected to take longer and is not waiting for interactive input, retry with a larger timeout value in milliseconds.
</bash_metadata>
[0m
[0m$ [0mmkdir -p ai-dev/active/I-00052/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/I-00052/reports/I-00052_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail I-00052 --step S10 --reason "Integration test suite timed out after 5 minutes (SIGTERM). 383/386 tests passed, 3 skipped, 2 FTS tests hung at completion. No assertion failures — hang was environmental."
Failed I-00052 step S10: Integration test suite timed out after 5 minutes (SIGTERM). 383/386 tests passed, 3 skipped, 2 FTS tests hung at completion. No assertion failures — hang was environmental.
[0m
**FAIL** — `make allure-integration` timed out after 5 minutes (SIGTERM).

383/386 tests passed, 3 skipped, 2 FTS tests (`test_project_doc_fts_full_text_search`, `test_functional_doc_migration_round_trip`) hung at completion with no assertion failures. Report written to `ai-dev/active/I-00052/reports/I-00052_S10_QvGate_report.md`.

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
