# CR-00035 S07 — API Implementation Report

## Work Item
**CR-00035** — Doc-generation job observability + execution report + dispatch fix

## Step
**S07 — api-impl**

---

## What Was Done

Added three HTTP endpoints that surface the on-disk doc-job log file to the dashboard.

### Router Chosen: `jobs_ui.py`

Rationale: the new routes live under `/project/{project_id}/jobs/doc_generation/{job_id}/log/*`, which is the natural extension of the existing job-detail URL space already handled by `jobs_ui.py`. The `docs.py` router handles `/project/{project_id}/docs/...` and `/api/docs/...` routes — mixing `jobs/doc_generation/...` endpoints there would break the URL hierarchy coherence and potentially shadow existing lifecycle endpoints.

### Endpoints Added

| Route | Response type | Purpose |
|---|---|---|
| `GET /project/{pid}/jobs/doc_generation/{job_id}/log/tail?n=200` | `application/json` | Last N ANSI-stripped lines (default 200, cap 1000) |
| `GET /project/{pid}/jobs/doc_generation/{job_id}/log/stream` | `text/event-stream` | Live SSE stream of new log lines |
| `GET /project/{pid}/jobs/doc_generation/{job_id}/log/raw` | `text/plain` | Full raw log download (ANSI preserved) |

### Private Helper: `_resolve_doc_job_log_path`

All three endpoints share this path-resolution helper (defined once, reused):
- Looks up `DocGenerationJob` by `public_id` OR UUID (`job_id` param)
- Validates project exists and `repo_root` is set
- Computes `Project.repo_root / "ai-dev" / "logs" / f"doc_job_{job.id}.log"` (always uses UUID, never public_id)
- Resolves and validates the path is inside `repo_root` (defence-in-depth against path traversal)
- Raises `HTTPException(404)` on any failure

### Implementation Details

**`log/tail`** (`doc_job_log_tail`):
- Reads full file, strips ANSI, takes last `n` lines
- Caps each line at 8 KB with `…` suffix
- Returns `{lines, truncated_from_bytes, file_size_bytes, line_count}`
- 404 for missing file

**`log/stream`** (`_doc_job_log_stream` async generator + `doc_job_log_stream` endpoint):
- Uses `time.sleep(0.25)` tight poll loop (not non-blocking fd — simplest and most reliable)
- Emits last 50 lines on connect (context for late-joiners)
- Follows new bytes as they're written; splits on `\n`
- `event:ping` heartbeat every 15 seconds when no new data
- Fresh `SessionLocal()` per status re-check every 2 seconds
- `event:status data:terminal` and close when job reaches `completed` or `failed`
- Respects `request.is_disconnected()` for clean client-disconnect handling
- Pre-validates job existence before streaming (so unknown job → HTTP 404, not SSE error frame)

**`log/raw`** (`doc_job_log_raw`):
- Streams raw file with `Content-Disposition: attachment; filename="doc_job_{job.id}.log"`
- ANSI **not** stripped (operators want original)
- 404 for missing file

### `job_detail` Handler Modification

Added `log_file_exists: bool` to the template context in `jobs_ui.py:job_detail`. For `doc_generation` jobs only, it resolves the log path (suppressing 404) and checks `is_file()`. Other job types always get `False`. This is consumed by S09's conditional "Download raw log" link.

---

## Files Changed

| File | Change |
|---|---|
| `dashboard/routers/jobs_ui.py` | Added `_resolve_doc_job_log_path`, three new endpoints (`doc_job_log_tail`, `_doc_job_log_stream`, `doc_job_log_stream`, `doc_job_log_raw`), and `log_file_exists` in `job_detail` context |
| `tests/dashboard/test_doc_job_log_endpoints.py` | **New** smoke tests for all three endpoints (404 for unknown job/missing file, 200 + correct content-type for existing file) |

---

## Pre-flight Quality Gates

```bash
make format   # ✓ 615 files formatted
make typecheck # ✓ Success: no issues found in 226 source files
make lint     # ✓ All checks passed!
```

---

## Test Results

**Unit tests** — `make test-unit`: `2600 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings` ✓

**Dashboard tests** — `uv run pytest tests/dashboard/ -q --no-cov`: `452 passed, 10 skipped, 1 xfailed, 2 warnings` ✓

**New smoke tests** — `uv run pytest tests/dashboard/test_doc_job_log_endpoints.py -v --no-cov`: `10 passed` ✓
- `test_returns_404_for_unknown_job` (tail / stream / raw)
- `test_returns_404_for_missing_log_file` (tail / raw)
- `test_returns_200_with_lines_for_existing_log`
- `test_respects_n_parameter`
- `test_n_parameter_hard_capped_at_1000`
- `test_returns_sse_content_type`
- `test_returns_text_plain_with_attachment_header`

---

## SSE Polling Strategy

Used `time.sleep(0.25)` inside the while loop (not `os.set_blocking(fd, False)`). Rationale:
- Simpler to reason about — no fd lifecycle management
- The log file is written by the daemon poller, which is cooperative (not high-frequency)
- Directly follows the established SSE pattern in `docs.py:_job_status_stream` which uses `await asyncio.sleep(2)`
- Clean and testable

Heartbeat: every 15 seconds. Status re-check: every 2 seconds via fresh `SessionLocal()`.

---

## Blockers

None.

---

## Notes

- The `doc_job_log_stream` endpoint pre-validates the job via `_resolve_doc_job_log_path` before launching the `StreamingResponse`, ensuring unknown job IDs return HTTP 404 (not a SSE `event:error` frame). This is consistent with how `docs_job_status` works.
- `log_file_exists` is only resolved for `JobType.doc_generation` in `job_detail`; all other job types get `False` (they don't have log files in `ai-dev/logs/`).
- The log path resolution uses `job.id` (UUID) in the filename, never `public_id`, per the convention from `doc_job_poller.py:244`.
- Path traversal defence: resolved log path is checked with `is_relative_to(repo_root_resolved)` after `.resolve()`.