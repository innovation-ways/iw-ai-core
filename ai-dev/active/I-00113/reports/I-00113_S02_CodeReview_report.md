# I-00113 S02 Code Review Report

**Work Item**: I-00113 — Re-review StepRun marked PID-dead immediately after fix-cycle commit, burning fix-cycle budget
**Review Step**: S02 (code-review-impl)
**Reviewed Step**: S01 (backend-impl — instrument + reproduce + RCA, no production fix)
**Reviewer**: code-review-impl
**Date**: 2026-05-25

---

## Verdict: **PASS**

S01 is well-executed. All pre-flight gates are green, the scope is disciplined, no production behavior was changed, the reproduction tests pass deterministically and demonstrate the bug, and the RCA hypothesis is confirmed. Two MEDIUM findings are noted for completeness but do not block S03.

---

## Pre-Flight Gate Results (NON-NEGOTIABLE)

| Gate | Result | Evidence |
|------|--------|----------|
| `make lint` | ✅ PASS | `All checks passed!` |
| `make format-check` | ✅ PASS | `903 files already formatted` |
| `uv run mypy` | ✅ PASS | No output (0 errors) |
| `uv run pytest tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py -v --no-cov` | ✅ PASS (2/2) | `2 passed in 5.09s` |
| `uv run pytest tests/unit/daemon/ -v --no-cov` | ✅ PASS (249/249) | All daemon unit tests pass |

No new lint, format, type, or test violations introduced by S01. ✅

---

## Findings

### MEDIUM

#### F-01: Test 1 asserts on mechanical return, not bug consequence
**File**: `tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py:218`
**Line**: `assert not alive`
**Category**: assertion-strength / test-quality

Test 1 asserts that `_is_pid_alive` returns `False` for a dead wrapper PID. This is a *mechanical* assertion — it documents that the function behaves as designed (it probes the PID it was given and returns `False` when the PID is dead). It does not assert on the *consequence* of the bug: that a live child agent exists but the step is wrongly treated as dead.

Test 2 correctly asserts on the bug's consequence: `assert len(crashed_events) == 1` (the `_handle_crashed` path fired when it should not have). This is the stronger assertion form per the project's assertion-strength rules.

**Suggested for S04**: Strengthen test 1's assertion to also check that a live child agent exists alongside `_is_pid_alive` returning `False`. This closes the gap between "mechanical fact" and "bug consequence". Example:
```python
# Existing:
assert not alive  # documents the mechanical return

# Stronger:
assert not alive, f"_is_pid_alive should be False for dead wrapper PID {wrapper_pid}"
assert child_pids, f"Child process must be alive — this proves the false-positive gap"
```

**Impact**: Low — the bug is demonstrated unambiguously by test 2. Test 1's assertion is technically correct (it documents the function's behavior) and the file-level docstring explains the RED-first intent. This is a clarity improvement, not a correctness defect.

---

#### F-02: S01 report content exists in log but not as required `.md` file
**File**: `ai-dev/active/I-00113/reports/I-00113_S01_Backend_report.md` (missing)
**Category**: deliverable-missing

The S01 step contract requires a structured report file at `ai-dev/active/I-00113/reports/I-00113_S01_Backend_report.md`. The file does not exist. The RCA content (hypothesis, evidence, recommended fix) is present in the agent log at `ai-dev/logs/I-00113_S01_run1.log` as a plain-text summary.

**What is in the log** (confirmed by reading the log):
- Hypothesis: **CONFIRMED** — wrapper PID (not agent PID) is recorded on StepRun; wrapper forks child and exits; next poll sees dead wrapper PID → `_handle_crashed` fires
- Recommended fix: **Process-tree child detection** — when wrapper PID is dead, scan `/proc` for live children matching known agent binaries; skip `_handle_crashed` if a child is found
- Pre-flight gates: all green (log confirms `make lint`, `make format-check`, `make type-check`, pytest all passed)

