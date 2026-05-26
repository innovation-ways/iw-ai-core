# F-00089 S04 Backend Report

## Summary
Implemented `tests/integration/daemon_chaos/test_agent_stall_recovery.py` with 4 deterministic integration tests for stall handling:
- `test_stalled_agent_is_detected`
- `test_stalled_agent_step_recorded`
- `test_stall_policy_routing`
- `test_stall_threshold_zero_boundary`

Used a clock shim (monkeypatched `orch.daemon.step_monitor.datetime.now`) and PID/kill monkeypatches to avoid wall-clock sleeps and real process signals.

## Files Changed
- `tests/integration/daemon_chaos/test_agent_stall_recovery.py`

## TDD (RED → GREEN)
RED evidence captured before refactor:
- `tests/integration/daemon_chaos/test_agent_stall_recovery.py::test_stalled_agent_is_detected`
- `AssertionError: assert <RunStatus.failed: 'failed'> == <RunStatus.stalled: 'stalled'>`

Then fixed by arming stall path correctly (alive PID + clock advance past threshold).

## Results
- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅
- `uv run pytest tests/integration/daemon_chaos/test_agent_stall_recovery.py -v --no-cov` ✅ (4 passed)
- `uv run pytest tests/integration/daemon_chaos/test_agent_stall_recovery.py -v` ⚠️ tests pass, but command exits non-zero due repository-wide coverage fail-under in single-file runs.

## Notes
From `docs/IW_AI_Core_Daemon_Design.md`: stall policy is split between soft-stall (`step_stalled`) and hard-stall kill/fail path. Runtime code currently uses hard-stall at `heartbeat_age > 2 * stall_threshold`, then marks `StepRun/WorkflowStep` failed so fix-cycle/retry can take over; `WorkItem` remains `in_progress` in this layer.

Boundary behavior (`IW_CORE_STALL_THRESHOLD=0`): harness rejects `inject_agent_stall_after_seconds(0)`; monitor path with threshold=0 immediately takes hard-stall kill/fail path on first advanced tick.
