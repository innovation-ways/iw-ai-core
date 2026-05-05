# CR-00034_S02_CodeReview_prompt

**Work Item**: CR-00034 -- Robust `data-full-text` test assertions using `html.escape`
**Step Being Reviewed**: S01 (tests-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state. (Standard policy. Testcontainer
fixtures in tests are exempt.)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds NO migrations. Verify in your review that no migration files were created.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00034/CR-00034_CR_Design.md` — Design document.
- `ai-dev/work/CR-00034/reports/CR-00034_S01_Tests_report.md` — Implementation report.
- `tests/dashboard/test_i00067_recent_activity_truncation.py` — File under review.

## Output Files

- `ai-dev/work/CR-00034/reports/CR-00034_S02_CodeReview_report.md` — Review report.

## Context

You are reviewing the implementation of CR-00034 by tests-impl in S01.

The change is intentionally tiny: add `import html`, rewrite two assertions on lines (formerly) 95 and 241 to wrap the fixture in `html.escape(..., quote=True)`. **The total diff should be ~5–10 lines, all confined to one file.**

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the changed file:

```bash
make lint
make format
```

Any NEW violation in `tests/dashboard/test_i00067_recent_activity_truncation.py` (relative to main) is a **CRITICAL** finding with `"category": "conventions"`.

## Review Checklist

### 1. Scope discipline (highest priority for this CR)

- The diff MUST be confined to `tests/dashboard/test_i00067_recent_activity_truncation.py`. Any other file changed = **CRITICAL** finding (scope violation).
- The diff MUST contain only: one `import html` addition, plus rewritten lines 95 and 241 (and the local-variable-shadowing fix the agent chose). Anything else (new tests, refactored helpers, "drive-by" cleanups) = **HIGH** finding (scope creep).

### 2. Correctness of the `html.escape` call

- The call MUST be `html.escape(<fixture>, quote=True)`. Bare `html.escape(s)` with no `quote` arg is **MEDIUM_FIXABLE** — the default already enables quote escaping in modern Python, but explicit `quote=True` documents intent and is what the design doc specifies.
- The expected substring MUST keep the literal `data-full-text="..."` shape — only the value inside the quotes changes.

### 3. Local-variable shadowing fix

- Verify the agent resolved the collision between local `html` (response body) and module `html` (stdlib). Two valid approaches per the S01 prompt:
  1. Rename the local in both affected functions (`html` → `body` or `page_html`), OR
  2. Pre-compute the escaped value into a local BEFORE the `html = response.text` assignment.
- If neither was applied, the file will fail at runtime with `AttributeError: 'str' object has no attribute 'escape'`. That is a **CRITICAL** finding.
- If the agent applied DIFFERENT approaches in the two functions (one renamed, one pre-computed), it is **MEDIUM_FIXABLE** for inconsistency — pick one and apply uniformly.

### 4. Existing tests still pass

- Run `uv run pytest tests/dashboard/test_i00067_recent_activity_truncation.py -v`. All 7 tests must pass. Any failure is **CRITICAL**.

### 5. Project conventions

- `import html` should be in the stdlib group, alphabetically between `from __future__` and the local imports. If misplaced, **MEDIUM_FIXABLE**.
- The file uses `from __future__ import annotations` already; keep it at the top.

### 6. NOT in scope (do NOT raise findings about)

- The other 5 unchanged assertions in the file are pre-existing and out of scope. Do not propose to "harden" them in this CR.
- Production templates, dashboard routers, models — none of these are touched, none are in scope.

## Test Verification (NON-NEGOTIABLE)

Run the full unit test suite to verify no regressions:

```bash
make test-unit
uv run pytest tests/dashboard/test_i00067_recent_activity_truncation.py -v
```

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Test fails, scope violation (file outside the allow-list touched), or shadowing bug that would break at runtime |
| **HIGH** | Scope creep (extra changes beyond the spec), missing the explicit `quote=True` documented in the design doc |
| **MEDIUM_FIXABLE** | Inconsistent shadowing fix between the two functions, misplaced import, lint/format drift |
| **MEDIUM_SUGGESTION** | Style preferences |
| **LOW** | Nitpicks |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00034",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "tests/dashboard/test_i00067_recent_activity_truncation.py",
      "line": 0,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings; otherwise `fail`.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
