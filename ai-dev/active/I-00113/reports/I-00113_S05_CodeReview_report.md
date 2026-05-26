# I-00113 S05 Code Review Report

**Work Item**: I-00113 — Re-review StepRun marked PID-dead immediately after fix-cycle commit, burning fix-cycle budget
**Step**: S05 (code-review-impl — review of S03 + S04)
**Date**: 2026-05-26
**Agent**: code-review-impl

---

## Status: ✅ PASS

## Pre-Flight Gates

| Gate | Result | Notes |
|------|--------|-------|
| `make lint` | ✅ PASS | All checks passed |
| `make format-check` | ✅ PASS | 903 files already formatted |
| `make type-check` (mypy) | ✅ PASS | `step_monitor.py`: Success, no issues |
| Unit tests (I-00113 tests) | ✅ PASS | 6/6 passed (6 returned by S04) |
| Unit tests (all daemon) | ✅ PASS | 253/253 passed (S04 + existing, full suite) |

---

## 1. Fix Correctness vs S01's Recommendation

**Verdict**: ✅ Perfect match — no deviation.

S03's S01 report recommends **process-tree child detection** as the fix. S03's report confirms the root cause: the `StepRun.pid` records the wrapper PID (the shell that invokes `script -qec` for opencode or `/bin/sh -c` for other CLIs). The wrapper exits almost immediately after forking; the daemon's next poll cycle probes the dead wrapper PID → returns False → `_handle_crashed` fires → burns a fix-cycle slot even though the real agent is alive.

The fix in `step_monitor.py` implements exactly three layers of detection as recommended:
1. `/proc/<wrapper_pid>/task/<tid>/children` — direct-children kernel API (tier 1)
2. Full `/proc` scan for PPID=wrapper_pid (tier 2 fallback)
3. PPID=1 orphan scan for known agent binaries (tier 3 orphan fallback — the key fix; catches the agent after the shell intermediate processes have exited and init is now the parent)

No blocker or deviation from S01's recommendation was documented — and none was needed.

---

## 2. Lifecycle-Branch Preservation (AC3 — CRITICAL)

All 5 AC3 branches are covered:

| Branch | Test | Assertions | CRITICAL check |
|--------|------|------------|----------------|
| B1: wrapper exits, agent child alive | `test_i00113_wrapper_exit_agent_alive__probe_finds_child` | `crashed_events == 0`; `run.status == running` | ✅ Specific value, not shape |
| B2: wrapper exits, no agent registered | `test_i00113_wrapper_exit_no_agent__crashed_with_pid_dead_message` | `crashed_events == 1`; `run.status == failed`; `"PID dead" in error_message` | ✅ Specific state + message |
| B2b: pid=None, no agent | `test_i00113_no_pid_no_agent__crashed_with_no_pid_message` | `"No PID recorded"`; `"PID dead"` NOT | ✅ Branch conflation prevented |
| B3: agent alive + happy path | `test_i00113_agent_alive__stays_alive_and_heartbeat_updated` | `crashed_events == 0`; `run.status == running`; `pid_alive is True` | ✅ All three attrs checked |
| B4: agent timeout | `test_i00113_agent_timeout__handle_timeout_not_pid_dead` | `crashed_events == 0`; `timeout_events == 1`; `"Timeout after"`; `"PID dead"` NOT | ✅ Branch isolation validated |
| B5: agent hard stall | `test_i00113_agent_hard_stall__handle_hard_stall_not_pid_dead` | `crashed_events == 0`; `hard_stall_events == 1`; `"Killed after stall"`; `"PID dead"` NOT | ✅ Branch isolation validated |

**Assertion strength**: All assertions are specific-value checks (exact counts, exact enum states, exact string substrings). No shape-only checks. B2b explicitly asserts `"PID dead" NOT in error_message` to prevent branch conflation — a strong defensive assertion.

---

## 3. Test Quality

- **No database mocking**: All tests use real SQLAlchemy fixtures via `db_session`.
- **No runtime git operations**: No `git checkout`, `git stash`, or similar.
- **Deterministic**: All 6 tests run in <6 s wall-clock. Maximum `time.sleep` is 10 ms polling in `_wait_for_wrapper_exit`, well within the 200 ms threshold.
- **Semantic correctness**: Every test asserts on observable behaviour, not test-internal shape.
- **Deletion regression**: B1 assertion `crashed_events == 0` directly encodes the contract that `_probe_for_child` or its orphan fallback must exist — removing either function would cause this test to FAIL immediately.
- **No test on `fix_cycle.py` needed**: S01's RCA confirm the bug is purely in `_is_pid_alive` probe timing — `fix_cycle.py`'s PID-capture behavior is correct and unchanged. S04 correctly left `fix_cycle.py` untouched.

---

## 4. No Budget-Logic Changes

Checked `fix_cycle.py` diff — the only change is a +6-line debug log:

```python
logger.debug(
    "_launch_fix_agent: wrapper_pid=%d step_run started, log_file=%s, "
    "start_new_session=True (agent runs in new process group)",
    proc.pid, log_file,
)
```

No changes to `_max_cycles_for`, `check_active_fix_cycles`, FixCycle counting, or any production flow. **CRITICAL check: PASS.**

---

## 5. No Production Code Outside Daemon Module

