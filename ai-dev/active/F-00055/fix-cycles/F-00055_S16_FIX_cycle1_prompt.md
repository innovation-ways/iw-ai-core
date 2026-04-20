# F-00055 S16 QV Fix Cycle 1/5

Quality gate S16 for work item F-00055 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 72 unit tests failed (920 passed). Failures in code_qa_router_citations, code_qa_router_phase, code_qa_router_rerender, f00055_boundaries, qa_engine_hybrid_retrieval, qa_engine_phase_events, qa_engine_render_cache, rag_docs_indexer modules.

**Command output**:
```
...(truncated)...
ngine_render_cache.py::TestRenderCache::test_cache_put_evicts_expired
FAILED tests/unit/test_qa_engine_render_cache.py::TestRenderCacheMaxAndTTL::test_render_cache_max_is_64
FAILED tests/unit/test_qa_engine_render_cache.py::TestRenderCacheMaxAndTTL::test_render_cache_ttl_is_10_minutes
FAILED tests/unit/test_rag_docs_indexer.py::TestIndexDesignDocsFunctionExists::test_function_is_importable
FAILED tests/unit/test_rag_docs_indexer.py::TestIndexDesignDocsChunking::test_chunking_respects_chunk_size
FAILED tests/unit/test_rag_docs_indexer.py::TestIndexDesignDocsChunking::test_single_chunk_when_under_threshold
FAILED tests/unit/test_rag_docs_indexer.py::TestSkipOnNullDesignDoc::test_null_content_not_indexed
FAILED tests/unit/test_rag_docs_indexer.py::TestSummaryOnlyFallback::test_summary_only_item_emits_one_row
FAILED tests/unit/test_rag_docs_indexer.py::TestIncrementalModeFilter::test_incremental_filters_by_updated_at
FAILED tests/unit/test_rag_docs_indexer.py::TestIncrementalModeFilter::test_incremental_uses_merge_insert_not_delete_reinsert
FAILED tests/unit/test_rag_docs_indexer.py::TestMapgenOnlyBypassesDocs::test_mapgen_only_does_not_call_docs_indexer
FAILED tests/unit/test_rag_docs_indexer.py::TestDocIndexResult::test_doc_index_result_fields
FAILED tests/unit/test_rag_docs_indexer.py::TestDocIndexResult::test_doc_index_result_default_errors_empty
FAILED tests/unit/test_rag_docs_indexer.py::TestDocsTableSchema::test_table_name_hyphen_to_underscore
FAILED tests/unit/test_rag_docs_indexer.py::TestProgressEvents::test_emits_indexing_docs_phase
FAILED tests/unit/test_rag_docs_indexer.py::TestEmbeddingModel::test_uses_resolved_embed_model
================= 72 failed, 920 passed, 13 warnings in 12.41s =================
make: *** [Makefile:29: test-unit] Error 1
[0m
**FAIL** - 72 failed, 920 passed
[0m← [0mWrite ai-dev/active/F-00055/reports/F-00055_S16_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00055 --step S16 --reason "72 unit tests failed (920 passed). Failures in code_qa_router_citations, code_qa_router_phase, code_qa_router_rerender, f00055_boundaries, qa_engine_hybrid_retrieval, qa_engine_phase_events, qa_engine_render_cache, rag_docs_indexer modules."
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00055 step S16: 72 unit tests failed (920 passed). Failures in code_qa_router_citations, code_qa_router_phase, code_qa_router_rerender, f00055_boundaries, qa_engine_hybrid_retrieval, qa_engine_phase_events, qa_engine_render_cache, rag_docs_indexer modules.
[0m
**FAIL** - 72 failed, 920 passed.

Failed tests span: `test_code_qa_router_citations`, `test_code_qa_router_phase`, `test_code_qa_router_rerender`, `test_f00055_boundaries`, `test_qa_engine_hybrid_retrieval`, `test_qa_engine_phase_events`, `test_qa_engine_render_cache`, `test_rag_docs_indexer`.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
