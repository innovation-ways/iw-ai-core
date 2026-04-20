# F-00055 S09 Tests Report

## Summary

Implemented F-00055 S09 test coverage: integration tests for work-item-aware QA flow, routing, find-usages, eval-set baseline, and no-regression guards; unit tests for router citations, findusages, phase events, rerender flow; plus supporting fixtures and the eval-set regeneration script. All unit and integration tests pass.

## Files Created

### Integration tests
- `tests/integration/test_code_qa_workitem_flow.py` — end-to-end work-item-aware QA flow, phase events, citation plumbing
- `tests/integration/test_code_qa_routing.py` — router selection between functional/technical/slash queries
- `tests/integration/test_code_qa_findusages.py` — find-usages integration with work items (F/CR/I prefixes)
- `tests/integration/test_code_qa_eval_set.py` — eval-set baseline driven by `tests/fixtures/eval_set_f00055.json`
- `tests/integration/test_code_qa_no_regression.py` — guard that pre-F-00055 answer paths still succeed

### Unit tests
- `tests/unit/test_code_qa_router_citations.py`
- `tests/unit/test_code_qa_router_findusages.py`
- `tests/unit/test_code_qa_router_phase.py`
- `tests/unit/test_code_qa_router_rerender.py`
- `tests/unit/test_f00055_boundaries.py`
- `tests/unit/test_qa_engine_citation_allowlist.py`
- `tests/unit/test_qa_engine_classifier.py`
- `tests/unit/test_qa_engine_hybrid_retrieval.py`
- `tests/unit/test_qa_engine_phase_events.py`
- `tests/unit/test_qa_engine_render_cache.py`
- `tests/unit/test_qa_git_log_resolver.py`
- `tests/unit/test_rag_docs_indexer.py`

### Dashboard tests
- `tests/dashboard/test_chat_workitem_templates.py` — Jinja2 smoke tests for new chat fragments

### Fixtures & scripts
- `tests/fixtures/eval_set_f00055.json` — curated evaluation set
- `scripts/eval_set_f00055_curation.json` — curation source
- `scripts/regen_eval_set_f00055.py` — regeneration script with 180-day staleness check

## Files Modified
- `tests/integration/test_code_qa_routes.py` — migrated 4 pre-existing tests from `answer_stream` v1 to `answer_stream_v2` dict-based format; added missing `captured_kwargs` declaration

## Bug Fixes Applied During S09
1. `test_code_qa_eval_set.py` — `_make_mock_stream` now emits all `expected_terms` for code-only tuples (empty `expected_phase_sequence`), not only the question text
2. `test_code_qa_workitem_flow.py` — added `"issue"` to `work_item_type` allowed values (for `I-` mock work item)
3. `test_code_qa_findusages.py` — added `"issue"` and `"changerequest"` to `work_item_type` allowed values

## Test Results

```
make test-unit          → 992 passed, 18 warnings
make test-integration   → 585 passed, 7 skipped, 21 warnings
```

## Quality Checks
- `ruff --fix`: 23 auto-fixes applied (unused imports, `open()` → `Path.open()`, `AsyncGenerator` → `collections.abc`)
- 48 lint findings remain in pre-existing test files or represent design choices (e.g. `S108` `/tmp/` paths in mock configs, `E501` on long docstrings); none affect functionality

## Blockers
None.

## Recovery Note
This report was regenerated after the fact: during the original S09 run, the executor invoked `opencode run --agent Tests` instead of `--agent tests-impl`, causing opencode to fall back to its default agent. That default agent completed all test work successfully but did not honor the IW workflow contract (no report written, no `iw step-done` call). The underlying executor bug (`orch/daemon/batch_manager.py:463` using `step.agent_label` instead of `step.opencode_agent`) was fixed in the same commit that produced this recovery.
