# F-00089_S03_Backend_prompt

**Work Item**: F-00089 -- Daemon chaos / fault-injection test layer
**Step**: S03
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations added or applied. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status F-00089 --json` — runtime step state.
- `ai-dev/work/F-00089/F-00089_Feature_Design.md` — Design document (AC3, Invariants 3 + 6, Boundary Behavior "Fix-cycle cap = 1").
- `ai-dev/work/F-00089/reports/F-00089_S01_Backend_report.md` — Harness API (`inject_fix_cycle_always_fails()` hook).
- `tests/integration/daemon_chaos/harness.py` + `conftest.py`.
- CR-00060 (Hypothesis property tests on state machines) — the state-machine-level proof; this step is its runtime complement.

## Output Files

- `ai-dev/work/F-00089/reports/F-00089_S03_Backend_report.md` — Step report.

## Context

You are implementing **S03: Scenario 2 — fix-cycle cap exhaustion**. The harness's `inject_fix_cycle_always_fails()` hook forces CodeReview to return `verdict=fail, mandatory_fix_count=1` on every cycle. Your tests prove the daemon honours `MAX_FIX_CYCLE` at runtime — the state-machine invariant was already proved by CR-00060 / P2-CR-B; you prove the daemon implementation honours it.

**Test-only scope.** Do NOT modify production code anywhere.

## Requirements

### 1. Create `tests/integration/daemon_chaos/test_fix_cycle_cap_exhaustion.py`

Tests required:

- `test_fix_cycle_count_equals_cap_exactly` — arm injection; advance daemon through cycles; assert `WorkItem.fix_cycle_count == MAX_FIX_CYCLE` exactly (never `< MAX_FIX_CYCLE`, never `> MAX_FIX_CYCLE`).
- `test_item_is_terminal_failed_at_cap` — same scenario; assert WorkItem.status is a terminal-failed state at exactly the cap.
- `test_no_further_fix_attempts_after_cap` — assert no new fix-cycle DaemonEvent rows are created after the cap is reached (count before/after additional poll cycles).
- `test_daemon_picks_next_item_after_failure` — batch with [failing item, pickable item]; advance until failing item caps out; assert pickable item gets picked on the next poll cycle (proving daemon did not crash or stall).
- `test_cap_is_one_edge_case` — boundary-behavior row: monkeypatch `MAX_FIX_CYCLE=1`; assert exactly one CodeReview attempt + one fix attempt, terminal-fail at cycle 1, never cycle 2.

### 2. Assertion strength

Strong assertions only. Every test must assert against a daemon-mutated DB row or daemon-emitted log/event. The exact value of `MAX_FIX_CYCLE` must come from `orch.config` (the same source the daemon reads from), not a hardcoded literal — that way a config-level change is caught.

### 3. Determinism

No wall-clock dependencies. The harness's hook + `chaos_daemon.advance_one_cycle()` from S01 are the only control flow.

### 4. Follow project conventions

Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`. Strong-assertion rules apply.

## TDD Requirement

Red-Green-Refactor:

1. **RED**: Write `test_fix_cycle_count_equals_cap_exactly` first. Run it (targeted). Confirm it fails for the right reason — `AssertionError` from a count mismatch when the injection is not yet armed correctly. Capture the failing line.
2. **GREEN**: Refine + arm injection until pass.
3. **REFACTOR**: Add remaining tests using shared helpers.

Record the captured RED failure line in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — all must pass.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/daemon_chaos/test_fix_cycle_cap_exhaustion.py -v
```

Only this file. If you uncover a real daemon bug (e.g. cap is honoured at `MAX_FIX_CYCLE + 1` not `MAX_FIX_CYCLE`), `xfail`-pin the test (`strict=True`), file an Incident, and note both in your report's `notes`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Backend",
  "work_item": "F-00089",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/integration/daemon_chaos/test_fix_cycle_cap_exhaustion.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed",
  "tdd_red_evidence": "tests/integration/daemon_chaos/test_fix_cycle_cap_exhaustion.py::test_fix_cycle_count_equals_cap_exactly — AssertionError: <captured RED line>",
  "blockers": [],
  "notes": ""
}
```
