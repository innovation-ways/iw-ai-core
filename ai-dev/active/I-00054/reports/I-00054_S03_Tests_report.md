# I-00054 S03 Tests Report

## Step Summary

S03 implemented unit tests for the I-00054 fix (Coverage Page Toggle Label Does Not Update on Expand/Collapse). The fix adds JavaScript-driven toggle state to the coverage page template, and the tests verify that the server-rendered HTML contains all the attributes and markup the JS toggle logic depends on.

## What Was Done

Added three tests to `tests/dashboard/test_coverage_page.py` inside the existing `TestCoveragePage` class:

### 1. `test_i00054_coverage_page_toggle_attributes_present` (reproduction test)
Verifies that for a single-package `CoverageView`, the rendered HTML contains:
- `data-pkg-toggle="orch"` on the `<tr>` element
- `data-expanded="false"` initial state attribute
- `id="expand-label-orch"` on the label `<td>`
- Guard condition `this.dataset.expanded!='true'` in `hx-trigger`
- Visible "click to expand" text (via `>click to expand<` to avoid matching JS string)

This test FAILS before the S01 fix (attributes absent) and PASSES after (attributes present).

### 2. `test_i00054_coverage_toggle_attributes_per_package` (regression test)
Verifies that with two packages (orch, dashboard), each gets its own scoped attributes:
- `data-pkg-toggle="orch"` and `data-pkg-toggle="dashboard"`
- `id="expand-label-orch"` and `id="expand-label-dashboard"`
- `hx-target="#files-orch"` and `hx-target="#files-dashboard"`
- At least 2 occurrences of the guard condition `this.dataset.expanded!='true'`

### 3. `test_i00054_coverage_page_toggle_script_present` (regression test)
Verifies the JS toggle script block is rendered:
- `htmx:afterSwap` listener is present in the HTML
- `data-pkg-toggle` appears (referenced in `querySelectorAll`)
- `>click to collapse<` does NOT appear in initial render (ensuring "click to collapse" is only set by JS after swap, not server-rendered)

## Design Decisions

### Assertion style: Semantic correctness over shape checking
Per the I003 lesson embedded in the prompt, every assertion checks specific values, not just attribute presence:
- `assert 'data-pkg-toggle="orch"'` not `assert "data-pkg-toggle" in html`
- `assert 'id="expand-label-orch"'` not `assert "expand-label" in html`

### Avoiding false negatives from JS strings in script blocks
The initial test design used `assert "click to collapse" not in html` and `assert "click to expand" in html`. However, the `coverage.html` template contains a `<script>` block that sets `label.textContent = 'click to collapse'` — so "click to collapse" always appears in the HTML as a JS string literal, making the naive assertion always fail.

The fix uses `>click to expand<` and `>click to collapse<` to match only the visible HTML text content (the `<td>` element's text), not the JS string literals in the `<script>` block. This correctly distinguishes between:
- Server-rendered visible text: `<td ...>click to expand</td>` → matches `>click to expand<`
- JS string literals in script: `label.textContent = 'click to collapse';` → does NOT match `>click to collapse<`

## Files Changed

- `tests/dashboard/test_coverage_page.py` — Added 3 new test methods to `TestCoveragePage` class

## Test Results

```
8 passed, 0 failed
- 5 pre-existing tests: all pass
- 3 new I-00054 tests: all pass
```

## Quality Gates

- **format**: `ruff format --check .` → 503 files already formatted ✓
- **typecheck**: `mypy orch/ dashboard/` → Success: no issues found in 210 source files ✓
- **lint**: `ruff check .` → All checks passed! ✓
- **unit tests**: `pytest tests/dashboard/test_coverage_page.py` → 8 passed ✓

## Blockers

None.

## Notes

The tests verify only server-side rendering (what Jinja2 produces). The actual toggle behavior (label flip on click, collapse on second click) is client-side JS and is verified end-to-end by the QV Browser step (S11) using Playwright.