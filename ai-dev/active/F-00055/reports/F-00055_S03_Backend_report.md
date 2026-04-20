# F-00055 S03 Backend Implementation Report

## Summary

Implemented the phase-aware work-item-aware code chat backend for `QAEngine.answer_stream_v2`, including:

1. **Phase event system** - New `answer_stream_v2` method yields dict events (`phase`, `token`, `citation`) for the SSE router
2. **Query classifier** - `_classify_query` routes to workitem_aware or code_only pipeline based on slash overrides or LLM classification
3. **Hybrid retrieval** - Combines code LanceDB, docs LanceDB, Postgres FTS, and git-log resolution
4. **Citation allowlist** - Filters LLM output to only allow cited work-item IDs from the evidence bundle
5. **Render cache** - LRU cache with 10-minute TTL for tone-switch rerendering

## Files Changed/Created

### New Files
- `orch/rag/evidence.py` - `CodeChunk`, `DocChunk`, `EvidenceBundle` dataclasses
- `orch/rag/git_log_resolver.py` - Git log parser for resolving files to work-item IDs
- `orch/rag/classifier.py` - Query classifier with slash override and LLM classification
- `orch/rag/citation_allowlist.py` - Citation filter and validation
- `tests/unit/test_qa_engine_phase_events.py` - Phase event tests
- `tests/unit/test_qa_engine_classifier.py` - Classifier tests
- `tests/unit/test_qa_engine_citation_allowlist.py` - Citation allowlist tests
- `tests/unit/test_qa_git_log_resolver.py` - Git log resolver tests
- `tests/unit/test_qa_engine_hybrid_retrieval.py` - Hybrid retrieval tests
- `tests/unit/test_qa_engine_render_cache.py` - Render cache tests

### Modified Files
- `orch/rag/qa.py` - Added `answer_stream_v2`, `_retrieve_evidence_bundle`, `_build_workitem_system_prompt`, `rerender`, and render cache

## Test Results

```
91 passed, 13 warnings (all passed)
```

All 6 new test files pass with 58 new tests, plus 33 existing QA engine tests pass.

## Key Design Decisions

1. **answer_stream_v2 returns dict events** - Preserves backwards compatibility via the original `answer_stream` method
2. **Citation filtering at sentence boundary** - Buffers tokens until `.`, `!`, `?`, or `\n` before filtering
3. **Git log uses shutil.which** - Finds full path to git binary to satisfy ruff S607 warning
4. **Render cache thread-safe** - Uses `threading.Lock` for concurrent access

## Notes

- The `code_chunks` parameter in `_merge_and_rank_work_items` is unused but kept for API symmetry
- LLM classifier defaults to `code_only` on timeout or error per AC3
- Git log resolver returns empty dict on subprocess errors (file pre-dates convention)
