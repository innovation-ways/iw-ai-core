# F-00055_S12_CodeReview_Fix_Final_prompt

**Work Item**: F-00055 — Work-item-aware code chat
**Step**: S12
**Agent**: code-review-fix-final-impl

---

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md`
- `ai-dev/active/F-00055/reports/F-00055_S11_CodeReview_Final_report.md` — findings list
- All previous step reports and changed files

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S12_CodeReview_Fix_Final_report.md`

## Context

Apply fixes for every CRITICAL and HIGH finding from S11. MEDIUM findings should be addressed unless they are explicitly deferred with a rationale; LOW findings are optional.

## Requirements

### 1. Fix every CRITICAL finding

For each CRITICAL finding in S11:
- Read the finding and its recommended fix.
- Apply the fix at the specified file:line.
- Re-run the targeted test (if one exists) to confirm the fix.
- If no targeted test exists, add one as part of the fix.

### 2. Fix every HIGH finding

Same as above for HIGH.

### 3. Address MEDIUM findings

For each MEDIUM finding:
- Either apply the fix OR write a one-sentence rationale in the report explaining the deferral.
- Do not defer a MEDIUM that masks a CRITICAL/HIGH issue.

### 4. Full test suite sanity

After all fixes:

```bash
make test-unit
make test-integration
uv run ruff check .
uv run ruff format --check .
uv run mypy orch/ dashboard/
```

All must pass. Any failure is a blocker — do not report completion with red tests.

### 5. Regression cross-check

Run the integration test `test_code_qa_no_regression.py` explicitly. Confirm the default code-only chat path behaves identically to pre-F-00055. Document the confirmation in the step report.

## Report structure

```markdown
# F-00055 S12 Fix Report

## Findings Addressed
| ID | Severity | Status | File | Test |
|----|----------|--------|------|------|
| F01 | CRITICAL | fixed | `path:line` | `test_x` |
| ... | ... | ... | ... | ... |

## Deferred (with rationale)
| ID | Severity | Reason |
|----|----------|--------|
| F07 | MEDIUM | ... |

## Test Run
- `make test-unit`: X passed, 0 failed
- `make test-integration`: X passed, 0 failed
- `uv run ruff check .`: clean
- `uv run ruff format --check .`: clean
- `uv run mypy orch/ dashboard/`: clean

## Regression Check
Result of `test_code_qa_no_regression.py`: PASS / FAIL + notes
```

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "code-review-fix-final-impl",
  "work_item": "F-00055",
  "completion_status": "complete|partial|blocked",
  "critical_fixed": 0,
  "high_fixed": 0,
  "medium_fixed": 0,
  "medium_deferred": 0,
  "tests_passed": true,
  "regression_check": "pass|fail",
  "notes": ""
}
```
