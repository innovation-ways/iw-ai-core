# I-00054_S04_CodeReview_Tests_prompt

**Work Item**: I-00054 -- Coverage Page Toggle Label Does Not Update on Expand/Collapse
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable to this step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state**: `uv run iw item-status I-00054 --json`
- `ai-dev/active/I-00054/I-00054_Issue_Design.md` — Design document
- `ai-dev/active/I-00054/reports/I-00054_S03_Tests_report.md` — S03 test implementation report
- `tests/dashboard/test_coverage_page.py` — Test file with new tests

## Output Files

- `ai-dev/active/I-00054/reports/I-00054_S04_CodeReview_Tests_report.md` — Review report

## Context

You are reviewing the tests written in S03 for **I-00054: Coverage Page Toggle Label Does Not Update on Expand/Collapse**.

The tests verify that the template renders the data attributes and JS toggle script required for the expand/collapse behavior.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Report any NEW violations in `tests/dashboard/test_coverage_page.py` as CRITICAL findings.

## Review Checklist

### 1. Reproduction Test Correctness

- Does `test_i00054_coverage_page_toggle_attributes_present` exist and target the bug?
- Would this test have FAILED against the pre-fix template (where `data-pkg-toggle`, `data-expanded`, `id="expand-label-..."`, and the hx-trigger guard were absent)?
- Does it PASS against the fixed template?

### 2. Semantic Correctness (CRITICAL CHECK)

This is the most important check. Each assertion must verify a **specific expected value**, not just the presence of a key:

- BAD: `assert "data-pkg-toggle" in html` — only checks the attribute name exists somewhere
- GOOD: `assert 'data-pkg-toggle="orch"' in html` — checks the specific attribute=value pair for the correct package

Review every assertion in every new test. Any assertion that only checks for attribute/key presence without verifying the specific value is a **HIGH** finding.

- Does `test_i00054_coverage_page_toggle_attributes_present` check `'data-pkg-toggle="orch"'` (with value), not just `'data-pkg-toggle'`?
- Does it check `'id="expand-label-orch"'` (with full value), not just `'expand-label'`?
- Does it check that `"click to collapse"` is NOT in the initial render?

### 3. Multiple Packages Coverage

- Is there a test (`test_i00054_coverage_toggle_attributes_per_package` or equivalent) that verifies attributes are rendered for EACH package, not just one?
- Does this test use multiple packages and assert per-package scoped ids and data attributes?

### 4. Script Block Test

- Is there a test verifying `htmx:afterSwap` appears in the rendered HTML (confirming the script block is present)?

### 5. Existing Tests Untouched

- Are all pre-existing tests in `TestCoveragePage` still present and passing?
- Did the S03 agent modify or delete any existing test? If so, that is a CRITICAL finding.

### 6. Test Isolation and Pattern

- Do new tests use the same `client` fixture and `unittest.mock.patch` pattern as existing tests?
- Do new tests belong inside the `TestCoveragePage` class?
- Are test names prefixed with `test_i00054_` for traceability?

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

All tests (existing + new) must pass.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00054",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 0,
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
