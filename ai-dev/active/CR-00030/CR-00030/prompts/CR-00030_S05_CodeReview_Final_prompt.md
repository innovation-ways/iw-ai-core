# CR-00030_S05_CodeReview_Final_prompt

**Work Item**: CR-00030 -- Show remaining time (not end time) on Claude 5h usage slot
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This work item touches no migrations.)

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00030 --json`.
- `ai-dev/active/CR-00030/CR-00030_CR_Design.md`
- `ai-dev/active/CR-00030/CR-00030_Functional.md`
- All step reports under `ai-dev/active/CR-00030/reports/CR-00030_S0[1-4]_*.md`
- All files listed in the implementation reports' `files_changed` (expected: `orch/llm_usage.py`, `tests/unit/test_llm_usage.py` — and ONLY those two).

## Output Files

- `ai-dev/active/CR-00030/reports/CR-00030_S05_CodeReview_Final_report.md`

## Context

This is the final cross-step review before quality gates. The change is small (one helper, one router-side dict key swap, a new test class, and one strengthened assertion), so the review must focus on **completeness against the acceptance criteria** and **scope discipline**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in the changed files → CRITICAL findings.

## Review Checklist

### 1. Completeness vs Design Document

Walk through AC1..AC7 in `CR-00030_CR_Design.md` and confirm each one is satisfied:

| AC | Where to verify |
|----|-----------------|
| AC1 (5h shape `Xh Ym` / `Xm`) | `orch/llm_usage.py::_format_remaining_from_ts` + strengthened test assertion |
| AC2 (7d unchanged) | `_claude_usage` still calls `_format_resets_at` for `seven_day` |
| AC3 (sub-hour minutes only) | helper branch `remaining_s < 3600` |
| AC4 (sub-minute → `"0m"`) | helper branch returning `"0m"` for `0 <= remaining_s < 60` |
| AC5 (expired/missing → None) | helper guard `resets_at <= 0 or remaining_s < 0` |
| AC6 (percentages untouched) | `block_pct` / `week_pct` unchanged in `_claude_usage` |
| AC7 (quality gates pass) | qv-gate steps S06..S10 will run after this — confirm `make test-unit` passes now and `make typecheck` is clean |

A missing AC is a CRITICAL `missing_requirements` entry.

### 2. Scope Discipline

The manifest declares `scope.allowed_paths = ["orch/llm_usage.py", "tests/unit/test_llm_usage.py"]`. Confirm via `git diff --name-only main..HEAD` (or equivalent) that NO other file was modified. Any extra modification — especially under `dashboard/`, `orch/db/`, `orch/cli/` — is a CRITICAL scope violation.

### 3. Cross-Step Consistency

- The helper added in S01 must match the function name imported / referenced in S03's tests. A mismatch (typo, rename) is HIGH.
- The dict shape returned by `_claude_usage()` (`block_pct`, `week_pct`, `block_reset`, `week_reset`) is unchanged. The dashboard router (`dashboard/routers/usage.py`) reads these by name; renaming any key is CRITICAL.
- The footer template (`dashboard/templates/fragments/llm_usage_footer.html`) was NOT edited. Any edit to it is a scope violation; conversely, if the design's intent was met without a template edit, this is correct — confirm by reading the file and observing that `claude_reset` is rendered as a string with no transformation.

### 4. Architecture Compliance

Read `orch/CLAUDE.md`:
- All change is inside `orch/`, no cross-layer leakage.
- No new dependencies in `pyproject.toml`.
- The new helper is private (leading underscore).

### 5. Test Coverage (Holistic)

- The new `TestFormatRemainingFromTs` class covers all branches per the table in S04.
- The strengthened `test_claude_usage_uses_seven_day_from_cache` asserts both the new 5h shape and the unchanged 7d shape.
- No regression in `TestFormatResetsAt`, `TestFormatReset`, `TestNoCcusageRegressions`, `TestNoSqliteRegressions`, MiniMax tests, or cache-TTL tests.

### 6. Security (Cross-Cutting)

- No new I/O, no new HTTP calls, no new file reads, no new env-var lookups. The helper is a pure function. Nothing to flag.

## Test Verification (NON-NEGOTIABLE)

Run **both**:

```bash
make test-unit
make allure-integration
```

If integration tests fail, that is a CRITICAL finding (no integration test changes, but regression net must hold).

## Severity Levels

(Standard table.)

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "CR-00030",
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
