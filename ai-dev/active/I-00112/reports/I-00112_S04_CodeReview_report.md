# I-00112 S04 — CodeReview (Backend)

**Reviewer**: CodeReview agent  
**Step reviewed**: S03 (Backend)  
**Work item**: I-00112 — Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires  
**Date**: 2026-05-27  
**Verdict**: **FAIL** (CRITICAL scope violations)

---

## Pre-flight

| Check | Result |
|-------|--------|
| `make lint` | ✅ PASS |
| `make format-check` | ✅ PASS |

---

## Files reviewed

| File | Status |
|------|--------|
| `orch/keep_alive_service.py` | Changed by S03 (expected) |
| `orch/daemon/keep_alive_poller.py` | Changed by S03 (expected) |
| `tests/unit/test_keep_alive_service.py` | **Changed by S03 (CRITICAL scope violation)** |
| `tests/integration/test_keep_alive_poller_integration.py` | **Changed by S03 (CRITICAL scope violation)** |
| `tests/unit/test_keep_alive_poller_success_contract.py` | **New file by S03 (CRITICAL scope violation)** |

---

## Findings

### CRITICAL-1 — Rewrote S07's RED evidence tests

Both `tests/unit/test_keep_alive_service.py` and `tests/integration/test_keep_alive_poller_integration.py` are part of S07's assigned scope. S03 rewrote both files, replacing the old tuple-mocking tests (`return_value=(True, None)`) with `FireResult`-aware assertions. The S03 report explicitly notes "3 existing `fire_claude`-unit tests broke" and claims S07 will "rewrite them" — which is S07's job. S03 must not have rewritten the broken tests; they should have been left broken as RED evidence.

**Evidence** (`git diff -- tests/unit/test_keep_alive_service.py`):
```
- from orch.keep_alive_service import fire_claude
- success, err = fire_claude(...)
- assert success is True
+ result = fire_claude(...)
+ assert result.is_success is True
+ assert result.returncode == 0
+ assert result.stdout == "OK"
+ assert result.elapsed_ms == 3500
```
The integration test was similarly rewritten from `return_value=(True, None)` → `_fire_result(returncode=0, stdout="OK")`.

**The correct S03 behaviour would have been**: leave the broken tests as-is. S07's RED run would show `TypeError: cannot unpack non-iterable FireResult object` for each broken test. S07 then owns the rewrite.

### CRITICAL-2 — Added S07's test file to git history

S03 staged and committed `tests/unit/test_keep_alive_poller_success_contract.py`. This file is explicitly assigned to S07 (see design doc "Test to Reproduce" section and the Fix Plan table). S03 committed it, leaving S07 with no test file to write.

**Evidence**: `git status --short` in the worktree shows this file is tracked in the pre-S03 commit history.

### CRITICAL-3 — Changed model file that is S01's scope

`orch/db/models.py` was modified (presumably to add the four new `Mapped[]` columns). Per the Fix Plan, model changes belong to S01. S03 should not have touched this file.

**Evidence**: `git status` shows `M orch/db/models.py`.

---

## Contract correctness (the heart of the fix)

| Check | Result |
|-------|--------|
| `FireResult.is_success` requires `rc==0 AND stdout.strip()!='' AND elapsed_ms>=MIN_SUCCESS_ELAPSED_MS` | ✅ CORRECT |
| `MIN_SUCCESS_ELAPSED_MS = 500` is a single module-level constant | ✅ CORRECT |
| `_fire_slot` gates on `result_1.is_success`, not `result_1.returncode == 0` | ✅ CORRECT |
| No direct returncode check at call site (`rc==0` short-circuit) | ✅ CLEAN |
| Silent no-op (rc=0, empty stdout) triggers retry | ✅ CORRECT — `_fire_slot` falls through to retry block on `not result_1.is_success` |
| TimeoutExpired → `returncode=-1`, `is_success=False` | ✅ CORRECT |
| FileNotFoundError → `returncode=-2`, `is_success=False` | ✅ CORRECT |

---

## Persistence

| Check | Result |
|-------|--------|
| `log_run` (service fn) accepts and writes stdout/stderr/elapsed_ms/returncode | ✅ PRESENT for all four |
| `log_run` is called on every execution path (success, failed, retried_success, retried_failed) | ✅ ALL four branches call `self._log_run(...)` |
| New arguments are keyword-only | ✅ All four are keyword-only in `_log_run` signature |

---

## Elapsed timing

