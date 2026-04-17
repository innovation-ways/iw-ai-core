# CR-00006 S08 — Tests Review Report

## Summary

Reviewed 4 new test modules (26 tests total) for coverage, correctness, isolation, and conformance to project testing hard rules. All 4 modules pass.

## Files Reviewed

| File | Tests | Status |
|------|-------|--------|
| `tests/unit/test_code_qa_streaming.py` | 2 | PASS |
| `tests/unit/test_jobs_aggregator.py` | 12 | PASS |
| `tests/unit/test_qa_markdown_sanitize.py` | 6 | PASS |
| `tests/integration/test_jobs_api.py` | 7 | PASS |

## Hard Rules Verification

| Rule | Status |
|------|--------|
| No hardcoded port 5433 or IW_CORE_DB_PORT | PASS |
| Integration tests use testcontainers pattern | PASS |
| No `importlib.reload(orch.config)` | PASS |
| No DB mocking in integration tests | PASS |
| FTS DDL applied after `Base.metadata.create_all()` | PASS |
| psycopg v3 URL replacement applied | PASS |
| `DaemonEvent.event_metadata` used (not `.metadata`) | PASS |

## Checklist Compliance

### test_code_qa_streaming.py
- Non-buffering assertion: time-gap ≥0.3s for 5×100ms tokens — PASS
- `FakeAnswerStream` uses `await asyncio.sleep()` — PASS
- Monkeypatch targets `orch.rag.qa.QAEngine` (matches `dashboard/routers/code_qa.py:62`) — PASS
- Error-path asserts single `event: error` frame with "Local AI unavailable" — PASS
- Uses `@pytest.mark.asyncio` — PASS

### test_jobs_aggregator.py
- Four source types seeded, 4-row union asserted — PASS
- Separate tests for type/status/date filters, pagination, sort, get_job — PASS
- Status normalisation: BatchStatus.executing → "running", DocStatus.published → "completed" — PASS
- Seeds via `db_session.flush()`, fresh session before aggregator — PASS
- Transaction rollback prevents state leaks — PASS

### test_jobs_api.py
- FastAPI app via `create_app()` — PASS
- `get_db` overridden to use testcontainer session — PASS
- 7 test cases cover list, type filter, fragment (no `<html>`), detail, 404, 422, missing project — PASS
- HTML verified by specific ids/strings — PASS
- No real Ollama server — PASS

### test_qa_markdown_sanitize.py
- `test_dompurify_loaded_in_base`: DOMPurify CDN + semver pin — PASS
- `test_qa_panel_uses_dompurify`: `marked.parse` + `DOMPurify.sanitize`, stale textContent path gone, `noopener noreferrer` present — PASS
- `test_qa_panel_user_bubble_uses_text_not_markdown`: `textContent` confirmed, `innerHTML` absent — PASS

## Test Results

```bash
# Unit tests (new modules only)
uv run pytest tests/unit/test_code_qa_streaming.py tests/unit/test_jobs_aggregator.py tests/unit/test_qa_markdown_sanitize.py -v
# 19 passed in 4.63s

# Integration tests (new modules only)
uv run pytest tests/integration/test_jobs_api.py -v
# 7 passed in 5.38s
```

## Pre-existing Failures (Not in Scope)

The `make test-unit` and `make test-integration` runs show 2 and 8 failures respectively — all in unrelated modules (`test_rag_config.py`, `test_code_indexer.py`, `test_doc_polish.py`). These are pre-existing issues not introduced by CR-00006.

## Out of Scope (Deferred)

- DaemonEvent toast rendering (S11 browser verification)
- `code_map_completed` event row insertion (manual verification acceptable)
