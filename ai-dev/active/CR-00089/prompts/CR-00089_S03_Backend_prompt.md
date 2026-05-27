# CR-00089_S03_Backend_prompt

**Work Item**: CR-00089 -- Fix-Cycle Pipeline Systemic Hardening (I-00113 RCA Follow-up)
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state. Allowed: testcontainers in pytest fixtures, read-only `docker ps/inspect/logs`, `./ai-core.sh` and `make` targets. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00089 --json`
- `ai-dev/active/CR-00089/CR-00089_CR_Design.md` — design (AC3 is this step's success bar)
- `orch/daemon/step_monitor.py` — file to modify (`_check_step_health` function ~line 317)
- `ai-dev/active/I-00113/reports/I-00113_scope_blocked_root_cause_analysis.md` — RCA for context
- `tests/unit/daemon/test_step_monitor_i00113_probe_unit.py` — reference for existing unit test patterns

## Output Files

- `ai-dev/work/CR-00089/reports/CR-00089_S03_Backend_report.md`

## Context

You are implementing **Step 3 of 13** of CR-00089. This step is **independent** of S01/S02 — it only touches `step_monitor.py`.

The I-00113 RC1 fix (commit `23561e95`) added `_probe_for_child()` to detect live child processes before declaring a crash. This step adds the belt-and-suspenders guard: if `step_runs.completed_at IS NOT NULL`, the step already finished cleanly via `iw step-done`, and crash handling must be skipped.

Read `CLAUDE.md` (root + `orch/CLAUDE.md`) before editing.

## Requirements

### 1. Add completed_at guard in _check_step_health (orch/daemon/step_monitor.py ~line 340)

Locate the block after `_probe_for_child` returns False and before the call to `_handle_crashed`. Insert the guard:

```python
if not alive:
    # I-00113: probe child processes before declaring crash.
    if _probe_for_child(run.pid):
        run.pid_alive = True
        run.last_heartbeat = now
        if run.session_file is None:
            _maybe_resolve_pi_session_file(db, run, now)
        if run.session_file is not None:
            _update_token_counts(run)
        return
    # CR-00089: belt-and-suspenders guard — if iw step-done already set
    # completed_at, the step finished cleanly; skip crash handling entirely.
    if run.completed_at is not None:
        return
    _handle_crashed(db, run, project_id, now, project_config)
    return
```

The guard must come AFTER `_probe_for_child` (so the existing RC1 fix is still the primary mechanism) and BEFORE `_handle_crashed`.

### 2. TDD RED-first

Before adding the guard, write a new unit test file `tests/unit/daemon/test_step_monitor_completed_at_guard.py`. The test should:
- Create a mock `StepRun` with `pid=99999` (dead PID), `completed_at=datetime.now(UTC)`, and `pid_alive=True`.
- Patch `_is_pid_alive` to return `False`.
- Patch `_probe_for_child` to return `False`.
- Patch `_handle_crashed` to record whether it was called.
- Call `_check_step_health(db, run, project_id, config)`.
- Assert that `_handle_crashed` was NOT called.

Confirm this test FAILS against the current `step_monitor.py` (before adding the guard). Record the RED output in the step report. Then make it GREEN.

Also add a complementary test that confirms `_handle_crashed` IS still called when `completed_at is None` (regression guard).

### 3. Mirror check: verify _handle_crashed itself does not overwrite completed_at

Read `_handle_crashed` (~line 386). Confirm it sets `run.completed_at = now` only when the run was not already completed. The guard at the call site should prevent `_handle_crashed` from being reached when `completed_at` is set, but verify this is safe regardless.

### 4. Do NOT touch in this step

- `fix_cycle.py` (S02/S04's files).
- `project_registry.py` (S01's file).
- `projects.toml` (S01's file).

## Acceptance Criteria for this step

1. `_check_step_health` returns early (does not call `_handle_crashed`) when `run.completed_at is not None`, `_is_pid_alive` returns False, and `_probe_for_child` returns False (AC3 from design).
2. `_handle_crashed` is still called when `run.completed_at is None` and no child is found (regression guard passes).
3. `make lint && make typecheck` pass.
4. Both new tests pass GREEN.

## Hard Rules

- Allowed paths: `orch/daemon/step_monitor.py`, `tests/unit/daemon/test_step_monitor_completed_at_guard.py`, `ai-dev/work/CR-00089/reports/**`.
- Do NOT modify `_handle_crashed`, `_probe_for_child`, or any other function in `step_monitor.py`.
- The guard must be a single `if run.completed_at is not None: return` — do not add logging or DB writes.

## Result Contract

Emit standard `iw step-done` JSON with:
- `tdd_red_evidence`: short string with test name and failure mode.
- `files_changed`: exact list.
- `tests_added`: new test names.
