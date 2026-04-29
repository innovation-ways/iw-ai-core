# I-00049 S02 Code Review Report

**Work Item**: I-00049 — Daemon blocked by synchronous QV baseline gate command pipe deadlock
**Step Reviewed**: S01 (backend-impl)
**Reviewer**: code-review-impl
**Verdict**: PASS

---

## Files Changed

- `orch/daemon/batch_manager.py` — `_run_gate_command` fix (process-group kill)
- `orch/daemon/qv_baseline.py` — removed `"integration-tests"` from `GATE_PARSERS`

---

## Checklist Findings

### 1. Process-group kill correctness

| Check | Result |
|-------|--------|
| `start_new_session=True` | ✅ Line 739 |
| `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)` on `TimeoutExpired` | ✅ Line 747 |
| `ProcessLookupError` suppressed | ✅ Line 746 (`contextlib.suppress`) |
| `proc.communicate()` after `killpg` without timeout to drain pipes | ✅ Line 748 |
| Return value in timeout path (decoded stdout+stderr) | ✅ Line 749 |

**Additional observation**: `os.getpgid` can raise `PermissionError` (ESRCH) if the process is in an unreachable state, which is distinct from `ProcessLookupError`. The current `suppress(ProcessLookupError)` would not suppress `PermissionError`, but since the process group was spawned by the current user and `start_new_session=True` places it in a new session, this is extremely unlikely in practice. No change required — the code is correct for the intended scenario.

### 2. Normal exit path

- `proc.communicate(timeout=300)` returns `(stdout, stderr)` bytes — decoded with `errors="replace"` in both paths. ✅
- No double-decoding. ✅
- Combined via `+` — correct. ✅

### 3. `GATE_PARSERS` removal

- `"integration-tests"` is **definitively absent** from `GATE_PARSERS` (lines 224-229). ✅
- No other code path relies on `"integration-tests"` being in `GATE_PARSERS`. The gate is still used in workflow manifests, step definitions, and `step_monitor.py` timeouts — but those are for step execution (S10+), not baseline computation at worktree setup. ✅
- Unknown gate handling in `_compute_qv_baselines` (lines 664-670) logs a warning and skips gracefully. ✅

### 4. Code Quality

- `os` and `signal` are module-level imports. ✅
- `# noqa: S602` is present on the `Popen` call. ✅
- `# noqa: ARG002` on unused `gate` param is appropriate (signature kept for future extensibility). ✅
- Fix is minimal — exactly two files changed as designed. ✅

### 5. Architecture Compliance

- No threading introduced. ✅
- Daemon is single-threaded; the fix uses only `subprocess.Popen` + `os.killpg`, no threads. ✅

### 6. Security

- `shell=True` used with `# noqa: S602` comment. ✅
- Command and `worktree_path` come from DB/trusted sources (step.command + git-resolved path). No new injection surface. ✅

### 7. Testing

- Unit tests: **1963 passed, 2 skipped, 0 failed** ✅
- Typecheck: **Success: no issues found** ✅
- Lint on changed files: **All checks passed** ✅

Note: The global `make lint` shows 6 pre-existing errors in `test_merge_queue_migration_pipeline.py` (PT006 type hint issue + ERA001 commented-out code) — unrelated to these changes. Lint on the two changed files passes cleanly.

---

## Findings Summary

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00049",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "1963 passed, 2 skipped, 0 failed",
  "notes": "All checklist items pass. Process-group kill is correctly implemented. integration-tests removal is clean. Pre-existing lint errors in test_merge_queue_migration_pipeline.py are unrelated to these changes."
}
```
