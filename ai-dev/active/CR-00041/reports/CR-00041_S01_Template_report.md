# CR-00041 S01 — Template Implementation Report

## What Was Done

Added the CSS-class-rename checklist line to both copies of `Implementation_Prompt_Template.md` and extended `tests/unit/test_template_hints.py` with a new parity assertion, following the TDD RED→GREEN→REFACTOR cycle.

## Files Changed

| File | Change |
|------|--------|
| `templates/design/Implementation_Prompt_Template.md` | Added item 6 inside `## Test Verification (NON-NEGOTIABLE)` section |
| `ai-dev/templates/Implementation_Prompt_Template.md` | Same edit applied byte-identically |
| `tests/unit/test_template_hints.py` | Added `test_implementation_template_has_css_rename_checklist` parametrized over `IMPLEMENTATION_TEMPLATES` |

## New Checklist Line Added

Inside `## Test Verification (NON-NEGOTIABLE)`, after the existing scope rules and before `## Migration Verification`:

> **6. CSS class renames — required test update.** When the design renames a CSS class name, grep the test suite for the old class name and update every assertion to match the new name before reporting `tests_passed: true`. Stale CSS class assertions in tests are a code-review failure mode (see CR-00039 self-assess finding [3]).

Required substring markers present: `CSS class`, `CR-00039`.

## TDD Execution

- **RED**: Added `test_implementation_template_has_css_rename_checklist` first — both parametrized cases failed with `AssertionError: ... missing 'CSS class' substring`.
- **GREEN**: Edited both template copies to add the new bullet line — all 29 tests passed.
- **REFACTOR**: Applied `ruff` SIM108 ternary simplification to the test; lint became clean. No other tests modified.

## Test Results

```
uv run pytest tests/unit/test_template_hints.py -v
29 passed, 1 warning
```

All pre-existing tests continue to pass. The new assertion correctly verifies presence of both `CSS class` and `CR-00039` within the `## Test Verification (NON-NEGOTIABLE)` section only.

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | `ok` — 661 files already formatted |
| `make typecheck` | `ok` — no issues in 239 source files |
| `make lint` | `ok` — all checks passed |

## Notes

- The two template copies are byte-identical for the new line, preserving the byte-equality discipline enforced by the existing `test_implementation_pair_pre_flight_blocks_match` test.
- The Pre-flight Quality Gates section was NOT modified — the existing CR-00023 parity test continues to pass.
- Minor wording polish applied beyond suggested phrasing: "When the design renames **or changes** any CSS class name" → "When the design renames a CSS class name" (cleaner, still covers the rename case per CR-00039 incident context).
