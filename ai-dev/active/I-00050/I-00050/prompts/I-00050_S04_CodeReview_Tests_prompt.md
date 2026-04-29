# I-00050_S04_CodeReview_Tests_prompt

**Work Item**: I-00050 — Fix cycle prompt carries stale failure report instead of most recent run
**Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00050/I-00050_Issue_Design.md` — acceptance criteria and "Test to Reproduce" section
- `ai-dev/active/I-00050/reports/I-00050_S03_Tests_report.md` — what tests were written
- `tests/unit/test_fix_cycle.py` — new unit tests
- `tests/integration/test_fix_cycle.py` — new integration tests

## Output Files

- `ai-dev/active/I-00050/reports/I-00050_S04_CodeReview_Tests_report.md` — review report

## Context

Review the tests written in S03 for the `_get_browser_findings` fix.

## Review Checklist

### Reproduction Test Existence
- [ ] A test exists that would FAIL on the pre-fix code and PASS on the fixed code (not just a shape-check)
- [ ] The test name makes its purpose clear (e.g., `test_i00050_*`)

### Semantic Correctness (CRITICAL — I003 Lesson)
- [ ] Tests assert SPECIFIC VALUES, not just presence:
  - BAD: `assert "error" in findings` (only proves a substring — not that it leads)
  - GOOD: `assert findings.index("browser env setup failed") < findings.index("V1 FAIL")` (proves ordering)
  - GOOD: `assert findings.startswith("## ⚠️ Most Recent Failure")` (proves prepend structure)
- [ ] The original V table content is verified to still be present (regression check)

### Coverage
- [ ] Unit test: daemon-detected failure (no report_file on StepRun) → prepend occurs
- [ ] Unit test: agent-reported failure (report_file on StepRun) → no prepend, original behaviour
- [ ] Integration test: real DB rows confirm the behaviour end-to-end

### Test Isolation
- [ ] Integration tests use testcontainers, NOT the live DB (port 5433)
- [ ] No `importlib.reload(orch.config)` — use `monkeypatch.delenv()` if env vars need patching
- [ ] No database mocking in integration tests

### Format / Lint (run these)
- [ ] `make lint` on changed test files — no ARG001, F811, or other new violations
- [ ] `make format --check` on changed test files

## Severity Rubric

| Severity | Meaning |
|----------|---------|
| CRITICAL | Test doesn't actually verify the bug scenario (shape-checking instead of semantic) |
| HIGH | Missing the no-op / regression case, or test uses live DB |
| MED | Test name unclear, or ordering assertion missing |
| LOW | Minor style issue |

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00050",
  "overall_status": "pass|fail",
  "mandatory_fix_count": 0,
  "findings": []
}
```

Then call:
```bash
uv run iw step-done I-00050 --step S04 \
  --report ai-dev/active/I-00050/reports/I-00050_S04_CodeReview_Tests_report.md
```
