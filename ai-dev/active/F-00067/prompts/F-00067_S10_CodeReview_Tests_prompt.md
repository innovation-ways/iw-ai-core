# F-00067_S10_CodeReview_Tests_prompt

**Work Item**: F-00067 — Documentation Visual Design Overhaul
**Step Being Reviewed**: S09 (Tests)
**Review Step**: S10

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00067/F-00067_Feature_Design.md` — §Boundary Behavior, §Invariants, §TDD Approach
- `ai-dev/active/F-00067/reports/F-00067_S09_Tests_report.md`
- All test files listed in the S09 report

## Output Files

- `ai-dev/active/F-00067/reports/F-00067_S10_CodeReview_Tests_report.md`

---

## Review Checklist

### 1. Live DB rule
- Verify NO test imports or uses `orch.config` live DB connection (port 5433). CRITICAL if violated.
- Verify integration tests use testcontainer fixtures from `tests/conftest.py`.

### 2. Coverage completeness
- Verify all 6 Boundary Behavior rows from the design doc have corresponding tests.
- Verify all 6 Invariants have at least one test that validates the invariant.
- Verify both `mapgen.py` and `module_gen.py` diagram changes are tested.

### 3. Test isolation
- Verify unit tests mock the LLM (Ollama) — no real network calls.
- Verify each test is independent and does not rely on test execution order.

### 4. Test naming
- Verify test names clearly describe what they verify (pattern: `test_{what}_{condition}`).

### 5. Assertion quality
- Verify assertions check specific content (not just `assert result is not None`).
- Verify the `<!-- purpose:` comment format assertion uses a proper regex.

## Test Verification

Run `make test-unit` and `make test-integration`. Report results.

## Review Result Contract

```json
{
  "step": "S10",
  "agent": "CodeReview",
  "work_item": "F-00067",
  "step_reviewed": "S09",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
