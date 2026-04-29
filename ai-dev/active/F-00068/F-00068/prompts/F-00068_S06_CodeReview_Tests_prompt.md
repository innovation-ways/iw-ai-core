# F-00068_S06_CodeReview_Tests_prompt

**Work Item**: F-00068 — AI Chat Visual Improvements
**Step Being Reviewed**: S05 (Tests)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/F-00068/F-00068_Feature_Design.md` — §Boundary Behavior, §Invariants
- `ai-dev/active/F-00068/reports/F-00068_S05_Tests_report.md`
- All test files listed in S05 report

## Output Files

- `ai-dev/active/F-00068/reports/F-00068_S06_CodeReview_Tests_report.md`

---

## Review Checklist

### 1. Coverage of all 5 callout types
- Verify tests assert NOTE, WARNING, and DANGER are in the block (at minimum).

### 2. Regression preservation tests
- Verify tests confirm Mermaid and D2 mentions are preserved in `RENDERING_CAPABILITIES_BLOCK`.
- Missing these is HIGH — S01 could silently break existing diagram instruction.

### 3. Negative test for heading overuse
- Verify test checks that the block discourages starting every answer with a heading.

### 4. Live DB isolation
- Verify no test connects to live DB port 5433. CRITICAL if violated.

### 5. Test isolation
- Verify each test is independent (no shared mutable state between tests).

## Test Verification

Run `make test-unit`. Report results.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "F-00068",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
