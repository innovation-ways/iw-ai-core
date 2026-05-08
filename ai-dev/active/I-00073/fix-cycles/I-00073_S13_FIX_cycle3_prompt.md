# I-00073 S13 QV Fix Cycle 3/5

Quality gate S13 for work item I-00073 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00073/ai-dev/active/I-00073/I-00073_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: integration-tests failed: exit=2

**Gate report**:
```
...(truncated)...
 tests/integration/test_step_monitor_lifecycle.py::test_lifecycle_past_timeout_emits_timeout_not_warn
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_insert_and_query_pre_phase
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_insert_and_query_post_phase
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_blob_content_stored_and_retrieved
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_multiple_evidences_same_work_item_different_phase
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_multiple_evidences_same_phase_different_filename
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_step_id_is_optional
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_step_id_can_be_set
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_captured_at_defaults_to_now
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceUniqueConstraint::test_duplicate_project_work_item_phase_filename_rejected
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceUniqueConstraint::test_same_filename_different_phase_allowed
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletion_blocked_when_evidence_exists
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletable_when_no_evidence
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletable_after_evidence_removed
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceIndex::test_index_on_project_work_item_phase
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceEnumConstraint::test_invalid_evidence_phase_rejected
ERROR tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_insert_populates_search_vector
ERROR tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_update_functional_doc_content_regenerates_search
ERROR tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_update_title_regenerates_search
ERROR tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_gin_index_query_returns_row
ERROR tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_independence_from_design_doc_search
ERROR tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_bulk_insert_search_vectors
ERROR tests/integration/test_work_items_functional_doc_fts.py::TestFunctionalDocFTS::test_gin_index_used_for_search_query
= 341 failed, 1154 passed, 32 skipped, 1 xfailed, 874 warnings, 541 errors in 786.46s (0:13:06) =
make: *** [Makefile:55: test-integration] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make test-integration
```

After applying fixes, re-run this command to verify the issues are resolved.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Skim the section that covers this step's scope; quote-of-the-doc lives in this prompt when available.
2. **Diff your target file(s) against the spec** — list deviations explicitly before editing.
3. **Apply the minimum patch** to align code with the spec; the reported errors should resolve as a side effect of that alignment.
4. **If the errors disagree with the spec, the spec wins.** Note the disagreement in your output rather than silently following the errors.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
