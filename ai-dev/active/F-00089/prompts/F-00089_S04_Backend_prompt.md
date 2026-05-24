# F-00089_S04_Backend_prompt

**Work Item**: F-00089 -- Daemon chaos / fault-injection test layer
**Step**: S04
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations added or applied. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status F-00089 --json` — runtime step state.
- `ai-dev/work/F-00089/F-00089_Feature_Design.md` — Design document (AC4, Boundary Behavior "Stall threshold = 0").
- `ai-dev/work/F-00089/reports/F-00089_S01_Backend_report.md` — Harness API (`inject_agent_stall_after_seconds(seconds)`).
- `tests/integration/daemon_chaos/harness.py` + `conftest.py`.
- `orch/config.py:222` — `IW_CORE_STALL_THRESHOLD` definition.
- `orch/daemon/step_monitor.py` (or whatever module contains the stall-detection logic — read the daemon package to confirm).

## Output Files

- `ai-dev/work/F-00089/reports/F-00089_S04_Backend_report.md` — Step report.

## Context

You are implementing **S04: Scenario 3 — agent stall recovery**. The harness fast-forwards an agent's `last_heartbeat` past `IW_CORE_STALL_THRESHOLD`. Use the harness fixture to override the threshold to a small value (1–5 seconds) so the wall-clock cost is bounded, and use the harness's clock-shim (NOT `time.sleep`) to advance perceived time.

**Test-only scope.** Do NOT modify production code anywhere.

## Requirements

### 1. Create `tests/integration/daemon_chaos/test_agent_stall_recovery.py`

Tests required:

- `test_stalled_agent_is_detected` — arm stall injection; advance daemon's stall-detection pass; assert the step's status transitions to `stalled` and the harness recorded a "kill called" event (or the agent PID no longer exists, depending on how the daemon implements kill).
- `test_stalled_agent_step_recorded` — assert a DaemonEvent or similar audit row records the stall with the agent PID and the elapsed-since-heartbeat duration.
- `test_stall_policy_routing` — after stall is detected, assert the item's downstream state matches the **documented stall policy** in `docs/IW_AI_Core_Daemon_Design.md` (either a retry is scheduled or the item transitions to terminal-failed). Look up the policy in the design doc before writing the assertion. If the design doc is silent or ambiguous, flag this as a finding in your step report `notes` and assert whichever path the daemon actually takes — but document the gap.
- `test_stall_threshold_zero_boundary` — boundary-behavior row: set `IW_CORE_STALL_THRESHOLD=0` via fixture override. If the harness rejects this config (per S01's design), assert the rejection path. If the harness accepts it, assert that every running agent is flagged immediately (and document this behaviour explicitly to prevent test flake).

### 2. Assertion strength

Every test must include at least one positive assertion against a daemon-mutated DB row or daemon-emitted event row. Do not assert only "the hook fired".

### 3. Determinism

No `time.sleep` > 5s. The harness's clock-shim is the only way to advance perceived time. Real wall-clock dependencies are forbidden — they cause flakes.

### 4. Follow project conventions

Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`.

## TDD Requirement

Red-Green-Refactor:

1. **RED**: Write `test_stalled_agent_is_detected` first. Run it. Confirm it fails for the right reason (`AssertionError` — the daemon's stall-detection pass does not yet mark the step `stalled` because the injection isn't armed correctly, or the step's status assertion fails). Capture the failing line.
2. **GREEN**: Arm injection + threshold override correctly.
3. **REFACTOR**: Add remaining tests.

Record the captured RED failure line in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — all must pass.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/daemon_chaos/test_agent_stall_recovery.py -v
```

Only this file. If you uncover a real daemon bug, `xfail`-pin (`strict=True`), file an Incident, note in `notes`.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "Backend",
  "work_item": "F-00089",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/integration/daemon_chaos/test_agent_stall_recovery.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "4 passed, 0 failed",
  "tdd_red_evidence": "tests/integration/daemon_chaos/test_agent_stall_recovery.py::test_stalled_agent_is_detected — AssertionError: <captured RED line>",
  "blockers": [],
  "notes": "Document the documented stall policy you found in IW_AI_Core_Daemon_Design.md, and any ambiguity uncovered."
}
```
