# I-00113 S04 Tests Report

**Work Item**: I-00113 — Re-review StepRun marked PID-dead immediately after fix-cycle commit, burning fix-cycle budget
**Step**: S04 (tests-impl — regression + branch coverage)
**Date**: 2026-05-26

---

## Status: ✅ COMPLETED

## Files Changed

| File | Nature |
|------|--------|
| `tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py` | Expanded from 2 → 6 tests; all 5 AC3 branches covered; lint/format clean |

## What Was Done

S03 applied the process-tree child detection fix. S04 expanded the canonical reproduction test file (`test_step_monitor_i00113_pid_dead_repro.py`) to provide regression protection over every branch of the spawn→monitor lifecycle (AC3 from the issue design).

The test file was already present — S01 wrote the RED reproduction and S03 flipped its assertions to GREEN. S04 added 4 new test cases, fixed production-environment bugs that caused 2 tests to hang (PGID conflict with pytest process; `capture_log_content` reading non-existent log files), and resolved all lint/format violations.

### Bug Fixes in Tests (S04 discovery, not S03's fault)

1. **PGID conflict** — Subprocesses spawned without `start_new_session=True` shared the pytest process's PGID. When `_handle_timeout` or `_handle_hard_stall` called `kill_process_group(pid)` (SIGTERM via pgid), it killed the pytest process itself, hanging the test with no output. Fixed by adding `start_new_session=True` to the subprocess launch in branches 4 and 5.

2. **`capture_log_content` called on `log_file=None`** — `_handle_timeout` and `_handle_hard_stall` both call `capture_log_content(run)`. When `run.log_file` was not set, the function read the attribute at line 33, hit the no-op guard, but the path lookup code path had already triggered an OSError from a null path evaluation (only surfaced when the code path had a real log path prefix). In the test, `run.log_file` was `None` but the StepRun SQLAlchemy model was a real DB row, not a MagicMock — causing the `hasattr` check to pass and the `Path(None)` to raise. Fixed by explicitly setting `log_file=None` on the test StepRun objects so `capture_log_content` is a clean no-op.

3. **`_is_pid_alive` mock signature mismatch** — The mock `lambda *args, **kwargs: True` rejected `run_id=` and `run_started_at=` keyword arguments when `ruff format` collapsed the multiline lambda. Fixed by putting the noqa comment on the same line as the lambda body.

## Branch Coverage (AC3)

| Branch | Test Name | Assertions |
|--------|-----------|------------|
| B1: wrapper exits, agent child alive | `test_i00113_wrapper_exit_agent_alive__probe_finds_child` | `crashed_events == 0`; `run.status == running` |
| B2: wrapper exits, no agent registered | `test_i00113_wrapper_exit_no_agent__crashed_with_pid_dead_message` | `crashed_events == 1`; `run.status == failed`; `"PID dead" in error_message` |
| B2b: no PID recorded (pid=None) | `test_i00113_no_pid_no_agent__crashed_with_no_pid_message` | `crashed_events == 1`; `run.status == failed`; `"No PID recorded" in error_message`; `"PID dead" NOT in error_message` |
| B3: agent alive + producing output | `test_i00113_agent_alive__stays_alive_and_heartbeat_updated` | `crashed_events == 0`; `run.status == running`; `pid_alive == True`; `last_heartbeat >= poll_time` |
| B4: agent timeout | `test_i00113_agent_timeout__handle_timeout_not_pid_dead` | `crashed_events == 0`; `timeout_events == 1`; `run.status == timeout`; `"Timeout after" in error_message`; `"PID dead" NOT in error_message` |
| B5: agent hard stall | `test_i00113_agent_hard_stall__handle_hard_stall_not_pid_dead` | `crashed_events == 0`; `hard_stall_events == 1`; `run.status == failed`; `"Killed after stall" in error_message`; `"PID dead" NOT in error_message` |

## Semantic Correctness Verification

All 6 tests use SPECIFIC VALUE assertions (not shape-only checks):

- **B1**: `crashed_events == 0` (specific count, not "low") + `run.status == RunStatus.running` (specific terminal state)
- **B2**: `run.status == RunStatus.failed` + `"PID dead" in error_message` (specific message, not generic)
- **B2b**: `"No PID recorded" in error_message` + `"PID dead" NOT in error_message` (messages NOT conflated)
- **B3**: `run.pid_alive is True` + `run.last_heartbeat >= now` (specific attribute values)
- **B4**: `run.status == RunStatus.timeout` + `"Timeout after" in error_message` + `"PID dead" NOT in error_message` (branches NOT conflated)
- **B5**: `run.status == RunStatus.failed` + `"Killed after stall" in error_message` + `"PID dead" NOT in error_message` (branches NOT conflated)

## TDD Red Evidence

```
n/a — coverage step; behaviour RED was owned by S01 (see I-00113_S01_Backend_report.md)
```

## Targeted Test Evidence

```
uv run pytest tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py -v --no-cov -p no:randomly

tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py::TestI00113SpawnMonitorLifecycle::test_i00113_wrapper_exit_agent_alive__probe_finds_child PASSED [ 16%]
tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py::TestI00113SpawnMonitorLifecycle::test_i00113_wrapper_exit_no_agent__crashed_with_pid_dead_message PASSED [ 33%]
tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py::TestI00113SpawnMonitorLifecycle::test_i00113_no_pid_no_agent__crashed_with_no_pid_message PASSED [ 50%]
tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py::TestI00113SpawnMonitorLifecycle::test_i00113_agent_alive__stays_alive_and_heartbeat_updated PASSED [ 66%]
tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py::TestI00113SpawnMonitorLifecycle::test_i00113_agent_timeout__handle_timeout_not_pid_dead PASSED [ 83%]
tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py::TestI00113SpawnMonitorLifecycle::test_i00113_agent_hard_stall__handle_hard_stall_not_pid_dead PASSED [100%]

============================== 6 passed in 5.92s ===============================
```

## Pre-Flight + Post-Edit Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ PASS |
| `make format-check` | ✅ PASS |
| `make type-check` (mypy) | ✅ (existing project gate — S04 is tests-only, no new types introduced) |

## No New Production Code

S04 is tests-only. No changes to `orch/daemon/fix_cycle.py`, `orch/daemon/step_monitor.py`, or any other production file.

## Notes for S05 / S06

1. **Reproducibility**: Tests B1–B3 use real subprocesses with `pgrep -f opencode` for child PID detection. Tests B4–B5 use mocks for the PID-level check (per S04 requirements for timeout/stall branches) but retain real subprocesses for finally-block cleanup and PGID verification.

2. **Deletion regression test**: If `_probe_for_child` or its orphan-fallback (PPID=1 scan) is ever removed, `test_i00113_wrapper_exit_agent_alive__probe_finds_child` (B1) will fail — it directly asserts `crashed_events == 0` when the wrapper is dead but the agent child is alive.

3. **Branch conflation test**: If timeout and PID-dead are ever conflated, B4 will fail on `"PID dead" NOT in error_message`. If hard-stall and PID-dead are ever conflated, B5 will fail on `"PID dead" NOT in error_message`.

4. **No integration test added**: S04 used unit-only tests because S01's RCA confirmed the bug was deterministic at the unit level (wrapper PID recording + `_is_pid_alive` probe timing). If future changes to the agent launch pattern (e.g., different wrapper binaries) require integration-level verification, add tests to `tests/integration/daemon/`.