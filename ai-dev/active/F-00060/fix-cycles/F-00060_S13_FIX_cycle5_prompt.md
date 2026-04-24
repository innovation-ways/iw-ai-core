# F-00060 S13 QV Fix Cycle 5/5

Quality gate S13 for work item F-00060 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 16 integration tests failed in doc indexing subsystem (DocIndexer, DocIndexJobRunner, DocIndexPoller) and invariant tests. Core functionality (1017 passing) is intact. See report for details.

**Command output**:
```
...(truncated)...
r_f00060.py::TestBoundaryLanceDBIOError::test_lancedb_io_error_yields_empty_doc_chunks_no_exception
FAILED tests/integration/test_boundary_behavior_f00060.py::TestBoundaryReindexAfterPartialFailure::test_failed_job_restarts_from_scratch
FAILED tests/integration/test_boundary_behavior_f00060.py::TestBoundaryEmbedModelChange::test_embed_model_change_drops_and_reindexes
FAILED tests/integration/test_boundary_behavior_f00060.py::TestBoundaryFunctionalDocWithNULChars::test_indexer_sanitises_nul_chars
FAILED tests/integration/test_doc_index_job_runner.py::TestDocIndexJobRunnerBasic::test_error_on_missing_embed_model
FAILED tests/integration/test_doc_index_job_runner.py::TestDocIndexJobRunnerWatermark::test_watermark_skips_already_indexed
FAILED tests/integration/test_doc_index_poller.py::TestDocIndexOrphanRecovery::test_recover_orphaned_marks_running_as_failed
FAILED tests/integration/test_doc_index_poller.py::TestDocIndexOrphanRecovery::test_recovery_idempotent
FAILED tests/integration/test_doc_index_poller.py::TestDocIndexPollerStallDetection::test_stalled_job_marked_failed
FAILED tests/integration/test_doc_index_poller.py::TestDocIndexPollerLaunch::test_poll_launches_job_sets_status_to_running
FAILED tests/integration/test_doc_index_poller.py::TestDocIndexPollerLaunch::test_concurrency_cap_only_one_runs
FAILED tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
FAILED tests/integration/test_invariants_f00060.py::TestInv2NoCodeIndexJobsWrites::test_doc_index_job_does_not_write_code_index_jobs
FAILED tests/integration/test_invariants_f00060.py::TestInv6OrphanRecoveryBeforePoll::test_recover_orphaned_marks_running_job_as_failed
==== 16 failed, 1017 passed, 10 skipped, 112 warnings in 169.10s (0:02:49) =====
make: *** [Makefile:39: test-integration] Error 1
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00060/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00060/reports/F-00060_S13_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00060 --step S13 --reason "16 integration tests failed in doc indexing subsystem (DocIndexer, DocIndexJobRunner, DocIndexPoller) and invariant tests. Core functionality (1017 passing) is intact. See report for details."
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00060 step S13: 16 integration tests failed in doc indexing subsystem (DocIndexer, DocIndexJobRunner, DocIndexPoller) and invariant tests. Core functionality (1017 passing) is intact. See report for details.
[0m
**FAIL** — 16/1033 integration tests failed.

The failures are all in the doc indexing subsystem (DocIndexer, DocIndexJobRunner, DocIndexPoller) and related invariant tests. Core work-item/batch/daemon functionality is fine (1017 passing).

Report written to `ai-dev/active/F-00060/reports/F-00060_S13_QvGate_report.md`.

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


**ESCALATION**: This is the FINAL fix cycle (5/5). If you cannot resolve all issues, clearly document which remain and why.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