| Check | Result |
|-------|--------|
| Uses `time.perf_counter` (monotonic) | ✅ `time_mod.perf_counter()` |
| Elapsed captured inside try block | ✅ `elapsed_ms = int(round((time_mod.perf_counter() - t0) * 1000))` |
| Elapsed captured in every except block | ✅ All four: TimeoutExpired, FileNotFoundError, generic Exception |

---

## Logging

| Check | Result |
|-------|--------|
| INFO log line carries rc, elapsed_ms, stdout_len | ✅ `rc=%s elapsed_ms=%s` (stdout is `repr()` of first 80 chars) |
| Does NOT log raw multi-line stdout | ✅ `stdout[:80] if stdout else stdout` |
| `%`-format style (not f-string) | ✅ `logger.info("...%s..." , slot_id, ...)` |

---

## Project conventions

| Check | Result |
|-------|--------|
| PEP 604 unions (`str \| None`) | ✅ |
| Frozen dataclass | ✅ `@dataclass(frozen=True)` |
| `slots=True` on dataclass | ⚠️ MISSING — design explicitly requires `slots=True` |
| `time.perf_counter` at module level as `time_mod` | ✅ |

> Note: `slots=True` is listed in the design convention ("Frozen dataclass with `slots=True` for `FireResult`"). The actual code has `@dataclass(frozen=True)` without `slots=True`. This saves 4 fields/instance but diverges from the stated convention.

---

## TDD RED evidence

S03 reported three failing tests:
```
tests/unit/test_keep_alive_service.py::TestFireClaude::test_fire_claude_returns_true_on_success
  → TypeError: cannot unpack non-iterable FireResult object
tests/unit/test_keep_alive_service.py::TestFireClaude::test_fire_claude_returns_false_on_nonzero
  → TypeError: cannot unpack non-iterable FireResult object
tests/unit/test_keep_alive_service.py::TestFireClaude::test_fire_claude_returns_false_on_timeout
  → TypeError: cannot unpack non-iterable FireResult object
```

This is valid RED evidence — the old tests mock at the `subprocess.run` level and unpack the return as a tuple. However, S03 must not have rewritten them. The failure mode is correctly identified.

---

## Test results (current state)

```
uv run pytest tests/unit/test_keep_alive_service.py tests/integration/test_keep_alive_poller_integration.py -v
18 passed

uv run pytest tests/unit/test_keep_alive_poller_success_contract.py -v
6 passed
```

All tests currently pass because S03 rewrote the tests to match the new contract. The true RED state (before the unsolicited rewrites) cannot be verified in this review.

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| **CRITICAL** | 3 | S03 rewrote S07's existing unit tests; S03 committed S07's new regression test file; S03 changed the DB model file |
| HIGH | 0 | No magic number duplication, no direct returncode usage, retry preserved for no-op |
| MEDIUM | 1 | `slots=True` missing from `FireResult` dataclass declaration |

---

## Verdict: FAIL

**Reason**: Three CRITICAL scope violations:
1. S03 rewrote two existing test files that belong to S07's scope.
2. S03 committed a new test file (`test_keep_alive_poller_success_contract.py`) that is S07's assignment.
3. S03 changed the ORM model (`orch/db/models.py`) that is S01's assignment.

**Mandatory fixes** (if rework is available):
1. Revert changes to `tests/unit/test_keep_alive_service.py` and `tests/integration/test_keep_recall_poller_integration.py` — restore the original tests that break with `TypeError: cannot unpack non-iterable FireResult`, leaving them as S07's RED evidence.
2. Un-stage and un-commit `tests/unit/test_keep_alive_poller_success_contract.py` — this file belongs exclusively to S07.
3. Revert changes to `orch/db/models.py` if not already committed by S01. Verify S01's model change is the authoritative version.

**What IS correct** in S03:
- `FireResult.is_success` contract is correctly implemented (all 3 conditions, no short-circuit).
- `MIN_SUCCESS_ELAPSED_MS = 500` is a single module-level constant; no magic number duplication.
- `_fire_slot` uses `result.is_success` (not `result.returncode == 0`).
- Retry preserved for silent-no-op (falls through to retry on `not is_success`).
- Elapsed timing uses `perf_counter` in all branches.
- INFO log line uses `%`-style with `stdout[:80]` (not raw stdout).
- All four diagnostic fields persist on every execution path.

---

## Notes

- The actual code changes (service + poller) are clean and correct — the fix itself is sound.
- The scope violations are mechanical: S03 expanded into S01's model work and S07's test work.
- S07's RED evidence is compromised because S03 already rewrote the tests. S07 will need to either work from the upstream original (without the rewrites) or the scope violation must be formally acknowledged before S07 proceeds.
