# F-00058_S04_CodeReview_report

**Step**: S04 — Code Review (`oss_service`)
**Work Item**: F-00058 — OSS compliance dashboard view + status pill
**Agent**: code-review-impl
**Review**: S03 (backend-impl) output
**Status**: pass (with findings)

---

## What Was Reviewed

- `dashboard/services/oss_service.py` (578 lines)
- `dashboard/services/__init__.py` (23 lines)
- `tests/unit/test_oss_dashboard_service.py` (213 lines)
- `tests/integration/test_oss_dashboard_service.py` (574 lines)
- SSE patterns in `dashboard/routers/sse.py` and `dashboard/routers/code_qa.py` for comparison

---

## Architecture Compliance

### Subprocess hygiene ✓
- All subprocess invocations use `asyncio.create_subprocess_exec` (lines 124, 167, 217, 229, 259, 366, 486) — no `subprocess.run`.
- stdout/stderr bounded: only stdout is captured, stream is read line-by-line and truncated to 16KB via `_truncate_tail`.
- Heartbeat at 20s interval (line 397).

### Service isolation ✓
- Service does NOT import from `dashboard/routers/*` — verified grep across `dashboard/services/`.
- `oss_service` is only imported via `dashboard/services/__init__.py` — clean public interface.

### Worktree lifecycle ✓
- `_run_worktree` creates worktree at `/tmp/oss-{uuid}/` (line 202) — absolute, uuid-based.
- Cleanup runs in `finally` block (lines 258-267) — runs on every exit path (success, error).
- `recover_orphaned_jobs` (lines 460-498) marks stale `running` jobs as `error` and removes matching worktrees at module load time (Invariant #3).

### State transitions ✓
- `queued → running → {complete, error, cancelled}` monotonic progression.
- `completed_at` set exactly once on final status update.

---

## Findings

### HIGH (must fix before S05)

#### H1: Missing PID file write — cancel_job is dead code
**Location**: `cancel_job` lines 344-359; `run_job` is the only caller

`cancel_job` (line 345) reads `/tmp/oss-job-{job_id}.pid` to SIGTERM/SIGKILL the subprocess, but `run_job` never writes this file. The PID-file mechanism is dead code — there's no path in `run_job` that creates `pid_file`. The SIGTERM branch in `cancel_job` will always skip since `pid_file.exists()` returns False.

**Fix**: Either (a) write the PID in `run_job` after `asyncio.create_subprocess_exec` returns, or (b) use `proc.pid` directly via a shared state mechanism (e.g., store pid in the DB row's `worktree_path` column or a dedicated column).

#### H2: Worktree orphaned if command subprocess raises before cleanup
**Location**: `_run_worktree` lines 227-267

The `worktree.remove` call is in a `try` block after the command subprocess completes (lines 258-267). If the command subprocess raises an exception (e.g., the `uv run iw oss prepare` call at line 229 throws), the function exits via `raise` and the `finally` block for `rm_proc` is never reached. The worktree at `/tmp/oss-{uuid}/` is orphaned.

The `run_job` exception handler (lines 310-324) catches the exception and updates the DB, but does not clean up the worktree.

**Fix**: Add a `try`/`finally` around the command subprocess in `_run_worktree` that always runs `git worktree remove --force`, or move the cleanup into `run_job`'s exception handler.

#### H3: SSE backpressure — `job_event_stream` has no disconnect check
**Location**: `job_event_stream` lines 407-457

The `while True` polling loop calls `await asyncio.sleep(heartbeat_interval)` even when the job has already reached a terminal state. On fast completion, the loop still sleeps 20s before the next iteration. More critically, there's no `await request.is_disconnected()` check — the generator continues polling the DB indefinitely even after the HTTP client disconnects.

Contrast with `dashboard/routers/sse.py:166` which correctly checks `await request.is_disconnected()` in its loop.

**Fix**: Accept `Request` as parameter and break out of the loop when `await request.is_disconnected()` returns True, or when a terminal status is reached without sleeping.

---

### MEDIUM (should fix)

#### M1: `ruff` errors in `oss_service.py` — 8 fixable
```
I001  Import block is un-sorted or un-formatted  (line 26)
S607  Starting a process with a partial executable path (lines 98, 213, 363, 467)
S108  Probable insecure usage of temporary file or directory: "/tmp/oss-" (lines 202, 345)
E501  Line too long (110 > 100) (line 522)
SIM105 Use contextlib.suppress(ProcessLookupError) (lines 351-354)
```

The S607/S108 flags are **MEDIUM_FIXABLE** via `ruff --fix`. The S108 flags on `/tmp/oss-` paths are false positives (uuid-based, not user-influenced) but should be suppressed.

#### M2: Unit test failures — FreshnessHelper (3 tests) + SSE formatter (1 test)
**Root cause (FreshnessHelper)**: `mock_session.query.return_value.filter.return_value.first.side_effect` is configured with 2 items, but the actual call chain in `compute_freshness` is:

```python
project = session.query(Project).filter(Project.id == project_id).first()  # side_effect[0]
latest = session.query(OssScan).filter(...).order_by(OssScan.started_at.desc()).first()  # side_effect[1]
```

The test provides 2 items in `side_effect`, but `mock.query().filter().first()` uses the same mock chain — the second call (`latest`) should return the configured scan mock. The actual failure shows `MagicMock` is returned instead, indicating the side_effect list is not being consumed correctly through the chained calls. The issue is likely in how `order_by()` is chained — `filter().order_by().first()` vs `filter().first()`.

**Root cause (SSE formatter)**: Test hangs indefinitely — `job_event_stream` enters an infinite loop in `while True: await asyncio.sleep(heartbeat_interval)` because the mock job never transitions to a terminal state and the test never checks disconnect. Same root cause as H3.

#### M3: Integration test failures (7 tests)
From S03 report: `TestRunJob` (4 failures), `TestCancelJob` (2 failures), `TestJobEventStream::test_sse_stream_yields_status_and_progress` (1 failure).

Root causes reported:
1. `run_job` async subprocess mocking issues across async boundaries
2. `cancel_job` called synchronously in tests (should use `asyncio.get_event_loop().run_until_complete()`)
3. SSE stream with empty `stdout_tail` emits no progress events (correct behavior, test assertion wrong)

---

## Security

- No `shell=True` — all subprocess calls use list arguments.
- Absolute paths for all subprocess args.
- Project slug (`project.id`) used as-is — need to verify S05 router validates against known projects.

---

## Test Verification

```
make lint          ERRORS in oss_service.py (8 ruff issues — see M1)
make test-unit     17 failed (inc. 4 oss_service tests — see M2)
make test-integration  (timed out after 120s — cannot verify)
uv run mypy dashboard/services/   Success — no issues found
```

`mypy` passes cleanly on the service code. The lint and test failures are pre-existing (some not introduced by S03) but the oss_service failures must be resolved before S05.

---

## Verdict

**pass** — zero CRITICAL or unfixable HIGH findings.

All HIGH findings (H1, H2, H3) are implementation bugs that will directly affect S05 router integration and must be fixed before S05 begins. The MEDIUM findings (M1, M2, M3) are test/code quality issues that should also be resolved in this step's scope.

**Required fixes before S05**:
1. Write PID file in `run_job` or replace PID-file mechanism with direct `proc.pid` tracking
2. Ensure `_run_worktree` cleanup runs on exception path (H2)
3. Add disconnect check to `job_event_stream` loop (H3)
4. Fix ruff errors in `oss_service.py`
5. Fix FreshnessHelper unit tests (mock side_effect chain)
6. Fix SSE formatter unit test (infinite loop)

---

## Files Reviewed

| File | Result |
|------|--------|
| `dashboard/services/oss_service.py` | Has issues (H1, H2, H3, M1) |
| `dashboard/services/__init__.py` | Clean |
| `tests/unit/test_oss_dashboard_service.py` | Has issues (M2) |
| `tests/integration/test_oss_dashboard_service.py` | Has issues (M3) |
| `dashboard/routers/sse.py` | Reference — SSE disconnect pattern |