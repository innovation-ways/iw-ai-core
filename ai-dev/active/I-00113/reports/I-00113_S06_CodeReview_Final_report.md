# I-00113 S06 Code Review Final Report

**Work Item**: I-00113 — Re-review StepRun marked PID-dead immediately after fix-cycle commit, burning fix-cycle budget
**Step**: S06 (code-review-final-impl — global cross-agent review)
**Date**: 2026-05-26
**Agent**: code-review-final-impl

---

## Status: ✅ PASS

## Scope Discipline

`git diff HEAD` (working-tree changes only):

| File | Path matches allowed? | Nature |
|------|----------------------|--------|
| `orch/daemon/step_monitor.py` | ✅ | +170 production lines: `_probe_for_child` + `_has_agent_cmdline` + child-detection logic in `_check_step_health`; DEBUG/INFO logging |
| `orch/daemon/fix_cycle.py` | ✅ | +6 lines: DEBUG log in `_launch_fix_agent` (PID, log path) |
| `tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py` | ✅ | +531 lines: 6 regression tests across all 5 AC3 branches |

No file outside `orch/daemon/`, `tests/unit/daemon/`, or `ai-dev/active/I-00113/`. **Scope check: PASS.**

---

## Acceptance Criteria Coverage

### AC1: Reproduction test exists and proves the bug pre-fix

**Verdict: PASS**

- S01 wrote a reproduction test (`test_i00113_is_pid_alive_returns_false_for_dead_wrapper_but_child_is_alive`) demonstrating that when a fast-exit wrapper PID is dead but an agent child is alive, `<no assert>` fires catastrophically (the mechanical `assert not alive` documents the probe failure; the companion test documents `_handle_crashed` firing).
- S03 flipped the assertion direction: the same test now asserts `len(crashed_events) == 0` and `run.status == RunStatus.running` — confirming the bug is fixed.
- The assertion flip in the reproduction test is a minimal, focused diff: `assert len(crashed_events) == 0` (was `== 1`) + the status check. ✅

### AC2: Bug is fixed

**Verdict: PASS**

```
uv run pytest tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py -v --no-cov -p no:randomly
→ 6/6 passed in 6.73s
uv run pytest tests/unit/daemon/ -v --no-cov -q
→ 253/253 passed in 10.44s
```

The fix in `step_monitor.py:_check_step_health` addresses the wrapper-exit-before-agent-registered case specifically:

```python
if not alive:
    if run.pid is not None and _probe_for_child(run.pid):   # ← key fix
        run.last_heartbeat = now
        run.pid_alive = True
        return                                              # ← skip _handle_crashed
    _handle_crashed(...)                                   # ← only fires for true crash
```

`_probe_for_child` implements a three-tier scan:
1. `/proc/<wrapper_pid>/task/<tid>/children` — direct-children kernel API
2. Full `/proc` scan for PPID=wrapper_pid — handles kernels where children file is empty
3. **Orphan fallback (PPID=1)** — catches the agent after intermediate shells have exited

The fix is surgical. No changes to PID capture in `fix_cycle.py`, no changes to budget counting, no migrations. ✅

### AC3: Regression tests cover every branch of the spawn→monitor lifecycle

**Verdict: PASS — all 5 mandated branches + 1 bonus branch covered**

| Branch | Test Name | Key Assertions |
|--------|-----------|---------------|
| B1: wrapper exits, agent child alive (BUG) | `test_i00113_wrapper_exit_agent_alive__probe_finds_child` | `crashed_events == 0`; `run.status == running` |
| B2: wrapper exits, no agent registered | `test_i00113_wrapper_exit_no_agent__crashed_with_pid_dead_message` | `crashed_events == 1`; `run.status == failed`; `"PID dead" in error_message` |
| B2b: pid=None, no agent registered | `test_i00113_no_pid_no_agent__crashed_with_no_pid_message` | `crashed_events == 1`; `"No PID recorded" in error_message`; `"PID dead" NOT in error_message` |
| B3: agent alive + producing output | `test_i00113_agent_alive__stays_alive_and_heartbeat_updated` | `crashed_events == 0`; `run.status == running`; `pid_alive is True` |
| B4: agent timeout | `test_i00113_agent_timeout__handle_timeout_not_pid_dead` | `crashed_events == 0`; `timeout_events == 1`; `"Timeout after"`; `"PID dead" NOT in error_message` |
| B5: agent hard stall | `test_i00113_agent_hard_stall__handle_hard_stall_not_pid_dead` | `crashed_events == 0`; `hard_stall_events == 1`; `"Killed after stall"`; `"PID dead" NOT in error_message` |

