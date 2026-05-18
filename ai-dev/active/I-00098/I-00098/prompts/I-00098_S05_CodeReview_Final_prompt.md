# I-00098_S05_CodeReview_Final_prompt

**Work Item**: I-00098 -- Keep-alive scheduler re-fires successful slots around UTC midnight (TZ mismatch in `get_due_slots`)
**Review Step**: S05 (Final / Global Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Standard policy. Read-only introspection only.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item touches no migrations; any migration file in the per-step `files_changed` is CRITICAL scope violation.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00098 --json`
- `ai-dev/active/I-00098/I-00098_Issue_Design.md`
- `ai-dev/active/I-00098/I-00098_Functional.md`
- `ai-dev/active/I-00098/reports/I-00098_S01_Backend_report.md`
- `ai-dev/active/I-00098/reports/I-00098_S02_CodeReview_report.md`
- `ai-dev/active/I-00098/reports/I-00098_S03_Tests_report.md`
- `ai-dev/active/I-00098/reports/I-00098_S04_CodeReview_report.md`
- `orch/keep_alive_service.py` (post-fix)
- `tests/integration/test_keep_alive_integration.py` (post-S03)

## Output Files

- `ai-dev/active/I-00098/reports/I-00098_S05_CodeReview_Final_report.md`

## Context

You are the last per-step reviewer before the QV gates. Your job is cross-step consistency — predicate ↔ test, design ↔ code, scope ↔ files actually changed.

## Read the Design Document FIRST

In addition to the standard "read before reviewing" rule:

- **AC1 / AC2 / AC3** — each must trace to specific code or test. AC1 → predicate change in S01. AC2 → named test in S03. AC3 → UTC variant in S03's parametrize set.
- **Impacted Paths** — exactly two paths: `orch/keep_alive_service.py` and `tests/integration/test_keep_alive_integration.py`. Anything else in any step's `files_changed` is CRITICAL.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
uv run ruff check orch/keep_alive_service.py tests/integration/test_keep_alive_integration.py
uv run ruff format --check orch/keep_alive_service.py tests/integration/test_keep_alive_integration.py
```

NEW violations → CRITICAL findings.

## Global Review Checklist

### 1. Predicate ↔ Test Consistency (CRITICAL)

The post-fix predicate in `get_due_slots` must match what the tests assume:

- The fix uses `fired_at >= today_start_local AND fired_at < tomorrow_start_local` (half-open).
- The bug-exposing test seeds a `success` run inside today and expects `[]`.
- A test that seeds a run at, say, `tomorrow_start_local + 1 second` is OUTSIDE the new range and would (correctly) be a no-skip — but if S03 wrote such a case as a "should skip" assertion, the half-open range is wrong OR the test is wrong. Cross-check.

### 2. AC Traceability (HIGH)

Build a small table in your report:

| AC | Code / Test that fulfils it | File |
|----|-----------------------------|------|
| AC1 | New range predicate in `get_due_slots` | `orch/keep_alive_service.py` |
| AC2 | `test_get_due_slots_skips_already_run_slot_across_utc_midnight` | `tests/integration/test_keep_alive_integration.py` |
| AC3 | UTC variant in the tz-offset parametrize set | `tests/integration/test_keep_alive_integration.py` |

If any row is missing or vague → HIGH.

### 3. Scope Adherence (CRITICAL)

Compute the union of `files_changed` across S01..S04 and assert it is a **subset** of:

```
orch/keep_alive_service.py
tests/integration/test_keep_alive_integration.py
```

Plus implicit `ai-dev/active/I-00098/**` (reports). Any path outside this set → CRITICAL scope-violation.

In particular: nobody should have touched `tests/integration/test_keep_alive_poller_integration.py` (I-00090's territory) or any other file under `orch/`.

### 4. No Regression Audit

- `grep -rn 'func\.date' orch/ dashboard/` should return zero results. If S01 left an instance behind, CRITICAL.
- The existing tests `test_poll_logs_success_run`, `test_poll_retry_success_logs_retried_success`, `test_poll_double_failure_logs_retried_failed_with_combined_error`, `test_poll_processes_multiple_slots_independently`, and `test_poll_skips_slot_already_run_today` (in `test_keep_alive_poller_integration.py`) must still pass. Run them:
  ```bash
  uv run pytest tests/integration/test_keep_alive_poller_integration.py -v --no-cov
  ```
  Any failure → HIGH (the design's AC3 is breached).
- The existing tests in `tests/integration/test_keep_alive_integration.py` (pre-S03) must still pass.
- The existing unit tests in `tests/unit/test_keep_alive_service.py` must still pass.

### 5. TDD RED Evidence Audit (HIGH)

Per the design's "S03 owns RED" decision:

- S01's `tdd_red_evidence` must read `"n/a — behavioural regression test added in S03 (tests-impl); production logic change only"` (or close paraphrase). Anything else (especially `tdd_red_evidence: ""`) → HIGH.
- S03's `tdd_red_evidence` must include a per-new-test reasoning entry. Generic copy-paste of `test_summary` → MEDIUM_FIXABLE.

### 6. Functional Doc Consistency (MEDIUM)

- `I-00098_Functional.md` body ≤ 500 words. (Count: `wc -w ai-dev/active/I-00098/I-00098_Functional.md`.) Over 500 → blocking per design-review skill; you must flag MEDIUM_FIXABLE.
- No file paths, no SQL, no code fences in the functional doc. Any → MEDIUM_FIXABLE.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_keep_alive_service.py tests/integration/test_keep_alive_integration.py tests/integration/test_keep_alive_poller_integration.py -v --no-cov
```

All green.

## Severity Levels

Standard table.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00098",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "ac_traceability": {
    "AC1": "<file:line or short justification>",
    "AC2": "<file:line or short justification>",
    "AC3": "<file:line or short justification>"
  },
  "scope_audit": {
    "files_actually_changed": ["..."],
    "allowed_paths": ["orch/keep_alive_service.py", "tests/integration/test_keep_alive_integration.py"],
    "violations": []
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed across unit + 2 integration files",
  "notes": ""
}
```
