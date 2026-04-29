# I-00049_S02_CodeReview_prompt

**Work Item**: I-00049 — Daemon blocked by synchronous QV baseline gate command pipe deadlock
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No database changes in this work item.

---

## Input Files

- `ai-dev/active/I-00049/I-00049_Issue_Design.md` — Design document
- `ai-dev/active/I-00049/reports/I-00049_S01_Backend_report.md` — S01 report
- `orch/daemon/batch_manager.py` — primary changed file
- `orch/daemon/qv_baseline.py` — secondary changed file

## Output Files

- `ai-dev/active/I-00049/reports/I-00049_S02_CodeReview_report.md` — Review report

---

## Context

Review the fix implemented in S01 for the daemon pipe-deadlock bug.

The fix has two parts:
1. `_run_gate_command` in `batch_manager.py`: replaced `subprocess.run` with
   `Popen` + `start_new_session=True` + `os.killpg` on timeout.
2. `GATE_PARSERS` in `qv_baseline.py`: removed `"integration-tests"` entry.

---

## Review Checklist

### 1. Correctness of the process-group kill

- Does `_run_gate_command` use `start_new_session=True` (or equivalent setsid)?
- On `TimeoutExpired`, does it call `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)`?
- Is `ProcessLookupError` caught in case the process already exited?
- After `killpg`, does it call `proc.communicate()` (without timeout) to drain pipes?
- Could this still block? (e.g. if `os.getpgid` raises something other than `ProcessLookupError`)
- Is the return value correct in both the normal-exit and timeout paths?

### 2. No regression on normal exit path

- When the command exits within the timeout, is the combined stdout+stderr
  returned correctly?
- Is there any chance of double-decoding or encoding errors?

### 3. `GATE_PARSERS` change

- Is `"integration-tests"` actually removed (not just commented out)?
- Is there any other place in the codebase that relies on `integration-tests`
  being in `GATE_PARSERS`? (grep for it)
- Does the existing "Unknown gate" warning path in `_compute_qv_baselines`
  handle the removed entry gracefully?

### 4. Code Quality

- Are imports (`os`, `signal`) placed correctly (module-level or function-level)?
- Is there unnecessary complexity or over-engineering?
- Does the fix stay minimal — only the two files mentioned in the design?

### 5. Architecture Compliance

- Read `CLAUDE.md` — does this comply with all daemon conventions?
- The daemon is single-threaded; the fix must not introduce threading.

### 6. Security

- `shell=True` is used — is `# noqa: S602` present on the Popen call?
- Are there any new injection surfaces?

### 7. Testing

- Do existing unit tests in `tests/unit/test_merge_queue.py` and
  `tests/unit/test_merge_queue_migration_pipeline.py` still pass?

---

## Test Verification (NON-NEGOTIABLE)

Run before submitting:
```bash
make test-unit
make lint
make typecheck
```

---

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00049",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
