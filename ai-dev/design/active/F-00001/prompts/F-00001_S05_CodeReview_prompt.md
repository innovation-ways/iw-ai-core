# F-00001_S05_CodeReview_prompt

**Work Item**: F-00001 -- Batch Archive with Post-Merge Actions
**Steps Being Reviewed**: S03 (API) + S04 (Frontend)
**Review Step**: S05

---

## Input Files

- `ai-dev/design/active/F-00001/F-00001_Feature_Design.md` -- Design document
- `ai-dev/work/F-00001/reports/F-00001_S03_API_report.md` -- API implementation report
- `ai-dev/work/F-00001/reports/F-00001_S04_Frontend_report.md` -- Frontend implementation report
- All files listed in both implementation reports' `files_changed`

## Output Files

- `ai-dev/work/F-00001/reports/F-00001_S05_CodeReview_report.md` -- Review report

## Context

You are reviewing the implementation work done in steps S03 (API endpoint) and S04 (Frontend template) for **Batch Archive with Post-Merge Actions**.

Read the design document to understand what was intended. Read both implementation reports to understand what was done. Then review all changed files.

## Review Checklist

### 1. Architecture Compliance

- Does the archive endpoint follow the same patterns as other batch actions (approve, pause, resume, cancel)?
- Is the background thread approach correct (own session, daemon thread)?
- Are layer boundaries respected?

### 2. Code Quality

- Is the confirmation dialog wired correctly via htmx?
- Is the HX-Trigger/toast response consistent with other action endpoints?
- Are SSE event types added correctly to both `_TOAST_EVENTS` and `_TOAST_SEVERITY`?

### 3. Security

- No injection vulnerabilities in the archive endpoint
- Proper status validation before archiving

### 4. Frontend

- Does the Archive button match the styling pattern of other batch buttons?
- Is the SSE listener properly wired for toast notifications?
- Is the archived state handled (no action buttons shown)?

### 5. Testing

- Are endpoint tests adequate?
- Are edge cases covered (invalid status, concurrent archive)?

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the project's unit test command to verify no regressions
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
  "step": "S05",
  "agent": "CodeReview",
  "work_item": "F-00001",
  "step_reviewed": "S03+S04",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
