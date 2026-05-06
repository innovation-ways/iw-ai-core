# CR-00035 S08 — CodeReview Report (S07: api-impl)

## Work Item
**CR-00035** — Doc-generation job observability + execution report + dispatch fix

## Step Reviewed
**S07 (api-impl)** — three log endpoints: `/log/tail`, `/log/stream`, `/log/raw`

---

## Pre-Review Quality Gates

| Check | Result |
|---|---|
| `make lint` | ✓ All checks passed |
| `make format-check` | ✓ 615 files already formatted |
| `make typecheck` | ✓ Success: no issues found in 226 source files |

---

## Route Registration & Order

**File reviewed**: `dashboard/routers/jobs_ui.py`

FastAPI matches routes in declaration order. The new routes are:
- `doc_job_log_tail` at line 268 — `GET /project/{project_id}/jobs/doc_generation/{job_id}/log/tail`
- `doc_job_log_stream` at line 428 — `GET /project/{project_id}/jobs/doc_generation/{job_id}/log/stream`
- `doc_job_log_raw` at line 456 — `GET /project/{project_id}/jobs/doc_generation/{job_id}/log/raw`

The existing `GET /project/{project_id}/jobs/{job_type}/{job_id}` (job_detail) is at line 218 and uses `{job_type}` as a path parameter — it does NOT match the literal string `doc_generation`, so there is no shadowing. However, FastAPI's behaviour for path parameters vs. literal path segments means the catch-all `/{job_type}/{job_id}` would NOT match the more specific literal `/doc_generation/{job_id}` route — confirmed by reading `app.py` router order, where `jobs_ui` is registered once with no prefix conflicts.

The `doc_job_log_stream` endpoint pre-validates the job via `_resolve_doc_job_log_path` before returning a `StreamingResponse`, ensuring 404 for unknown jobs (not a SSE error frame).

**Finding**: ✓ No shadowing issue.

---

## Path Resolution (`_resolve_doc_job_log_path`)

- Accepts both `public_id` (DOC-NNNNN) and UUID: tries `DocGenerationJob.public_id == job_id` first, falls back to `db.get(DocGenerationJob, job_id)`.
- Log filename uses `job.id` (UUID), never `public_id` — confirmed at line 60.
- Resolved path is verified to be inside `Project.repo_root` after `.resolve()` via `is_relative_to()` — line 67-68.
- 404 raised (with explanatory detail) for: unknown project, empty `repo_root`, missing job, path resolved outside `repo_root`.

**Finding**: ✓ Path traversal guard in place.

---

## `/log/tail` Endpoint

- Default `n=200` via `Query(default=_MAX_LOG_TAIL_LINES, ge=1, le=_MAX_LOG_TAIL_LINES_HARD_CAP)` — the hard cap is `_MAX_LOG_TAIL_LINES_HARD_CAP = 1000`. ✓ Verified.
- ANSI strip via `strip_ansi` imported from `orch/utils/log_capture.py` — not re-implemented inline. ✓
- Per-line cap of 8 KB (`_MAX_LINE_BYTES = 8 * 1024`) with `…` truncation suffix — lines 315-321. ✓
- Empty file → 200 with `{"lines": [], ...}` — no special case needed since `splitlines()` of empty string returns `[]`. ✓
- Missing file → 404 with `{"detail": "log file not found"}` — lines 283-287. ✓
- Response shape: `{"lines", "truncated_from_bytes", "file_size_bytes", "line_count"}` — matches design doc. ✓

---

## `/log/stream` Endpoint (SSE)

- `Content-Type: text/event-stream; charset=utf-8` — set via `media_type="text/event-stream"` on `StreamingResponse`. ✓
- Initial 50-line backfill before tailing — lines 372-377 (`initial_lines = initial_text.splitlines()[-50:]`). ✓
- `event:ping` heartbeat every 15 seconds (`_STREAM_HEARTBEAT_SECONDS = 15`) — lines 404-406. ✓
- Terminal-status detection: fresh `SessionLocal()` re-check every 2 seconds (`last_status_check` + 2.0s threshold), uses `session.get(DocGenerationJob, job.id)` and checks `JobStatus.completed`/`JobStatus.failed`. ✓
- On terminal: `yield "event: status\ndata: terminal\n\n"` then return — generator exits, closing the stream. ✓
- Client disconnect via `await request.is_disconnected()` at top of loop — breaks and returns, terminating the generator. ✓
- Uses `os.read(f.fileno(), 4096)` for non-blocking reads with `time.sleep(_STREAM_POLL_SECONDS)` (0.25s) on empty reads. ✓

**Key check — terminal status detection pattern**: The generator re-opens a **fresh, short-lived session** every 2 seconds to check job status. This is the "single most likely defect" mentioned in the review checklist, and the implementation handles it correctly: it does NOT hold a long-lived session open for the stream's lifetime.

**Finding**: ✓ Terminal detection pattern is correct.

---

## `/log/raw` Endpoint

- ANSI **not** stripped — raw file read at line 476-478. ✓
- `Content-Disposition: attachment; filename="doc_job_{_job.id}.log"` — line 484. ✓
- File missing → 404 at lines 469-473. ✓
- Streamed via `iterfile()` generator reading 64 KB chunks — not loaded entirely in memory. ✓

---

## Cross-Cutting Concerns

- No `agent-browser`, `chromium.launch()`, or `npx playwright install` references in the changed files. ✓
- Type hints on `_resolve_doc_job_log_path`: `-> tuple[DocGenerationJob, Path]` — line 38. ✓
- Imports organized per ruff conventions (`strip_ansi` from `orch.utils.log_capture`). ✓
- Helper `_doc_job_log_stream` is module-private (prefixed with `_`), async generator, used only by `doc_job_log_stream`. ✓

---

## Test Results

| Suite | Result |
|---|---|
| `make test-unit` | 2600 passed, 4 skipped, 5 xfailed, 1 xpassed ✓ |
| Dashboard smoke tests (`test_doc_job_log_endpoints.py`) | 10 passed ✓ |
| `test_doc_job_poller.py` (15 tests) | 15 passed ✓ |
| `make typecheck` | Success: no issues found ✓ |

---

## Summary

**Verdict**: PASS

S07 (api-impl) correctly implements the three AC8 log endpoints. The implementation is clean, follows existing SSE patterns in the codebase, and correctly handles:
- Route registration order (no shadowing of `job_detail`)
- Path resolution with traversal guard using UUID
- Per-line 8 KB cap and 1000-line hard cap
- SSE terminal status detection via short-lived per-check sessions (not a long-lived session)
- Raw download with ANSI preserved
- All 404 error paths with explanatory bodies

No mandatory fixes required. Lint, format, and typecheck all clean.