# F-00060 S13 QV Fix Cycle 1/5

Quality gate S13 for work item F-00060 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 26 integration tests failed. Dominant issues: LanceDB empty data list errors in DocIndexer tests, DocIndexJob status not transitioning to running in poller tests, async classify_query not being awaited in code-only regression tests, and SQLAlchemy event API misuse in invariant test.

**Command output**:
```
...(truncated)...
PollerLaunch::test_concurrency_cap_only_one_runs
FAILED tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_index_three_items_creates_chunks_in_lancedb
FAILED tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_reindex_changed_updates_chunks
FAILED tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_skip_null_functional_doc_content
FAILED tests/integration/test_doc_indexer.py::TestDocIndexerBasic::test_embed_model_change_drops_and_reindexes
FAILED tests/integration/test_doc_indexer.py::TestDocIndexerReindex::test_reindex_none_changed
FAILED tests/integration/test_doc_indexer.py::TestDocIndexerReindex::test_watermark_none_indexes_all
FAILED tests/integration/test_invariants_f00060.py::TestInv2NoCodeIndexJobsWrites::test_doc_index_job_does_not_write_code_index_jobs
FAILED tests/integration/test_invariants_f00060.py::TestInv4CrossProjectIsolation::test_lancedb_table_isolated_to_single_project
FAILED tests/integration/test_invariants_f00060.py::TestInv6OrphanRecoveryBeforePoll::test_recover_orphaned_marks_running_job_as_failed
FAILED tests/integration/test_qa_v2_code_only_regression.py::TestCodeOnlyRegression::test_classifier_routes_signature_question_as_code_only
FAILED tests/integration/test_qa_v2_code_only_regression.py::TestCodeOnlyRegression::test_classifier_routes_how_do_i_use_as_code_only
===== 26 failed, 1007 passed, 10 skipped, 93 warnings in 168.07s (0:02:48) =====
make: *** [Makefile:39: test-integration] Error 1
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00060/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00060/reports/F-00060_S13_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00060 --step S13 --reason "26 integration tests failed. Dominant issues: LanceDB empty data list errors in DocIndexer tests, DocIndexJob status not transitioning to running in poller tests, async classify_query not being awaited in code-only regression tests, and SQLAlchemy event API misuse in invariant test."
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00060 step S13: 26 integration tests failed. Dominant issues: LanceDB empty data list errors in DocIndexer tests, DocIndexJob status not transitioning to running in poller tests, async classify_query not being awaited in code-only regression tests, and SQLAlchemy event API misuse in invariant test.
[0m
**FAIL** — 26 failed, 1007 passed.

The dominant failure patterns are:
- **LanceDB empty `data=[]`** in doc indexer tests (mock embedding not producing usable chunks)
- **DocIndexJob stuck at `queued`** (poller async transitions not completing in tests)
- **`classify_query` is async** but callers aren't awaiting it
- **SQLAlchemy `after_insert` event** registered on `Engine` (invalid API usage)

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