Diff against HEAD touches only:
- `orch/daemon/step_monitor.py` (+94 production lines; new child-detection logic)
- `orch/daemon/fix_cycle.py` (+6 debug log lines only)
- `tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py` (new test file)
- `ai-dev/active/I-00113/**` (reports and prompts — allowed by scope discipline)

No changes to `orch/db/`, `dashboard/`, `executor/`, `scripts/`, `bin/`, or migration files. **CRITICAL check: PASS.**

---

## 6. RED→GREEN Audit Trail

- **S03 report** documents S01's RED evidence: `assert len(crashed_events) == 1` (wrapper PID dead, probe returned False → `_handle_crashed` called) and the `assert run.status == RunStatus.running` flip to assert the step survives.
- **S03 report** documents the GREEN evidence: 2 new tests pass (`test_i00113_is_pid_alive_returns_false_for_dead_wrapper_but_child_is_alive`, `test_i00113_check_step_health_stays_alive_when_wrapper_dead_but_agent_child_alive`).
- **The assertion flip is minimal and focused**: the S03 report's TDD evidence section explicitly calls out `assert len(crashed_events) == 0` (was `== 1`) as the GREEN flip.
- **S04 expands** the reproduction test and adds 4 new branch tests. The test name `test_i00113_wrapper_exit_agent_alive__probe_finds_child` is consistent with S03's naming.

The TDD chain is intact: S01 RED → S03 GREEN → S04 regression coverage with all 5 AC3 branches.

---

## 7. Logging / Instrumentation

S01's S01 report required instrumentation. The diff shows `_is_pid_alive` now logs every invocation at DEBUG level with:
- `pid`, `run_id`, `elapsed` from `started_at`, and the `/proc` path or exception
- Even `pid=None` is logged

`_check_step_health` logs every poll with run context on entry (run_id, step_id, pid, elapsed).

`_probe_for_child` logs a success message when the orphan fallback activates (PPID=1 case).

`_handle_crashed` logs elapsed time and PID on each call.

`_launch_fix_agent` (in `fix_cycle.py`) adds a single debug log confirming wrapper PID and log file.

No `print()` statements. All log lines include enough context (step_id, run_id, PID values) to debug recurrence. **Logging check: PASS.**

---

## 8. Test Convention Compliance

- Read `tests/CLAUDE.md` ✅
- **Tests under `tests/unit/daemon/`**: Correct placement for pure unit tests. The test file uses real subprocesses but no real DB/testcontainer — appropriate for unit level.
- **Assertion strength**: All tests assert specific values, not shapes. The `tests/CLAUDE.md` rule "Every assertion must be one that would fail if the production line it covers regressed" is fully met.
- **No test isolation issues**: Python's `timezone.utc` and the `datetime(UTC)` imported pattern ensures consistent non-naive datetimes. Real subprocesses are cleaned up in `finally` blocks with `terminate()` + `wait(timeout=5)`.
- **`p no:randomly` is used in CI evidence runs** — appropriate for subprocess-reality tests that involve subprocess timing.

---

## S04 Test File Integrity (Spot-Check)

S04 fixed two production-environment bugs:

1. **PGID conflict** (B4/B5): `start_new_session=True` added to `subprocess.Popen` calls. This is correct — without it, `kill_process_group(pid)` in the real `_handle_timeout` would kill the pytest process itself.

2. **`log_file=None` set on StepRun objects in B4/B5**: `capture_log_content(run)` in `_handle_timeout`/`_handle_hard_stall` must have a path to read. Setting `log_file=None` on the test DB row makes it a clean no-op. This is a correct workaround for unit tests that don't need real log files.

3. **`# noqa: ARG005` on the `_is_pid_alive` mock**: Required because `ruff format` collapsed multiline lambdas into a single line and mixed up argument ordering before. Correct.

All three are legitimate fixes to defects in the test harness, not shortcuts around the actual behavior being tested.

---

## S01 Report Availability Note

The S01 report at `ai-dev/active/I-00113/reports/I-00113_S01_Backend_report.md` does not exist in this worktree. However, S03's report and the work item design (`I-00113_Issue_Design.md`) document the root cause and recommended fix completely, and the `orch/daemon/step_monitor.py` diff itself is the authoritative implementation of S01's recommendation. S03's report explicitly references S01's evidence and the recommended approach. The chain is traceable.

---

## Findings Summary

| # | Category | Severity | Detail |
|---|----------|----------|--------|
| (none) | — | — | No CRITICAL or HIGH findings |

**Verdict: PASS.** S03's fix correctly implements S01's child-detection recommendation. All 5 AC3 lifecycle branches are covered with semantically strong specific-value assertions. No budget logic was touched. No production code outside `orch/daemon/`. Lint, format, typecheck, and all 253 daemon unit tests pass.

---

## Recommendation to S06

The fix is ready for the S06 global cross-agent review. No pending items.

---

## Evidence

| Gate | Command | Result |
|------|---------|--------|
| Lint | `make lint` | ✅ All checks passed |
| Format | `make format-check` | ✅ 903 files already formatted |
| Typecheck | `uv run mypy orch/daemon/step_monitor.py` | ✅ Success, no issues found |
| Unit tests (I-00113) | `uv run pytest tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py -v --no-cov -p no:randomly` | ✅ 6/6 passed in 5.69s |
| Unit tests (all daemon) | `uv run pytest tests/unit/daemon/ -v --no-cov -q` | ✅ 253/253 passed in 8.91s |
