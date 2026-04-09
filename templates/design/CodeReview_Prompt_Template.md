# {TYPE}{NNN}_S{NN}_CodeReview_prompt

**Work Item**: {ID} -- {Title}
**Step Being Reviewed**: S{NN} ({Agent})
**Review Step**: S{review_step_NN}

---

## Input Files

- `ai-dev/work/{ID}/{ID}_{Type}_Design.md` -- Design document
- `ai-dev/work/{ID}/reports/{ID}_S{NN}_{Agent}_report.md` -- Implementation step report
- All files listed in the implementation report's `files_changed`

## Output Files

- `ai-dev/work/{ID}/reports/{ID}_S{review_step_NN}_CodeReview_report.md` -- Review report

## Context

You are reviewing the implementation work done in step S{NN} by {Agent} for **{Work Item Title}**.

Read the design document to understand what was intended. Read the implementation report to understand what was done. Then review all changed files.

## Review Checklist

### 1. Architecture Compliance

- Does the implementation match the design document's architecture?
- Are layer boundaries respected (no cross-layer imports)?
- Are the right patterns used for the project's framework?
- Read `CLAUDE.md` for project-specific architecture rules.

### 2. Code Quality

- Is the code clear, readable, and well-structured?
- Are there any obvious bugs, logic errors, or edge cases missed?
- Is error handling appropriate and consistent?
- Are there any performance concerns?
- Is there unnecessary duplication?

### 3. Project Conventions

- Read `CLAUDE.md` for all project conventions.
- Do naming conventions match the project's style?
- Is the code formatted according to project rules?
- Are imports organized correctly?

### 4. Security

- No hardcoded secrets, credentials, or API keys
- Input validation where user data enters the system
- No SQL injection, XSS, or other injection vulnerabilities
- Proper authorization checks where applicable

### 5. Testing

- Are all new public functions/methods tested?
- Do tests cover edge cases and error paths?
- Are tests isolated and deterministic?
- Do test names clearly describe what they verify?

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the project's unit test command to verify no regressions
2. Run lint and type checking
3. Report test results accurately in the result contract

## Severity Levels

Classify each finding with one of these severities:

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
  "step": "S{review_step_NN}",
  "agent": "CodeReview",
  "work_item": "{ID}",
  "step_reviewed": "S{NN}",
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

- `verdict`: Use `pass` if there are zero CRITICAL or HIGH findings AND zero MEDIUM (fixable) findings. Use `fail` if any mandatory fixes are needed.
- `mandatory_fix_count`: Count of CRITICAL + HIGH + MEDIUM (fixable) findings.
- Only CRITICAL, HIGH, and MEDIUM (fixable) findings trigger a fix cycle. MEDIUM (suggestion) and LOW are informational.
