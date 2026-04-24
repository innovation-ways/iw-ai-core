# F-00060 S13 QV Fix Cycle 2/5

Quality gate S13 for work item F-00060 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 21 integration tests failed. Root cause: DocIndexer.index_all() returns items_discovered=0 — not finding work items from DB. 19 of 21 failures are in doc indexing subsystem. Also found NUL byte sanitization issue in functional_doc_content field and SQLAlchemy event API issue in invariant tests.

**Command output**:
```
...(truncated)...
cIndexOrphanRecovery::test_recovery_idempotent
FAILED tests/integration/test_doc_index_poller.py::TestDocIndexPollerStallDetection::test_stalled_job_marked_failed
FAILED tests/integration/test_doc_index_poller.py::TestDocIndexPollerLaunch::test_poll_launches_job_sets_status_to_running
FAILED tests/integration/test_doc_index_poller.py::TestDocIndexPollerLaunch::test_concurrency_cap_only_one_runs
FAILED tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_index_three_items_creates_chunks_in_lancedb
FAILED tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
FAILED tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_skip_null_functional_doc_content
FAILED tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
FAILED tests/integration/test_doc_indexer.py::TestDocIndexerReindex::test_watermark_none_indexes_all
FAILED tests/integration/test_invariants_f00060.py::TestInv2NoCodeIndexJobsWrites::test_doc_index_job_does_not_write_code_index_jobs
FAILED tests/integration/test_invariants_f00060.py::TestInv6OrphanRecoveryBeforePoll::test_recover_orphaned_marks_running_job_as_failed
===== 21 failed, 1012 passed, 10 skipped, 70 warnings in 161.55s (0:02:41) =====
make: *** [Makefile:39: test-integration] Error 1
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00060/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00060/reports/F-00060_S13_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00060 --step S13 --reason "21 integration tests failed. Root cause: DocIndexer.index_all() returns items_discovered=0 — not finding work items from DB. 19 of 21 failures are in doc indexing subsystem. Also found NUL byte sanitization issue in functional_doc_content field and SQLAlchemy event API issue in invariant tests."
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00060 step S13: 21 integration tests failed. Root cause: DocIndexer.index_all() returns items_discovered=0 — not finding work items from DB. 19 of 21 failures are in doc indexing subsystem. Also found NUL byte sanitization issue in functional_doc_content field and SQLAlchemy event API issue in invariant tests.
[0m
**FAIL** — `make test-integration` failed with 21 failures.

**Root cause**: `DocIndexer.index_all()` returns `items_discovered=0` — not discovering work items from DB. This causes 19 of the 21 failures in the doc indexing subsystem (runner, poller, indexer tests).

Secondary issues:
- **NUL byte sanitization**: `functional_doc_content` field allows raw `\x00` bytes, violating PostgreSQL's `text` field constraint
- **SQLAlchemy event API**: `db_engine.listen("after_insert", ...)` raises `AttributeError: after_insert`

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


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