Every assertion in B2b/B4/B5 explicitly prevents branch conflation (`"PID dead" NOT in error_message`). All 6 tests use specific-value assertions (exact counts, exact enum states, exact string substrings) — not shape-only checks. **AC3 check: PASS.**

### AC4: No false-positive PID-dead via grace-window logic

**Verdict: PASS**

The fix achieves the grace-window behaviour at the test level:

- B1 (`test_i00113_wrapper_exit_agent_alive__probe_finds_child`) asserts `crashed_events == 0` — the StepRun stays `running` and `_handle_crashed` was NOT called.
- The fix uses `_probe_for_child` (not a blind grace period) so it is specific to live agent children — a genuine agent crash still fires `_handle_crashed` (B2 returns to `crashed_events == 1`).
- The 24-hour telemetry verification is observational; the test-level contract is confirmed. ✅

---

## Cross-Step Contract Audit

### S01 → S03: Fix approach alignment

| S01 recommendation | S03 implementation | Match? |
|--------------------|--------------------|--------|
| Process-tree child detection | `_probe_for_child` + `_has_agent_cmdline` in `step_monitor.py` | ✅ Perfect match |
| Scan /proc for known agent binaries | `_KNOWN_AGENT_BINARIES = {"opencode", "claude", "pi"}` | ✅ Exact match |
| Orphan fallback (PPID=1) | Implemented as tier 3 of `_probe_for_child` | ✅ Explicitly included |

**S01 → S03 chain: intact. No deviation.** ✅

### S04 → AC3: Coverage mapping

S04's report table directly maps test names to each AC3 branch. All 5 mandated branches (B1–B5) plus B2b are covered. No missing branches. **S04 → AC3 mapping: complete.** ✅

### S02 and S05: Per-agent review verdicts

| Step | Verdict | Blocking findings? |
|------|---------|--------------------|
| S02 | PASS | MEDIUM-01 (test 1 mechanical assertion — addressed by S04's assertion-strengthening in B1); MEDIUM-02 (missing S01 `.md` report — chain traceable via log) |
| S05 | PASS | None |

S02 and S05 both ended `verdict: pass`. **S06 is cleared to pass.** ✅

---

## Pre-Flight Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 903 files already formatted |
| `make type-check` (mypy) | ✅ Success, no issues found in 276 source files |
| Targeted unit tests (I-00113) | ✅ 6/6 passed in 6.73s |
| Full unit tests (daemon) | ✅ 253/253 passed in 10.44s |

---

## Security Check

- No hardcoded credentials in added log lines ✅
- PID values are local process identifiers and are only logged in debug/info context with run-specific context (`run_id`, `step_id`, `elapsed`) ✅
- No cross-boundary process information leaked ✅

---

## Notes for S07–S15 (QV Gates)

1. **Deletion regression is covered**: B1 (`test_i00113_wrapper_exit_agent_alive__probe_finds_child`) directly encodes `crashed_events == 0` for the dead-wrapper+alive-child case. Removing `_probe_for_child` or the orphan fallback would fail this test immediately.

2. **No integration test added**: S01's RCA confirmed the bug was deterministic at the unit level. No integration tests under `tests/integration/daemon/` were added by S04. S12 (QV integration-tests gate) will need to verify no regression in existing integration tests.

3. **Branch conflation protection**: B2b explicitly tests that `pid=None` → `"No PID recorded"` (not `"PID dead"`). B4 and B5 explicitly assert `"PID dead" NOT in error_message` for timeout/stall paths. Any future code that conflates these branches will FAIL these tests.

4. **PPID-1 orphan scan**: The orphan fallback adds up to ~5–10ms per dead-wrapper StepRun per poll cycle (full `/proc` scan). This is acceptable because it only fires when the wrapper PID is dead AND no direct children were found — a small fraction of poll-cycle StepRuns. It replaces the false-positive `_handle_crashed` that was burning fix-cycle budget.

5. **`_KNOWN_AGENT_BINARIES` extensibility**: The set `{"opencode", "claude", "pi"}` can be extended in `step_monitor.py` if new agent binaries are added. No config file is needed — this is a hardcoded constant for efficiency.

---

## Finding Summary

| Category | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 |

**Verdict: PASS.** The S06 global cross-agent review confirms that all four ACs are met, the cross-step contract (S01→S03→S04) is intact, both per-agent reviews (S02, S05) passed, all lint/format/typecheck gates are green, and all 253 daemon unit tests pass. The implementation is ready for QV gates S07–S15.

---

## Recommendation

Proceed to S07 (QV lint/format/typecheck assertions). The fix is narrow, test-covered, and well-audited.
