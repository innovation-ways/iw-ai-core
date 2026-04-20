# F-00055 S05 API Report

## Summary

Implemented the SSE streaming endpoint extensions for the work-item-aware code chat feature:

- Extended `POST /api/projects/{project_id}/code/qa` to forward dict-shaped outputs from `QAEngine.answer_stream_v2` as structured SSE events
- Added `phase` event type to the SSE event catalog
- Extended `citation` event payload with `work_item_type` and `work_item_id` fields
- Added `POST /api/projects/{project_id}/code/qa/rerender` endpoint for tone-switch functionality
- Extended `_CitationTracker` with work-item tracking and validation
- Added `/findusages` symbol hint extraction

## Files Changed

### Modified
- `dashboard/routers/code_qa.py` — Extended SSE generator, added rerender endpoint, extended CitationTracker
- `orch/rag/qa.py` — Added `symbol_hint` parameter to `answer_stream_v2` and `_retrieve_evidence_bundle`, implemented symbol filtering in LanceDB code table search

### Created
- `tests/unit/test_code_qa_router_phase.py` — Tests for phase events and CitationTracker
- `tests/unit/test_code_qa_router_citations.py` — Tests for work-item citation handling
- `tests/unit/test_code_qa_router_findusages.py` — Tests for findusages chip routing
- `tests/unit/test_code_qa_router_rerender.py` — Tests for rerender endpoint

## Test Results

```
uv run pytest tests/unit/test_code_qa_router_phase.py \
  tests/unit/test_code_qa_router_citations.py \
  tests/unit/test_code_qa_router_findusages.py \
  tests/unit/test_code_qa_router_rerender.py -v
```

**42 passed**, 0 failed.

Full unit test suite: **978 passed**, 0 failed.

## Quality Checks

- `uv run ruff check dashboard/routers/code_qa.py orch/rag/qa.py` — **All checks passed**
- `uv run ruff format --check dashboard/routers/code_qa.py orch/rag/qa.py` — **All checks passed**
- `uv run mypy dashboard/routers/code_qa.py` — **Success: no issues found**
- `uv run mypy orch/rag/qa.py` — 18 pre-existing errors (from S03, noted in S04 code review)

## Key Implementation Details

### 1. SSE Event Catalog
```
event: phase    → {"name": "retrieving|finding_items|reading_docs|composing", "detail": {...}}
event: token    → {"b64": "..."}
event: citation → {"n": 1, "label": "...", "url": "...", "snippet": "...",
                  "work_item_type": "feature|incident|change_request",
                  "work_item_id": "F-00042"}
event: done     → {"ok": true}
event: error    → {"message": "..."}
```

### 2. _CitationTracker Extension
- `add_work_item(work_item_id, work_item_type)` — Returns 1-based index or None if duplicate
- Work-item ID validation via regex `^(F|I|CR)-\d{5}$`
- `get_work_item(work_item_id)` — Returns `(work_item_type, work_item_id)` tuple

### 3. /findusages Consolidation
- When `findusages` is in `context_chips`, `symbol_hint` is extracted as `question.strip()`
- Passed to `answer_stream_v2` and forwarded to `_retrieve_evidence_bundle`
- LanceDB code table query filters by `text LIKE '%symbol_hint%'` when provided

### 4. Rerender Endpoint
- `POST /api/projects/{project_id}/code/qa/rerender`
- Request: `{"render_id": "<hex>", "tone": "technical|functional"}`
- Returns HTTP 410 with `{"error": "render_expired"}` on cache miss
- Streams `composing` phase with `rerendered: true` in detail

## Notes

- The `symbol_hint` parameter was added to `answer_stream_v2` and `_retrieve_evidence_bundle` in `orch/rag/qa.py` to support the findusages feature
- The pre-existing mypy errors in `orch/rag/qa.py` (18 errors) were noted in the S04 code review report and are not addressed in this step
- Legacy code-only pipeline (no `context_chips` triggers) continues to work as before - the classifier routes to `answer_stream` which yields strings, and `_sse_generator` handles them via the `isinstance(item, str)` branch
