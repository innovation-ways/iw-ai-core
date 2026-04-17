# CR-00006 S02 — Backend Review

## Input Files

- `ai-dev/active/CR-00006/CR-00006_CR_Design.md` — source of truth
- `ai-dev/active/CR-00006/prompts/CR-00006_S01_Backend_prompt.md` — what S01 was asked to do
- `dashboard/routers/code_qa.py` — streaming bridge (modified in S01)
- `orch/jobs/aggregator.py` — new file (created in S01)
- `orch/jobs/__init__.py` — new file (created in S01)
- `orch/rag/job.py` (or wherever completion path lives) — `DaemonEvent` emission added in S01

## Output Files

- `ai-dev/work/CR-00006/reports/S02_backend_review.md` — review findings (created during execution)

## Context

**Work item**: CR-00006
**Step**: S02
**Agent**: backend-review

You are reviewing the backend implementation from S01. Three artefacts to review: the streaming-bridge fix, the aggregator service, and the DaemonEvent emission.

## Review Checklist

### Streaming bridge (`dashboard/routers/code_qa.py`)

- [ ] The `_run_qa_in_thread` helper is fully removed (no references remain).
- [ ] The replacement uses an `asyncio.Queue` + `threading.Thread` (or equivalent non-buffering pattern).
- [ ] The worker thread writes to the queue via `loop.call_soon_threadsafe(queue.put_nowait, …)` so tokens hop to the async side as they are produced.
- [ ] The outer async generator awaits `queue.get()` in a loop and yields an SSE frame per token — it does NOT collect tokens into a list before yielding.
- [ ] The wire format is preserved exactly: `data: {"token": "..."}\n\n`, `data: {"event": "done", "full_response": "..."}\n\n`, `data: {"event": "error", "message": "..."}\n\n`.
- [ ] The `code_qa` endpoint signature, 404 index-path check, and `StreamingResponse` headers (`Cache-Control: no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`) are unchanged.
- [ ] Error paths (`ConnectionRefusedError`, `OSError`, `httpx.ConnectError` raised from `QAEngine.answer_stream`) produce a single `"event": "error"` frame and exit cleanly.
- [ ] Client disconnect is handled: a cancellation signal reaches the worker thread (e.g., via a `threading.Event`) so the thread doesn't leak after the response is aborted.
- [ ] No `asyncio.run(...)` is called inside the main request event loop (running one inside the worker thread is fine).
- [ ] `ruff check dashboard/routers/code_qa.py` is clean.
- [ ] `mypy dashboard/routers/code_qa.py` is clean (acceptable: narrow `# type: ignore` comments with a reason).

### Aggregator (`orch/jobs/aggregator.py`)

- [ ] `JobType`, `JobRow`, `JobListResult`, and `JobsAggregator` are exported as specified in the design.
- [ ] All four sources are queried: `code_index_jobs`, `doc_generation_jobs`, `batches`, `project_docs` with `doc_type = DocType.research`.
- [ ] Status normalisation follows the table in the design (BatchStatus → lowercase, DocStatus mapping, JobStatus lowercase, CodeIndexJob.status passthrough).
- [ ] `started_at` / `finished_at` mapping matches the design table.
- [ ] `title` for `doc_generation` joins `project_docs.title` via `doc_id` when present and falls back to `"Doc generation (orphan)"` when `doc_id is NULL`.
- [ ] Filter parameters (`types`, `statuses`, `date_from`, `date_to`) all narrow the result set correctly.
- [ ] Pagination returns `total` = count across all four sources after filters, before pagination.
- [ ] Sort order supports `started_at`, `finished_at`, `status`, `job_type` × `asc`/`desc`.
- [ ] `get_job` returns `None` (not raise) for a missing id.
- [ ] The service has no global state, accepts a session, and does not open its own DB connection.
- [ ] `raw` dict on `JobRow` contains enough data to drive a detail page (all meaningful source columns).
- [ ] `ruff check orch/jobs/` and `mypy orch/jobs/` are clean.

### DaemonEvent emission

- [ ] On successful completion (`status = completed`), a `DaemonEvent` with `event_type = "code_map_completed"` is inserted.
- [ ] The insert uses the **Python attribute** `event_metadata`, not `metadata` (see `CLAUDE.md` critical rules).
- [ ] The event row is inserted inside the same `db.commit()` as the status transition — not as a separate transaction.
- [ ] No event is emitted on `failed` or `cancelled`.
- [ ] `entity_id` is set to the `CodeIndexJob.id` (UUID as text).
- [ ] `message` is human-readable and includes file/chunk counts.
- [ ] `event_metadata` includes `job_id`, `llm_model`, `embed_model`, `index_tier`, `files_indexed`, `chunks_created`, and `duration_seconds` (when computable).

### Cross-cutting

- [ ] No tests were added in this step (S07 will cover tests).
- [ ] `sse.py` was NOT modified in this step (S03 owns it).
- [ ] No changes to `orch/rag/qa.py`.
- [ ] No database schema change, no Alembic migration.

## Commands to Run

```bash
grep -n "_run_qa_in_thread" dashboard/routers/code_qa.py || echo "OK: helper removed"
grep -n "asyncio.Queue\|call_soon_threadsafe" dashboard/routers/code_qa.py

uv run ruff check dashboard/routers/code_qa.py orch/jobs/
uv run mypy dashboard/routers/code_qa.py orch/jobs/

grep -rn "code_map_completed" orch/ dashboard/
grep -rn "event_metadata" orch/rag/  # confirm correct attribute used
```

## Signal completion

If the implementation is correct:

```bash
iw step-done CR-00006 S02 --summary "Backend review passed: streaming bridge non-buffering and wire-format-preserving, aggregator unions four sources with correct status/title/timestamp mapping, DaemonEvent(code_map_completed) emitted in-transaction with event_metadata attribute"
```

If issues are found, write each finding to the report with severity (CRITICAL / HIGH / MEDIUM / LOW), file:line references, and a concrete fix suggestion. Then:

```bash
iw step-fail CR-00006 S02 --reason "<count and summary of CRITICAL/HIGH findings — e.g., '2 CRITICAL: streaming still buffers + event emitted in separate txn'>"
```
