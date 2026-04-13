# F-00012 S05 CodeReview Final Report

## Summary

Final cross-agent review of F-00012 (AI Documentation Generation Phase 2). All 4 implementation steps (S01–S04) were reviewed. **Verdict: PASS with 1 security note.**

---

## Review Checklist Results

### 1. Completeness ✅

- **AC1–AC6**: All 6 acceptance criteria implemented
  - AC1: `POST /api/project/{id}/docs/{doc_id}/generate` creates queued job
  - AC2: `DocJobPoller.poll()` transitions queued→running, launches agent
  - AC3: `iw doc-job-done` transitions running→completed/failed
  - AC4: SSE stream emits `status` (2s), `completed`, `failed`, `timeout` events
  - AC5: Failed jobs show red badge + error message in job history
  - AC6: Regenerate creates new queued job even after previous completed
- **All 5 invariants enforced**:
  - Invariant 1 & 2: `started_at`/`completed_at` set via `start_doc_job()`/`complete_doc_job()`
  - Invariant 3: `get_running_jobs_count()` checked before launch (MAX=2)
  - Invariant 4: `doc-job-done` is idempotent (lines 305–308 in `doc_commands.py`)
  - Invariant 5: Failed jobs don't call `iw doc-update` (enforced by agent on-error handler)
- **Boundary behaviors tested**: concurrent limit, stall detection, 409 on duplicate, no-source-paths job creation

### 2. Daemon Integration ✅

- `DocJobPoller.poll()` called in Phase 3 of `_poll_cycle()` (`main.py:375–380`)
- Uses `SessionFactory` pattern (same as `BatchManager`)
- Executes AFTER per-project batch processing — does not interfere

### 3. CLI Commands ✅

- `iw doc-job-start`: transitions queued→running, sets `started_at`, `agent_pid`, `skill_used`
- `iw doc-job-done`: transitions running→completed/failed, computes `duration_seconds`
- Both idempotent; exit codes 0/1/2 as specified
- JSON to stdout, errors to stderr via `output_error()`

### 4. SSE Stream ✅

- Follows same pattern as `dashboard/routers/sse.py` (async generator, `SessionLocal` per poll)
- `request.is_disconnected()` checked in loop — generator exits cleanly
- `Cache-Control: no-cache`, `X-Accel-Buffering: no` headers set
- 15-minute timeout with `timeout` event emitted

### 5. Frontend ✅

- Generate button disabled (409 response shown as inline error, not blocking modal)
- SSE connects at `/api/project/{id}/docs/jobs/{job_id}/stream`
- Card refreshes on `docJobCompleted`/`docJobFailed` events
- Job history: queued=yellow clock, running=blue spinner, completed=green checkmark, failed=red X
- Error messages truncated to 80 chars with tooltip

### 6. Security ⚠️

- **SSE `project_id` validation**: `docs_job_stream()` calls `_get_project_or_404(project_id, db)` before streaming. ✅
- **Error string length**: `doc_job_done` `--error` option has no length bound. A huge error string could be stored in `DocGenerationJob.error` (Text column). Not a runtime OOM (PostgreSQL handles it), but unbounded UI display could cause rendering issues. **Note: not enforced.**
- **Subprocess command injection**: `_launch_job()` at line 139 uses `subprocess.Popen(cmd, shell=True)` where `cmd` is a list containing a single shell command string built via f-strings. `project_id`, `doc_id`, `job_id` are interpolated. These originate from DB (set by the daemon itself), not user input, so injection risk from external actors is low. However, `shell=True` with string commands is inherently riskier than passing arg lists.

### 7. Test Coverage ✅

- Full job lifecycle success path: ✅
- Full job lifecycle failure path: ✅
- Concurrent limit (MAX=2): ✅
- Stall detection (>10 min): ✅
- SSE stream: ⚠️ **No SSE integration test** — excluded in S04 because SSE creates its own `SessionLocal` session bypassing FastAPI DI. Covered by unit tests with mocking.

---

## Test Verification

| Check | Result |
|-------|--------|
| `make test-unit` | ✅ 602 passed, 1 warning |
| `make test-integration` | ✅ 360 passed, 3 warnings |
| `make quality` | ✅ ruff + format + mypy all pass |

---

## Mandatory Fix Count

**0** — No blocking issues found.

---

## Notes

1. **SSE stream tests excluded**: S04 report correctly identifies that SSE stream integration testing requires complex testcontainer setup due to the SSE endpoint creating its own `SessionLocal` session. This is acceptable given the SSE behavior is tested via unit tests with mocking.

2. **`_MAX_CONTENT_SIZE` in `doc_commands.py`**: Content for `doc-update` is bounded at 10 MB. Error strings for `doc-job-done` are not similarly bounded — recommend adding a limit (e.g., 4096 chars) in a future iteration.

3. **Skill selection mapping**: `guide|compliance|marketing|release → iw-doc-system`, all others → `iw-doc-generator`. Default is `iw-doc-generator` when `editorial_category` is unset. Matches design spec.

---

## Files Changed (Summary)

| Step | Files |
|------|-------|
| S01 | `orch/db/models.py`, `orch/db/migrations/versions/73a7ae48b82b_add_doc_job_agent_columns.py`, `orch/doc_service.py`, `orch/daemon/doc_job_poller.py`, `orch/daemon/main.py`, `tests/unit/test_doc_job_poller.py` |
| S02 | `orch/cli/doc_commands.py`, `dashboard/routers/docs.py`, `dashboard/templates/fragments/docs_generate_running.html`, `dashboard/templates/fragments/docs_job_history.html`, `tests/unit/test_doc_job_commands.py` |
| S03 | `dashboard/templates/fragments/docs_card.html`, `dashboard/templates/docs_detail.html`, `dashboard/templates/fragments/docs_job_status.html`, `dashboard/templates/fragments/docs_job_history.html` |
| S04 | `tests/integration/test_doc_generation.py`, `tests/integration/test_doc_job_routes.py`, `orch/cli/main.py` |
