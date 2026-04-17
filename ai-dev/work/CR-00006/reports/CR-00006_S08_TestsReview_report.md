# CR-00006 S08 — Tests Review Report

## Overview

Reviewed four test modules written in S07 (tests-impl) for CR-00006:
- `tests/unit/test_code_qa_streaming.py`
- `tests/unit/test_jobs_aggregator.py`
- `tests/integration/test_jobs_api.py`
- `tests/unit/test_qa_markdown_sanitize.py`

Ran `make test-unit` and `make test-integration` to validate.

## Test Results

### Unit Tests (`make test-unit`)
- **CR-00006 streaming test**: `test_sse_generator_streams_tokens_live` — **FAILS**
- Other failures (unrelated to CR-00006): `test_build_mermaid_contains_graph_td`, `test_default_index_path`
- 773 passed

### Integration Tests (`make test-integration`)
- **CR-00006 jobs API tests**: 5 of 7 fail with **404** — routes don't exist
- Other failures (unrelated to CR-00006): 8 failures in `test_doc_polish.py`
- 498 passed

### Individual Module Results

| Module | Tests | Passed | Failed | Issue |
|--------|-------|--------|--------|-------|
| `test_code_qa_streaming.py` | 2 | 1 | 1 | Streaming buffering bug not fixed |
| `test_jobs_aggregator.py` | 11 | 11 | 0 | — |
| `test_jobs_api.py` | 7 | 2 | 5 | Routes 404 (S03 not implemented) |
| `test_qa_markdown_sanitize.py` | 6 | 6 | 0 | — |

## Hard Rules Compliance

All four test modules comply with testing hard rules:

- **No live DB connection (port 5433)**: All tests use testcontainers on random ports. ✓
- **No `importlib.reload(orch.config)`**: Not used in any CR-00006 test file. ✓
- **Integration tests don't mock DB**: `test_jobs_api.py` uses real testcontainer session. ✓
- **FTS DDL applied after `Base.metadata.create_all()`**: Verified in `test_jobs_aggregator.py` fixtures (lines 54-60). ✓
- **psycopg v3 URL replacement**: Applied in test fixtures. ✓
- **`DaemonEvent.event_metadata`**: Not applicable to these test files (no DaemonEvent testing). ✓

## Critical Findings

### 1. Streaming Test Fails — Buffering Bug Still Present (CRITICAL)

**Test**: `test_sse_generator_streams_tokens_live`

**Failure**:
```
AssertionError: Expected last token >= 0.3s after first, got 0.000s.
This suggests buffering — tokens should arrive incrementally.
```

**Root Cause**: `dashboard/routers/code_qa.py:_sse_generator` (lines 85-124) still uses:
```python
tokens: list[str] = await loop.run_in_executor(
    None,
    _run_qa_in_thread,
    ...
)
```

And `_run_qa_in_thread` (lines 60-82) uses `asyncio.run(collect_tokens())` which collects ALL tokens into a list before returning. Only then does `_sse_generator` yield them — defeating the streaming.

**Expected fix**: S01 backend-impl was supposed to replace this with an `asyncio.Queue`-based non-buffering bridge. The implementation is unchanged from the buggy version.

### 2. Jobs API Tests Fail with 404 — Routes Not Implemented (CRITICAL)

**Test**: `test_jobs_api.py` (5 of 7 tests)

**Failure**: All calls to `/project/{project_id}/jobs`, `/project/{project_id}/jobs/fragment/table`, and `/project/{project_id}/jobs/{job_type}/{job_id}` return HTTP 404.

**Root Cause**: `dashboard/routers/jobs_ui.py` does not exist. The router was not created by S03 (api-impl) and is not registered in `dashboard/app.py`.

The CR-00006 design doc specifies this router should be at `dashboard/routers/jobs_ui.py` with routes:
- `GET /project/{project_id}/jobs`
- `GET /project/{project_id}/jobs/fragment/table`
- `GET /project/{project_id}/jobs/{job_type}/{job_id}`

## What Passed

### `test_jobs_aggregator.py` (11/11 passing)
- Tests four-source union correctly ✓
- Type/status/date filters tested ✓
- Pagination and sort tested ✓
- Status normalization tested (BatchStatus.executing → "running", DocStatus.published → "completed") ✓
- Fresh session pattern used (no uncommitted data leaks) ✓
- No global state leaks between tests (transaction rollback) ✓

### `test_qa_markdown_sanitize.py` (6/6 passing)
- DOMPurify CDN with pinned version verified ✓
- `marked.parse` + `DOMPurify.sanitize` pattern verified ✓
- Stale `textContent +=` path removed verified ✓
- `noopener noreferrer` on links verified ✓
- User bubble uses `textContent` (not `innerHTML`) verified ✓

## Recommendations

1. **Fix streaming implementation** (`dashboard/routers/code_qa.py`): Replace the `run_in_executor` + `asyncio.run(collect_tokens())` pattern with an `asyncio.Queue`-based approach where tokens are put into the queue as they arrive, not collected into a list.

2. **Implement jobs UI router**: Create `dashboard/routers/jobs_ui.py` with the three routes and register in `app.py`.

## Signal

Step S08 cannot be marked complete. The tests correctly identify that:
- The streaming bug fix from S01 is not present in the implementation
- The API routes from S03 are not implemented

The tests themselves are well-written and correctly written — they accurately identify missing/broken implementation. No issues with the test code itself.
