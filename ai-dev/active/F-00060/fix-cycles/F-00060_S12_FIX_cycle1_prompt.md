# F-00060 S12 QV Fix Cycle 1/5

Quality gate S12 for work item F-00060 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 5 unit tests failed: test_top_5_work_items_returned, test_single_source, test_fts_ranks_higher_than_git_log, test_top_5_cap, test_citation_events_emitted_after_reading_docs

**Command output**:
```
...(truncated)...
ts.py::TestPhaseEventSequence::test_citation_events_emitted_after_reading_docs
  /usr/lib/python3.12/unittest/mock.py:2188: RuntimeWarning: coroutine 'TestPhaseEventSequence.test_workitem_aware_emits_correct_phase_sequence.<locals>.mock_classify' was never awaited
    def __init__(self, name, parent):
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/unit/test_qa_engine_render_cache.py::TestRenderCache::test_cache_put_and_get
  /usr/lib/python3.12/unittest/mock.py:767: RuntimeWarning: coroutine 'TestPhaseEventSequence.test_composing_phase_contains_render_id.<locals>.mock_classify' was never awaited
    def __setattr__(self, name, value):
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/unit/test_f00055_boundaries.py::TestBoundaryFeedOverflow::test_top_5_work_items_returned
FAILED tests/unit/test_qa_engine_hybrid_retrieval.py::TestMergeAndRankWorkItems::test_single_source
FAILED tests/unit/test_qa_engine_hybrid_retrieval.py::TestMergeAndRankWorkItems::test_fts_ranks_higher_than_git_log
FAILED tests/unit/test_qa_engine_hybrid_retrieval.py::TestMergeAndRankWorkItems::test_top_5_cap
FAILED tests/unit/test_qa_engine_phase_events.py::TestPhaseEventSequence::test_citation_events_emitted_after_reading_docs
================= 5 failed, 1406 passed, 31 warnings in 16.73s =================
make: *** [Makefile:36: test-unit] Error 1
[0m
**FAIL** - 5 of 1411 unit tests failed. The failing tests are in `test_f00055_boundaries.py`, `test_qa_engine_hybrid_retrieval.py`, and `test_qa_engine_phase_events.py`.
[0m$ [0mmkdir -p ai-dev/active/F-00060/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00060/reports/F-00060_S12_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00060 --step S12 --reason "5 unit tests failed: test_top_5_work_items_returned, test_single_source, test_fts_ranks_higher_than_git_log, test_top_5_cap, test_citation_events_emitted_after_reading_docs"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00060 step S12: 5 unit tests failed: test_top_5_work_items_returned, test_single_source, test_fts_ranks_higher_than_git_log, test_top_5_cap, test_citation_events_emitted_after_reading_docs
[0m
**FAIL** — 5/1411 unit tests failed. The failures are in RAG/QA engine tests (`_merge_and_rank_work_items` boundary tests and citation events tests). Step marked as failed. Report written to `ai-dev/active/F-00060/reports/F-00060_S12_QvGate_report.md`.

```


## Gate Command

The quality gate that failed runs:
```bash
make test-unit
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
