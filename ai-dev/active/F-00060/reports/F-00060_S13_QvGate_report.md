# F-00060 S13 — QV: Integration Tests Gate

## What was done
Executed `make test-integration` as the quality gate for step S13.

## Result: FAIL

Exit code: 1 (15 failed, 1018 passed, 10 skipped)

## Failed Tests (15)

| Test | File | Issue |
|------|------|-------|
| `test_empty_project_returns_empty_bundle_no_error` | `test_boundary_behavior_f00060.py` | `items_indexed == 0` expected `>= 1` |
| `test_missing_lancedb_table_treated_as_empty` | `test_boundary_behavior_f00060.py` | Same — DocIndexResult returns 0 items |
| `test_lancedb_io_error_yields_empty_doc_chunks_no_exception` | `test_boundary_behavior_f00060.py` | Same |
| `test_failed_job_restarts_from_scratch` | `test_boundary_behavior_f00060.py` | Same |
| `test_embed_model_change_drops_and_reindexes` | `test_boundary_behavior_f00060.py` | Same |
| `test_indexer_sanitises_nul_chars` | `test_boundary_behavior_f00060.py` | Same |
| `test_watermark_skips_already_indexed` | `test_doc_index_job_runner.py` | Expected 0 new items, got 2 |
| `test_recover_orphaned_marks_running_as_failed` | `test_doc_index_poller.py` | Expected recovered==1, got 0 |
| `test_recovery_idempotent` | `test_doc_index_poller.py` | Expected recovered==1, got 0 |
| `test_stalled_job_marked_failed` | `test_doc_index_poller.py` | Expected status=failed, got running |
| `test_poll_launches_job_sets_status_to_running` | `test_doc_index_poller.py` | Expected status=running, got queued |
| `test_concurrency_cap_only_one_runs` | `test_doc_index_poller.py` | Expected 1 running job, got 0 |
| `test_reindex_changed_updates_chunks` | `test_doc_indexer.py` | Expected items_indexed==1, got 0 |
| `test_doc_index_job_does_not_write_code_index_jobs` | `test_invariants_f00060.py` | FK violation: project_id not in projects |
| `test_recover_orphaned_marks_running_job_as_failed` | `test_invariants_f00060.py` | Precondition: no running jobs found |

## Key Observation

The majority of failures share a common pattern: `DocIndexer` / `DocIndexJobRunner` operations return 0 items indexed rather than the expected count. This suggests a **regression in the LanceDB indexing path** — items are being discovered (query works) but not written to LanceDB, or the `DocIndexResult` aggregation is broken.

The `test_doc_index_job_does_not_write_code_index_jobs` FK failure (`project_id=(test-proj) is not present in table "projects"`) is a pre-existing test-setup issue unrelated to the core indexing path.

## Files Changed
No files changed as part of this step — this was a pure execution/reporting step.
