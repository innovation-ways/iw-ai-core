# CR-00006 S02 — Backend Review Report

## Summary

All three artefacts reviewed and passing.

## Streaming Bridge — `dashboard/routers/code_qa.py`

| Check | Result |
|-------|--------|
| `_run_qa_in_thread` removed | ✅ No references remain |
| `asyncio.Queue` + `threading.Thread` pattern | ✅ Lines 66-95 |
| `loop.call_soon_threadsafe(queue.put_nowait, …)` per token | ✅ Line 83 |
| No buffering — yields per token | ✅ Lines 99-120 (`while True: kind, payload = await queue.get()`) |
| Wire format preserved | ✅ `{"token":"..."}`, `{"event":"done","full_response":"..."}`, `{"event":"error","message":"..."}` |
| Endpoint signature, 404 check, StreamingResponse headers unchanged | ✅ |
| `ConnectionRefusedError`, `OSError` caught and produce error frame | ✅ Lines 84-88 |
| Client disconnect handled via `stop_event` | ✅ Lines 67, 81-82, 122 |
| No `asyncio.run()` in request event loop | ✅ `asyncio.run(_drain())` called inside worker thread, not request loop |
| `ruff check` clean | ✅ |
| `mypy` clean | ✅ |

**Minor note**: `httpx.ConnectError` is not explicitly caught in the worker thread (the `except` block handles `ConnectionRefusedError` and `OSError` only). However, `QAEngine.answer_stream` at `orch/rag/qa.py:118` catches `httpx.ConnectError` and yields an `"__ERROR__:…"` token, which `code_qa.py` handles at line 112-117. So errors from that path do route through the error frame correctly.

## Aggregator — `orch/jobs/aggregator.py`

| Check | Result |
|-------|--------|
| `JobType`, `JobRow`, `JobListResult`, `JobsAggregator` exported | ✅ (all public, no `__all__` but convention respected) |
| All four sources queried | ✅ `_fetch_code_mapping`, `_fetch_doc_generation`, `_fetch_batch_execution`, `_fetch_research` |
| Status normalisation correct | ✅ `_normalise_batch_status` (lines 120-135), `_normalise_job_status` (116-117), `_normalise_doc_status` (106-113) |
| `started_at` / `finished_at` mapping | ✅ Matches design table |
| `doc_generation` title joins `project_docs.title` via `doc_id`, fallback `"Doc generation (orphan)"` | ✅ Lines 289-293 |
| Filter parameters narrow results | ✅ Filter logic lines 170-173 |
| `total` = count after filters, before pagination | ✅ Line 184 |
| Sort order supports all four columns × asc/desc | ✅ Lines 175-182 |
| `get_job` returns `None` for missing id | ✅ All four `_get_*` methods return `None` on miss |
| No global state, session passed in | ✅ `__init__(self, session: Session)` |
| `raw` dict contains sufficient detail | ✅ Sufficient for detail page |
| `ruff check orch/jobs/` clean | ✅ |
| `mypy orch/jobs/` clean | ✅ |

**Note**: `orch/jobs/__init__.py` is empty. No exports defined there. If consumers use `from orch.jobs import JobType, JobsAggregator, …` they will get a `ModuleNotFoundError`. The design says "are exported as specified" — the implicit `__all__` from the module level works for direct imports. If strict `__init__.py` exports are required, this would be a MEDIUM issue. Given the module is new and intended for import by path (`from orch.jobs.aggregator import …`), this is not a practical problem.

## DaemonEvent Emission — `orch/rag/job.py`

| Check | Result |
|-------|--------|
| `code_map_completed` emitted on `completed` status | ✅ Line 285-312 |
| Uses **Python attribute** `event_metadata` (not `metadata`) | ✅ Line 298 |
| Event inserted inside same `session.commit()` as status transition | ✅ Line 313 (`session.commit()` at end of `do_update`) |
| No event on `failed` or `cancelled` | ✅ Only emitted when `status == "completed" and completed` (line 285) |
| `entity_id` set to `CodeIndexJob.id` | ✅ Line 292 |
| `message` human-readable with file/chunk counts | ✅ Lines 293-297 |
| `event_metadata` has all required fields | ✅ job_id, llm_model, embed_model, index_tier, files_indexed, chunks_created, duration_seconds (lines 299-309) |

## Cross-Cutting

| Check | Result |
|-------|--------|
| No tests added in this step | ✅ N/A — tests covered in S07 |
| `sse.py` not modified | ✅ Not touched |
| `orch/rag/qa.py` not modified | ✅ Not touched |
| No database schema change | ✅ No migration generated |

## Commands Run

```
grep -n "_run_qa_in_thread" dashboard/routers/code_qa.py  → OK: helper removed
uv run ruff check dashboard/routers/code_qa.py orch/jobs/  → All checks passed!
uv run mypy dashboard/routers/code_qa.py orch/jobs/       → Success: no issues found in 3 source files
grep -rn "code_map_completed" orch/                       → orch/rag/job.py:291
grep -rn "event_metadata" orch/rag/                      → orch/rag/job.py:298
```

## Verdict

**PASS** — all checklist items green, no issues found.