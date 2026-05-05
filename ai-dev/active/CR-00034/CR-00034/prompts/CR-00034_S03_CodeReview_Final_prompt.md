# CR-00034_S03_CodeReview_Final_prompt

**Work Item**: CR-00034 -- Robust `data-full-text` test assertions using `html.escape`
**Review Step**: S03 (Final Review)
**Implementation Steps Reviewed**: S01

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds NO migrations. Verify in your final review that no migration files exist in the diff.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00034/CR-00034_CR_Design.md` — Design document.
- `ai-dev/work/CR-00034/reports/CR-00034_S01_Tests_report.md` — Implementation report.
- `ai-dev/work/CR-00034/reports/CR-00034_S02_CodeReview_report.md` — Per-agent review report.
- `tests/dashboard/test_i00067_recent_activity_truncation.py` — Only changed file.

## Output Files

- `ai-dev/work/CR-00034/reports/CR-00034_S03_CodeReview_Final_report.md` — Final review report.

## Context

You are performing the final cross-step review of CR-00034. Because this CR has only one implementation step (S01) and one changed file, the "cross-cutting" surface is small — but the review still has value as the gate before QV.

Read the design document. Read S01's report and S02's review. Read the changed file in full.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any NEW violation in the changed file (relative to main) is a **CRITICAL** finding.

## Review Checklist

### 1. Completeness vs Design Document

- All three Acceptance Criteria (AC1, AC2, AC3) must be satisfied:
  - **AC1**: Existing tests pass — verify by running the targeted file.
  - **AC2**: The `html.escape(..., quote=True)` shape is in place. AC2 is conceptual; you don't need to substitute a `"`-containing fixture, but you should confirm by reading the code that the escape call is correctly wrapped around the fixture.
  - **AC3**: `import html` is present and in the stdlib group; lint/format pass.
- The CR scope is "two assertions + one import in one file." Anything beyond that = missing-requirement violation in reverse: the implementer added unauthorized work.

### 2. Cross-Step Consistency (here = within S01)

- The two affected test functions must use the SAME shadowing-fix approach (both rename `html` local, OR both pre-compute escaped value). Inconsistency = **MEDIUM_FIXABLE**.

### 3. Integration Points

- Verify no other test file or production module was edited. The merge gate enforces this via `scope.allowed_paths`, but flag here if something slipped through.

### 4. Test Coverage (Holistic)

- The 7 tests in the file must all pass. Run:
  ```bash
  uv run pytest tests/dashboard/test_i00067_recent_activity_truncation.py -v
  ```
- This CR does NOT add new tests; that is per spec, not a gap.

### 5. Architecture Compliance

- This CR does not affect architecture. Nothing crosses layer boundaries.

### 6. Security (Cross-Cutting)

- N/A — test-file change with no user input, no new endpoints.

## Test Verification (NON-NEGOTIABLE)

Run the full test suite (unit + integration):

```bash
make test-unit
uv run pytest tests/dashboard/ -v
```

If integration tests fail unrelated to this change, note it but do not block; if they fail in `tests/dashboard/test_i00067_recent_activity_truncation.py` specifically, that is a **CRITICAL** finding.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Test fails, scope violation, file outside allow-list touched |
| **HIGH** | Missing acceptance-criteria coverage, missing `quote=True` arg |
| **MEDIUM_FIXABLE** | Inconsistent shadowing fix, misplaced import, lint drift |
| **MEDIUM_SUGGESTION** | Style preferences |
| **LOW** | Nitpicks |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-final-impl",
  "work_item": "CR-00034",
  "steps_reviewed": ["S01"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "tests/dashboard/test_i00067_recent_activity_truncation.py",
      "line": 0,
      "description": "...",
      "suggestion": "...",
      "cross_cutting": false
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings; otherwise `fail`.
- `cross_cutting`: For this single-step CR, almost always `false`. Only mark `true` if a finding genuinely spans S01 plus an unanticipated downstream concern.
