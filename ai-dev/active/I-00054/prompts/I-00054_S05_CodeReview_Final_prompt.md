# I-00054_S05_CodeReview_Final_prompt

**Work Item**: I-00054 -- Coverage Page Toggle Label Does Not Update on Expand/Collapse
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01, S03

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable to this step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state**: `uv run iw item-status I-00054 --json`
- `ai-dev/active/I-00054/I-00054_Issue_Design.md` — Design document
- `ai-dev/active/I-00054/reports/I-00054_S01_Frontend_report.md` — S01 implementation report
- `ai-dev/active/I-00054/reports/I-00054_S02_CodeReview_Frontend_report.md` — S02 review report
- `ai-dev/active/I-00054/reports/I-00054_S03_Tests_report.md` — S03 tests report
- `ai-dev/active/I-00054/reports/I-00054_S04_CodeReview_Tests_report.md` — S04 review report
- `dashboard/templates/pages/system/coverage.html` — Modified template
- `tests/dashboard/test_coverage_page.py` — Test file with new tests

## Output Files

- `ai-dev/active/I-00054/reports/I-00054_S05_CodeReview_Final_report.md` — Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for **I-00054: Coverage Page Toggle Label Does Not Update on Expand/Collapse**.

The fix is minimal: one Jinja2 template modified, three new tests added. Your job is to verify the complete picture — design intent vs implementation, reproduction test correctness, and that no regressions were introduced.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Report any NEW violations in changed files as CRITICAL findings.

## Review Checklist

### 1. Completeness vs Design Document

- Does the template change match ALL three changes specified in the design doc: (a) data attributes on `<tr>`, (b) id on label `<td>`, (c) `<script>` block with `htmx:afterSwap` listener and collapse handler?
- Does the hx-trigger guard condition match exactly: `this.dataset.expanded!='true'`?
- Does the `htmx:afterSwap` listener correctly scope to coverage file divs using `target.id.startsWith('files-')`?

### 2. Reproduction Test — Does It Actually Catch the Bug?

This is the most critical check:

- Would `test_i00054_coverage_page_toggle_attributes_present` have **FAILED** against the original template (before S01)?
  - Original template has no `data-pkg-toggle`, no `data-expanded`, no `id="expand-label-..."`, and `hx-trigger="click, keydown[key=='Enter']"` (no guard) — the test must assert the absence of these to be a true reproduction test.
- Does the test assert **specific values** (e.g. `'data-pkg-toggle="orch"'`) not just key presence (e.g. `'data-pkg-toggle'`)?

### 3. Semantic Correctness of All Assertions

Review every assertion across all three new tests. Flag any assertion that only checks for key/attribute presence without verifying the specific expected value as a **HIGH** finding. Specifically:

- `'data-pkg-toggle="orch"'` — GOOD (checks value)
- `'data-pkg-toggle'` — HIGH (checks only name)
- `'id="expand-label-orch"'` — GOOD
- `'expand-label'` — HIGH (too broad)

### 4. Scope Containment

- Is the fix strictly limited to `dashboard/templates/pages/system/coverage.html` and `tests/dashboard/test_coverage_page.py`?
- No backend changes, no new routes, no service layer changes, no new static JS files?

### 5. No Regressions

- Do all existing tests in `TestCoveragePage` still pass?
- Does the htmx expand path (first click) still work — i.e., is `hx-get`, `hx-target`, `hx-swap` still present on each row?

### 6. Security

- The `pkgName` in the JS is derived from `target.id.slice('files-'.length)`, which is server-rendered from `pkg.name`. Confirm `pkg.name` is a Python package directory name (not user input) and not injectable.

## Test Verification (NON-NEGOTIABLE)

Run the full test suite:

```bash
make test-unit
make allure-integration
```

Report results accurately. Integration test failures are CRITICAL findings.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00054",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file",
      "line": 0,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": false
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
