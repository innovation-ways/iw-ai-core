# I-00112_S04_CodeReview_Backend_prompt

**Work Item**: I-00112 -- Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires
**Step Being Reviewed**: S03 (Backend)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers via pytest fixtures excepted. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. S03 did not touch migrations. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00112 --json`.
- `ai-dev/active/I-00112/I-00112_Issue_Design.md` — design document (read **Root Cause Analysis**, **AC1**, **AC2**, **Notes** on the 500 ms floor).
- `ai-dev/active/I-00112/reports/I-00112_S03_Backend_report.md` — S03 step report.
- All files listed in S03's `files_changed`.

## Output Files

- `ai-dev/active/I-00112/reports/I-00112_S04_CodeReview_report.md` — review report.

## Context

You are reviewing S03 (Backend). The step refactored `fire_claude` to return a `FireResult` dataclass capturing stdout/stderr/elapsed_ms/returncode, refactored the poller to apply the stricter success contract (`rc==0 AND non-empty stdout AND elapsed >= 500ms`), and updated `_log_run` to persist all four fields.

## Read the Design Document FIRST

- **Acceptance Criteria** — every AC1–AC2 is a mandatory check.
- **Notes** — the 500 ms floor rationale (it must live in a single named constant, not a magic number repeated at the call site).
- **Test to Reproduce** — note the names of the six tests S07 will write; S03 is not expected to write them, but the contract S07 will test against MUST already hold after S03.

The design names no test file in S03's `files_changed`. If S03 added or modified a test file, that is a CRITICAL scope violation.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violation in S03's `files_changed` is a CRITICAL finding.

## Review Checklist

### 1. Contract correctness (the heart of this incident)

- `FireResult.is_success` returns `True` iff ALL three: `returncode == 0` AND `stdout.strip() != ""` AND `elapsed_ms >= _MIN_SUCCESS_ELAPSED_MS`. Any short-circuit, missing condition, or off-by-one is **CRITICAL** — this is the entire fix.
- The 500 ms floor lives in a single module-level constant (`_MIN_SUCCESS_ELAPSED_MS`). A magic `500` literal anywhere else in the diff is HIGH.
- `_fire_slot` consumes `result.is_success`, not `result.returncode == 0`. A direct returncode check is the bug class returning — CRITICAL.
- A silent no-op (rc=0, empty stdout) triggers the existing single retry. Skipping the retry for the no-op branch is HIGH (regression vs prior behaviour on the rc!=0 branch).
- TimeoutExpired and FileNotFoundError are reflected as `returncode=-1` with the diagnostic in `stderr`. Returning `is_success=True` for either is CRITICAL.

### 2. Persistence

- `log_run` writes stdout/stderr/elapsed_ms/returncode on **every** invocation — success and failure. A code path that omits them (NULL on success, populated on failure, or vice versa) is HIGH.
- The new arguments are keyword-only on `log_run`. Positional acceptance of stdout/stderr is MEDIUM (fixable) — protects against future call-site bugs.

### 3. Elapsed timing

- `time.perf_counter` is used (monotonic, jump-safe). `time.time()` or `datetime.now()` would be HIGH (jumps on NTP corrections produce nonsense elapsed_ms).
- Elapsed is captured **inside** both the try block and every except block, so timeout/missing-binary errors carry a real elapsed_ms (typically ≈ timeout for TimeoutExpired). Missing elapsed capture in any branch is MEDIUM (fixable).

### 4. Logging

- The new INFO log line carries rc, elapsed_ms, and stdout_len (NOT raw stdout — could be multi-line and pollute logs). Logging raw stdout is MEDIUM (fixable).
- `%`-format style for the logger (`logger.info("…%s…", a, b)`), not f-string. f-strings are HIGH because they break log aggregation and `make lint` G004.

### 5. Scope adherence

- S03's `files_changed` MUST contain exactly two paths: `orch/keep_alive_service.py` and `orch/daemon/keep_alive_poller.py`. Any other file (model, migration, template, test) is a CRITICAL scope violation.
- Existing tests that broke (because they mocked the old `(bool, error)` shape) MUST NOT be silently rewritten by S03 — they are S07's RED evidence. Rewritten tests in this step are CRITICAL.

### 6. Project conventions

- PEP 604 unions everywhere (`str | None`), not `Optional[str]`.
- Frozen dataclass with `slots=True` for `FireResult`.
- `import time` at module top, not local.

### 7. TDD RED evidence (Backend = behaviour-implementing)

1. Confirm `tdd_red_evidence` is present and plausible — must reference a real test id and a real failure line (the existing tests broken by the signature change). An `ImportError` or `SyntaxError` quoted as RED evidence is HIGH.
2. Reason about whether the existing test would actually have failed against the new code — yes it should, because the old test mocks `fire_claude` to return a tuple and the new code expects a `FireResult`. A `tdd_red_evidence` value that doesn't match this failure mode is HIGH.

## Test Verification (NON-NEGOTIABLE)

Run:
```bash
uv run pytest tests/unit/test_keep_alive_service.py tests/unit/test_keep_alive_poller.py -v
```

Existing tests breaking with the contract change is **expected**. Report the exact failure count under `test_summary`. Do NOT run `make test-unit` / `make test-integration` here — they are S16/S17.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Contract incorrect, persistence missing, scope violation, rewrote S07's tests |
| **HIGH** | Magic number duplicated, retry skipped for no-op, f-string log line, returncode used instead of is_success |
| **MEDIUM (fixable)** | Logging raw stdout, missing elapsed in error branch, positional new args |
| **MEDIUM (suggestion)** | Better naming, helper extraction |
| **LOW** | Nitpicks |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00112",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": false,
  "test_summary": "<n> failed (existing tests broken by contract change — expected; S07 will rewrite)",
  "notes": "Confirmed _MIN_SUCCESS_ELAPSED_MS = 500 is the only floor literal; FireResult.is_success applies all three conditions."
}
```

## Lifecycle Commands

```bash
uv run iw step-start I-00112 --step S04
uv run iw step-done I-00112 --step S04 --report ai-dev/active/I-00112/reports/I-00112_S04_CodeReview_report.md
```
