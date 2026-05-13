# CR-00048 S10 QV Fix Cycle 1/5

Quality gate S10 for work item CR-00048 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00048/ai-dev/active/CR-00048/CR-00048_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: diff-coverage failed: exit=2

**Gate report**:
```
...(truncated)...
_execution_report_creates_file
ERROR tests/integration/test_execution_report_auto_generation.py::TestExecutionReportAutoGeneration::test_hotspots_sorted_by_retry_count_desc
ERROR tests/integration/test_archive.py::test_fts_finds_archived_item - sqlal...
ERROR tests/integration/test_archive.py::test_archive_stores_step_reports - s...
ERROR tests/integration/test_archive.py::test_full_archive_flow - sqlalchemy....
ERROR tests/integration/test_archive.py::test_cli_archive_command - sqlalchem...
ERROR tests/integration/test_archive.py::test_archive_all_completed - sqlalch...
ERROR tests/integration/test_archive.py::test_archive_idempotent - sqlalchemy...
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceIndex::test_index_on_project_work_item_phase
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletion_blocked_when_evidence_exists
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletable_when_no_evidence
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceFKNoCascade::test_work_item_deletable_after_evidence_removed
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceUniqueConstraint::test_duplicate_project_work_item_phase_filename_rejected
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceUniqueConstraint::test_same_filename_different_phase_allowed
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceEnumConstraint::test_invalid_evidence_phase_rejected
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_blob_content_stored_and_retrieved
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_step_id_is_optional
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_insert_and_query_pre_phase
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_step_id_can_be_set
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_multiple_evidences_same_phase_different_filename
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_captured_at_defaults_to_now
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_insert_and_query_post_phase
ERROR tests/integration/test_work_item_evidence.py::TestWorkItemEvidenceInsert::test_multiple_evidences_same_work_item_different_phase
ERROR tests/integration/test_step_monitor_lifecycle.py::test_lifecycle_past_timeout_emits_timeout_not_warn
ERROR tests/integration/test_step_monitor_lifecycle.py::test_full_lifecycle_emits_single_warn_then_idempotent
ERROR tests/integration/test_step_monitor_lifecycle.py::test_lifecycle_below_50pct_emits_no_warn
312 failed, 1370 passed, 33 skipped, 3 xfailed, 978 warnings, 579 errors in 850.79s (0:14:10)
make: *** [Makefile:134: diff-coverage] Error 1
```

## Verdict

```
fail
```

```


## Gate Command

The quality gate that failed runs:
```bash
make diff-coverage
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
