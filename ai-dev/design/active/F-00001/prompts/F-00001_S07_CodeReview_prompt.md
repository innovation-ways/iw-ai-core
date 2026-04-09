# F-00001_S07_CodeReview_prompt

**Work Item**: F-00001 -- Batch Archive with Post-Merge Actions
**Step Being Reviewed**: S06 (Tests)
**Review Step**: S07

---

## Input Files

- `ai-dev/design/active/F-00001/F-00001_Feature_Design.md` -- Design document
- `ai-dev/work/F-00001/reports/F-00001_S06_Tests_report.md` -- Tests implementation report
- All files listed in the implementation report's `files_changed`

## Output Files

- `ai-dev/work/F-00001/reports/F-00001_S07_CodeReview_report.md` -- Review report

## Context

You are reviewing the test implementation work done in step S06 by Tests for **Batch Archive with Post-Merge Actions**.

Read the design document to understand what was intended. Read the implementation report to understand what was done. Then review all test files.

## Review Checklist

### 1. Test Coverage

- Are all acceptance criteria from the design document covered?
- Are all boundary behaviors from the design document tested?
- Are both happy path and error paths covered?

### 2. Test Quality

- Are tests isolated and deterministic?
- Do test names clearly describe what they verify?
- Are fixtures set up correctly (testcontainers, FTS triggers)?
- Is the testcontainers URL replacement done correctly (`psycopg2` → `psycopg`)?

### 3. Test Conventions

- Read `CLAUDE.md` for project-specific test rules.
- No connection to live DB (port 5433)
- No `importlib.reload(orch.config)` calls
- Proper use of `monkeypatch.delenv()` instead

### 4. Integration Test Correctness

- Do integration tests create all necessary DB objects (project, batch, batch_items, work_items)?
- Are status transitions verified after the archive operation?
- Is the DaemonEvent emission verified?

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `make test-unit` and `make test-integration`
2. Run lint and type checking
3. Report test results accurately in the result contract

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview",
  "work_item": "F-00001",
  "step_reviewed": "S06",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
