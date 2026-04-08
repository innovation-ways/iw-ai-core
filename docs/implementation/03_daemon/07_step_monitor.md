# Step 07: Daemon Step Monitor

## Context

Daemon core loop is running. Now implement the step monitoring logic — the most critical daemon function. This is what detects zombies, timeouts, and stalls.

Read these documents:
- `IW_AI_Core_Daemon_Design.md` — section 4.1 (step monitoring), section 7 (timeout configuration)
- `IW_AI_Core_Architecture.md` — section 9 (execution management)

## Task

### 1. Step Monitor (`orch/daemon/step_monitor.py`)

Implement `monitor_running_steps(db, project_id, config)`:

For each `step_run WHERE status='running'` in this project:

**a) PID alive check** (`os.kill(pid, 0)`):
- Alive → update `pid_alive = True`, `last_heartbeat = now()`
- Dead (ProcessLookupError) → mark as failed: "Process exited without reporting completion (PID dead)"
- PermissionError → treat as dead (shouldn't happen, but handle gracefully)
- pid is NULL → mark as failed: "No PID recorded"

**b) Timeout detection** (only if PID alive):
- Calculate elapsed: `now() - started_at`
- If elapsed > `timeout_secs`: send SIGTERM, mark as `timeout`, record `error_message`, `completed_at`, `duration_secs`
- Update parent `workflow_step.status = 'failed'`

**c) Stall detection** (only if PID alive and not timed out):
- Calculate heartbeat age: `now() - last_heartbeat`
- If age > `stall_threshold` (from config, default 600s): mark as `stalled`
- Stalled is a WARNING, not a terminal state — the user decides whether to kill or wait

**d) Emit events** for each state change: `step_timeout`, `step_crashed`, `step_stalled`

### 2. Timeout Resolution (`orch/daemon/step_monitor.py`)

Implement `get_timeout(project_config, step_type) -> int`:

Priority chain:
1. Step-level override (from `workflow_steps.config JSONB`, if present)
2. Project-level override (from `.iw-orch.json` `timeout_overrides`)
3. Platform defaults:
   - implementation: 2700 (45 min)
   - code_review: 1800 (30 min)
   - code_review_fix: 2700 (45 min)
   - code_review_final: 2400 (40 min)
   - code_review_fix_final: 2700 (45 min)
   - quality_validation: 600 (10 min)
   - qv_fix: 1800 (30 min)
   - browser_verification: 900 (15 min)
   - fallback: 1800 (30 min)

### 3. Kill Helper

Implement `kill_process(pid) -> bool`:
- Try `os.kill(pid, signal.SIGTERM)`
- Return True if signal sent
- Catch ProcessLookupError → return False (already dead)
- Log the action

### 4. Tests (TDD)

**Unit tests** (`tests/unit/test_step_monitor.py`) — mock `os.kill`:

- Test: PID alive, within timeout → no action, heartbeat updated
- Test: PID alive, exceeded timeout → SIGTERM sent, status=timeout, error_message set
- Test: PID alive, stalled (heartbeat old) → status=stalled
- Test: PID dead → status=failed, error_message="Process exited..."
- Test: PID is None → status=failed
- Test: timeout resolution priority chain (step > project > platform)
- Test: timeout resolution falls back to platform defaults
- Test: kill_process sends SIGTERM, returns True
- Test: kill_process on dead PID returns False (no exception)

Use `freezegun` for all time-dependent tests. Use `unittest.mock.patch("os.kill")` for all PID checks.

## Acceptance Criteria

- [ ] Monitor detects dead PIDs and marks steps as failed
- [ ] Monitor detects timeouts and sends SIGTERM
- [ ] Monitor detects stalls (alive but no progress)
- [ ] Timeout resolution uses the correct priority chain
- [ ] All tests pass with mocked os.kill (never touches real PIDs)
- [ ] `make test` passes, `make quality` passes