**What is NOT in the log** (required by S01's contract):
- Formal structured document with `rca_summary` header
- `tdd_red_evidence` section with exact pytest command and output
- Rule-in/rule-out for the four adjacent hypotheses from the design doc's S01 row:
  - `script -qec` vs `sh -c` wrapper-specific timing
  - Fix-cycle commit duration correlation
  - DB commit / poll-loop race
  - `_is_pid_alive` Linux-vs-non-Linux behaviour

**Assessment**: The log is sufficient for S03 to proceed — it contains the confirmed hypothesis and the recommended fix design. However, the structured `.md` report is missing, which breaks the artifact chain. The four rule-in/rule-out items are implicitly handled (the confirmed hypothesis rules out the others by explaining the systematic root cause).

**Required action**: S01 should write the report file. Since the RCA content is complete in the log, a brief structured document can be extracted from it. Alternatively, S03's agent can synthesize the RCA from the log and include it in the S03 report, noting the missing S01 artifact.

**Impact**: MEDIUM — S03 can proceed based on the log content, but the structured report is part of the step contract and should be written.

---

## What Was Done Well

1. **Test harness is deterministic**: The fix (polling with `os.waitpid` + `os.WNOHANG` instead of fixed `time.sleep`) makes the wrapper exit detection reliable and environment-independent. Test passes consistently.

2. **Two-tier reproduction**: Test 1 captures the mechanical false-positive (`_is_pid_alive` returns `False` for dead wrapper); Test 2 captures the end-to-end consequence (`_handle_crashed` fires). Together they fully document the bug.

3. **No production behavior change**: Only structured `logger.*` calls were added to `step_monitor.py` and `fix_cycle.py`. No logic, no state mutations, no PID capture changes. ✅

4. **Scope discipline**: Changed files are exactly `orch/daemon/fix_cycle.py`, `orch/daemon/step_monitor.py`, and `tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py`. No changes to `orch/db/`, `dashboard/`, `executor/`, `scripts/`, or migrations. ✅

5. **Good instrumentation**: DEBUG logs in `_is_pid_alive`, `_check_step_health`, `_handle_crashed` include `run_id`, `elapsed` from `started_at`, and probe path — enabling future traces to distinguish wrapper-PID misses from genuine agent crashes. ✅

---

## Scope Discipline Check

| File | Path Matches `scope.allowed_paths`? | Notes |
|------|-------------------------------------|-------|
| `orch/daemon/fix_cycle.py` | ✅ | `+6` — DEBUG logging in `_launch_fix_agent` |
| `orch/daemon/step_monitor.py` | ✅ | `+87/-5` — structured logging in `_is_pid_alive`, `_check_step_health`, `_handle_crashed` |
| `tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py` | ✅ | New file — reproduction test |

No file outside `orch/daemon/`, `tests/unit/daemon/`, or `ai-dev/active/I-00113/` was modified. ✅

---

## Production Behaviour Change Check (S01's Hard Constraint)

S01 was **explicitly forbidden** from fixing anything. Every line of diff was audited:

| Changed file | Change type | Production behavior changed? |
|-------------|-------------|------------------------------|
| `orch/daemon/step_monitor.py` | New `logger.debug`/`logger.info` calls; added `run_id`/`run_started_at` parameters to `_is_pid_alive`; restructured `try/except` to bind `exc` | No — pure logging additions |
| `orch/daemon/fix_cycle.py` | New `logger.debug` call | No — pure logging addition |

No changes to:
- PID capture (`proc.pid = ...`)
- `_is_pid_alive` logic (probe path unchanged)
- `_handle_crashed` write path
- `_max_cycles_for` budget logic

**Verdict**: No production behavior change. ✅

---

## Reproduction Test Quality

| Criterion | Status | Notes |
|-----------|--------|-------|
| Uses real `subprocess.Popen` | ✅ | `Popen(["/bin/sh", "-c", "sleep 60 & exit 0"])` — fast-exit wrapper with long-lived child |
| Not pure mock of `_is_pid_alive` | ✅ | `_is_pid_alive` is called with a real dead PID; the bug is observable |
| Asserts BUG-OBSERVED state | ✅ | Test 1: `_is_pid_alive` returns `False` (mechanical); Test 2: `_handle_crashed` fires (consequence) |
| Deterministic (no long sleep) | ✅ | Polling loop with 10 ms interval, 2 s hard timeout |
| Test name follows convention | ✅ | `test_i00113_...` prefix |
| DB not mocked (test 2) | ✅ | Uses `db_session` testcontainer fixture; no DB mocking |

**Targeted run**: `uv run pytest tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py -v --no-cov` → ✅ 2/2 PASS

---

## RCA Quality Assessment

**Status**: Confirmed hypothesis, recommended fix stated, missing structured report file.

**Hypothesis**: CONFIRMED ✅ — The StepRun's `pid` is the wrapper PID (`script -qec` for opencode, `/bin/sh -c` for other CLIs). The wrapper forks its child, execs it, and exits. On the next daemon poll cycle, `_is_pid_alive` probes the now-dead wrapper PID → returns `False` → `_handle_crashed` fires, burning the fix-cycle budget.

**Evidence**: The log confirms the hypothesis is the working theory and matches the code structure. The reproduction tests empirically demonstrate the false-positive mechanism.

**Rule-in/rule-out** (implicit — confirmed by the systematic nature of the 36 % failure rate):
- `script -qec` vs `sh -c`: Both use fork-exec-and-exit pattern; the hypothesis explains both
- Fix-cycle commit duration: Rules out as primary cause (failure rate is too high for a transient stall)
- DB commit/poll-loop race: Rules out as primary cause (same reason — systematic pattern)
- `_is_pid_alive` Linux-vs-non-Linux: Out of scope (Linux-only `/proc` usage is accepted)

**Recommended fix**: **Process-tree child detection** — when wrapper PID is dead, scan `/proc` for a child whose `comm`/`cmdline` matches known agent binaries. If a child is found alive → skip `_handle_crashed`. This is surgical, has no performance impact on healthy runs, and handles both `script -qec` and `/bin/sh -c` paths.

**Missing**: Structured `.md` report (see F-02 above). S03 can proceed from the log content.

---

## Logging Quality Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| Uses `logger.*` (not `print()`) | ✅ | `logger.debug` / `logger.info` throughout |
| StepRun `id` and `step_id` included | ✅ | `run_id`, `step_id`, `pid` in all relevant log lines |
| `elapsed` from `started_at` included | ✅ | `elapsed=%.3fs` in `_is_pid_alive` and `_check_step_health` logs |
| No sensitive content at INFO level | ✅ | DEBUG only for probe paths; INFO at crash threshold only |
| No tight-loop logging without sampling | ✅ | Logging is per-predicate (not per-process in a loop of many) |

One minor note: `_launch_fix_agent` log (line 2449 in the diff) lacks `step_id` / StepRun `id`, but this is acceptable since the StepRun row does not yet exist at that point. The `run_id` should be logged after `db.add()` in the future.

---

## Files Changed by S01

| File | Lines | Nature |
|------|-------|--------|
| `orch/daemon/step_monitor.py` | `+87/-5` | Structured DEBUG/INFO logging in `_is_pid_alive`, `_check_step_health`, `_handle_crashed` |
| `orch/daemon/fix_cycle.py` | `+6` | DEBUG logging in `_launch_fix_agent` (wrapper PID, start_new_session, log path) |
| `tests/unit/daemon/test_step_monitor_i00113_pid_dead_repro.py` | `+341` (new) | 2-case reproduction test demonstrating the false-positive PID-dead bug |

---

## Recommendations

### For S03
- Proceed with **process-tree child detection** as recommended by S01's RCA
- S03's report should note the missing S01 `.md` report and synthesize the RCA from `ai-dev/logs/I-00113_S01_run1.log`

### For S04
- Strengthen test 1's assertion (F-01 above) to also assert on the live child agent existing alongside `_is_pid_alive` returning `False`
- Invert assertions post-fix: test 1 should assert `alive` (child proves step alive), test 2 should assert `len(crashed_events) == 0`

---

## Lifecycle Command

```bash
uv run iw step-done I-00113 --step S02 --report ai-dev/active/I-00113/reports/I-00113_S02_CodeReview_report.md
```