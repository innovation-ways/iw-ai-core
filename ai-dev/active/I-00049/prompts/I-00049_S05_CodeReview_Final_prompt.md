# I-00049_S05_CodeReview_Final_prompt

**Work Item**: I-00049 — Daemon blocked by synchronous QV baseline gate command pipe deadlock
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Input Files

- `ai-dev/active/I-00049/I-00049_Issue_Design.md` — Design document
- `ai-dev/active/I-00049/reports/I-00049_S01_Backend_report.md`
- `ai-dev/active/I-00049/reports/I-00049_S02_CodeReview_report.md`
- `ai-dev/active/I-00049/reports/I-00049_S03_Tests_report.md`
- `ai-dev/active/I-00049/reports/I-00049_S04_CodeReview_report.md`
- `orch/daemon/batch_manager.py`
- `orch/daemon/qv_baseline.py`
- `tests/unit/test_i00049_gate_command.py`

## Output Files

- `ai-dev/active/I-00049/reports/I-00049_S05_CodeReview_Final_report.md`

---

## Context

Final cross-agent review of all I-00049 work. Two implementation changes
and a new test file.

---

## Review Checklist

### 1. Completeness vs Design Document

- Both fixes implemented: `_run_gate_command` Popen+killpg AND
  `"integration-tests"` removed from `GATE_PARSERS`?
- All acceptance criteria from the design document met?
  - AC1: `_run_gate_command` returns promptly on timeout
  - AC2: `integration-tests` gate skipped
  - AC3: Reproduction test exists and passes

### 2. Fix Correctness (final sanity check)

- `_run_gate_command`: is `start_new_session=True` present?
- On `TimeoutExpired`: is `os.killpg` called, then `communicate()` drained?
- Can the fix itself block? (e.g. if `os.killpg` fails for unexpected reason)
- `GATE_PARSERS`: is `"integration-tests"` definitively absent?

### 3. Regression Safety

- Do all existing tests in `tests/unit/test_merge_queue.py` and
  `tests/unit/test_merge_queue_migration_pipeline.py` still pass?
- Does removing `"integration-tests"` from `GATE_PARSERS` affect any other
  code path outside `_compute_qv_baselines`? (grep for uses of `GATE_PARSERS`)

### 4. Test Holistic Assessment

- Does the reproduction test provide real confidence (spawns real subprocess)?
- Does the mock-based process-group kill test verify `signal.SIGKILL` specifically?
- Are fast-gate registration tests present?
- Would these tests have caught the original bug in CI?

### 5. Architecture Compliance

- Fix is confined to the daemon layer — no cross-layer changes?
- No threading introduced into the single-threaded daemon loop?

### 6. Security

- `shell=True` noqa annotations in place?
- No new injection surfaces?

---

## Test Verification (NON-NEGOTIABLE)

Run the **full test suite** (both unit AND integration):

```bash
make test-unit
make allure-integration
make lint
make typecheck
```

Report results accurately. Integration test failures are CRITICAL findings.

---

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00049",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
