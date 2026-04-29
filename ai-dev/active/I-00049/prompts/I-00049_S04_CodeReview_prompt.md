# I-00049_S04_CodeReview_prompt

**Work Item**: I-00049 — Daemon blocked by synchronous QV baseline gate command pipe deadlock
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Input Files

- `ai-dev/active/I-00049/I-00049_Issue_Design.md` — Design document
- `ai-dev/active/I-00049/reports/I-00049_S03_Tests_report.md` — S03 report
- `tests/unit/test_i00049_gate_command.py` — New test file

## Output Files

- `ai-dev/active/I-00049/reports/I-00049_S04_CodeReview_report.md` — Review report

---

## Context

Review the tests written in S03 for I-00049.

---

## Review Checklist

### 1. Reproduction test — semantic correctness and real coverage

- Does the reproduction test (`test_i00049_run_gate_command_does_not_block_after_timeout`)
  actually spawn a real subprocess that holds the pipe open?
- Is the wall-clock assertion tight enough to catch a regression? (e.g. `< 5 s`)
- Would this test **fail** against the old `subprocess.run(capture_output=True)` code?
- Is the timeout patched to a short value (e.g. 2 s) so CI doesn't wait 300 s?

### 2. Process-group kill test — mock correctness

- Does the mock-based test assert `os.killpg` is called with
  `(pgid, signal.SIGKILL)` — not just that it was called at all?
- Is the mock set up correctly so `communicate(timeout=...)` raises
  `TimeoutExpired` as expected?

### 3. GATE_PARSERS exclusion tests

- Does the test assert `"integration-tests" not in GATE_PARSERS` with a
  meaningful error message (not just `assert False`)?
- Does the test verify the fast gates (lint, typecheck, unit-tests,
  frontend-tests) are still present?

### 4. Normal and error path tests

- Is `test_run_gate_command_returns_stdout_on_success` present and does it
  assert the actual content (e.g. `"hello" in result`), not just non-empty?
- Is the non-zero exit test checking output is returned without raising?

### 5. Isolation and determinism

- Do tests use real subprocesses only where necessary (reproduction test)?
- Are mocks used for the process-group kill test to avoid flakiness?
- No dependency on filesystem state, live DB, or network.

### 6. Test conventions (tests/CLAUDE.md)

- File in `tests/unit/`?
- No testcontainers in unit tests?
- Imports clean and sorted?

---

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make lint
make typecheck
```

---

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00049",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
