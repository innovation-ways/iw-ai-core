# F-00001_S02_CodeReview_prompt

**Work Item**: F-00001 -- Batch Archive with Post-Merge Actions
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

---

## Input Files

- `ai-dev/design/active/F-00001/F-00001_Feature_Design.md` -- Design document
- `ai-dev/work/F-00001/reports/F-00001_S01_Backend_report.md` -- Implementation step report
- All files listed in the implementation report's `files_changed`

## Output Files

- `ai-dev/work/F-00001/reports/F-00001_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing the implementation work done in step S01 by Backend for **Batch Archive with Post-Merge Actions**.

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
- `subprocess.run` with `shell=True` — verify command strings come from trusted config only (project owner controls `.iw-orch.json`)
- No injection vulnerabilities in command construction

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
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "F-00001",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
