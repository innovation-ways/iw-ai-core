# F-00001_S08_CodeReview_Final_prompt

**Work Item**: F-00001 -- Batch Archive with Post-Merge Actions
**Review Step**: S08 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## Input Files

- `ai-dev/design/active/F-00001/F-00001_Feature_Design.md` -- Design document
- All implementation step reports: `ai-dev/work/F-00001/reports/F-00001_S*_*_report.md`
- All per-agent code review reports
- All files listed in all implementation reports' `files_changed`

## Output Files

- `ai-dev/work/F-00001/reports/F-00001_S08_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for **Batch Archive with Post-Merge Actions**.

This review looks at the complete picture -- not individual steps in isolation, but how everything fits together. Per-agent reviews have already been done; your job is to catch cross-cutting issues they could not.

Read the design document to understand the full intended scope. Read all implementation and review reports to understand what was built. Then review all changed files holistically.

## Review Checklist

### 1. Completeness vs Design Document

- Are ALL requirements from the design document implemented?
- Are all 5 acceptance criteria covered?
- Are all boundary behaviors handled?
- All 5 invariants hold?

### 2. Cross-Agent Consistency

- Does the batch archiver (S01) integrate correctly with the API endpoint (S03)?
- Does the frontend (S04) properly wire up to the API endpoint?
- Are SSE event types consistent between the archiver (emits), SSE module (routes), and frontend (listens)?
- Is `batch_archived` / `batch_archive_failed` / `batch_archiving` handled consistently across all layers?

### 3. Integration Points

- Does `archive_batch()` create its own DB session correctly for background thread use?
- Does the threading model work — main thread returns toast, background thread does work?
- Are there any race conditions (e.g., user navigates away, background thread still running)?

### 4. Test Coverage (Holistic)

- Do integration tests exercise the full flow (endpoint → background thread → DB state)?
- Are cross-module interactions tested?
- Are error paths tested end-to-end?

### 5. Architecture Compliance

- Read `CLAUDE.md` for project-specific architecture rules.
- Does the implementation respect the existing patterns in `dashboard/routers/actions.py`?

### 6. Security (Cross-Cutting)

- `subprocess.run(cmd, shell=True)` — is `cmd` only sourced from project config JSONB?
- No user-supplied input reaches shell execution

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the **full test suite** (both unit AND integration tests)
2. Run lint and type checking
3. Report test results accurately in the result contract
4. If integration tests fail, this is a CRITICAL finding

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability, missing requirement | Must fix before merge |
| **HIGH** | Significant bug, integration failure, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "CodeReview_Final",
  "work_item": "F-00001",
  "steps_reviewed": ["S01", "S03", "S04", "S06"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
