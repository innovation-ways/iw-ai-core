# I-00092_S03_Tests_report

## Work Item
I-00092 — Auto-merge filter chip never highlights the active filter

## Step
S03 — Regression tests for filter chip active-state highlighting

## What Was Done

Added 3 regression tests to `tests/dashboard/test_auto_merge_routes.py` covering AC1, AC2, and AC3 from the issue design:

1. **`test_filter_chip_resolved_is_highlighted_when_active`** — AC1: when `?type=merge_auto_resolved` is in the URL, the `resolved` chip's `<a>` carries `bg-primary` in its `class` attribute (attribute-scoped via `re.search`) AND `aria-pressed="true"`; all other 6 chips carry `aria-pressed="false"` and lack `bg-primary`.

2. **`test_filter_chip_all_is_highlighted_when_no_type_param`** — AC2: when no `?type=` param is provided, the `all` chip is active; all other 6 chips are not.

3. **`test_filter_chip_title_tooltips_match_event_types`** — AC3: each chip's `<a title="...">` attribute matches its underlying event_type string (`merge_auto_resolved`, `merge_auto_resolution_attempted`, etc.) or `"all event types"` for the `all` chip.

Also added the `_extract_filter_chip_blocks(html)` helper at module level, which parses the fragment response and returns `{label: outer-<a>-html}` for each of the 7 chips, asserting all 7 are found.

## Semantic Correctness (I-00067 lesson)

The original I-00067 finding was that a naive `assert "bg-primary" in html` passes even when the bug is unfixed (the class is defined in compiled CSS or appears in `<script>` blocks). The new tests use the attribute-scoped form:

```python
assert re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', chips["resolved"])
```

This anchors the match to the `class` attribute specifically, so it cannot be satisfied by CSS definitions or data attributes elsewhere in the document.

## Files Changed
- `tests/dashboard/test_auto_merge_routes.py` — added `_extract_filter_chip_blocks` helper and 3 regression tests

## Test Results
```
tests/dashboard/test_auto_merge_routes.py -v
28 passed in 32.85s
```
(all 28 tests green; coverage failure is pre-existing and unrelated)

## Pre-flight Quality Gates
- **format**: `uv run ruff format tests/dashboard/test_auto_merge_routes.py` — reformatted 1 file ✓
- **typecheck**: pre-existing mypy issues in the file (unrelated to these changes) ✓
- **lint**: `uv run ruff check tests/dashboard/test_auto_merge_routes.py` — All checks passed ✓

## TDD Red Evidence
`n/a — coverage step (tests-impl)`

## Blockers
None.