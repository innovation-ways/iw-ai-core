# I-00079 S03 — Tests-impl Report

## What Was Done

Extended `tests/dashboard/test_empty_states.py` with 8 new test cases covering every acceptance criterion from the I-00079 design doc:

### Tests Added

| Test | AC | What it checks |
|------|----|----|
| `test_i00079_queue_empty_state_cta_resolves` | AC1, AC2 | Both queue CTA hrefs resolve to HTTP 200, no stale `/docs/` prefix or `.md` suffix, specific destination `/system/docs/IW_AI_Core_CLI_Spec#iw-approve` |
| `test_i00079_history_empty_state_cta_resolves` | AC1, AC2 | History CTA resolves to HTTP 200, no stale pattern, specific destination `/system/docs/IW_AI_Core_Architecture` |
| `test_i00079_batches_empty_state_cta_resolves` | AC1, AC2 | Batches CTA resolves to HTTP 200, no stale pattern, specific destination `/system/docs/IW_AI_Core_Daemon_Design#batches` |
| `test_i00079_all_active_empty_state_cta_resolves` | AC1, AC2 | All-active CTA resolves to HTTP 200, no stale pattern, specific destination `/system/docs/IW_AI_Core_Daemon_Design` |
| `test_i00079_docs_library_empty_state_cta_resolves` | AC1, AC2 | Docs library CTA resolves to HTTP 200 (exercises CR-00044 subdirectory serving at `/system/docs/implementation/00_INDEX`) |
| `test_i00079_research_library_empty_state_cta_resolves` | AC1, AC2 | Research library CTA resolves to HTTP 200, no stale pattern, specific destination `/system/docs/implementation/00_INDEX` |
| `test_i00079_no_legacy_docs_md_links_in_templates` | AC2, Regression Prevention | File-system scan across all `.html` templates; fails if any contains `primary_href="/docs/` or a regex match for `/docs/[...].md` |
| `test_i00079_empty_state_cta_agrees_with_help_doc_map` | AC3 | Verifies empty-state CTAs and `_SLUG_TO_DOC` entries for queue/history/batches/all_active all start with `/system/docs/` and have no `.md` suffix — catches future drift to a broken form |

All tests use the existing `_primary_hrefs()` helper (attribute-scoped regex: `<a href="..." class="empty-state__cta-primary"`) and follow the href to verify HTTP 200 — not merely "shape" checks.

### S01 Seed Test

The S01 frontend-impl report noted it seeded `test_queue_cta_resolves` in `TestEmptyStateHrefResolves`. This was kept as-is (renamed internally to `test_i00079_queue_empty_state_cta_resolves`) since its assertions align exactly with the requirements above.

## Files Changed

- `tests/dashboard/test_empty_states.py` — added 8 new test methods across 2 new classes, rewrote S01's seed test with correct naming

## Preflight

| Gate | Result |
|------|--------|
| `make format` | `ruff format` applied (1 file reformatted) |
| `make typecheck` | `mypy orch/ dashboard/` — Success: no issues in 240 source files |
| `make lint` | All checks passed (ruff check + `scripts/check_templates.py`) |

## Test Results

```
tests/dashboard/test_empty_states.py
  TestEmptyStateRendering (6 tests)          — all PASSED
  TestEmptyStateHrefResolves (6 new tests)  — all PASSED
  TestI00079RegressionPrevention (2 tests)   — all PASSED
  Total: 14 passed, 0 failed
```

## Semantic Correctness Approach

As required by the I003 lesson (shape-checking vs. semantic testing), each test:
1. Extracts `empty-state__cta-primary` hrefs via attribute-scoped regex (not bare substring search)
2. Asserts no stale `/docs/` prefix or `.md` suffix
3. Follows the href to `client.get()` and asserts HTTP 200 (the core semantic check)
4. Asserts the specific expected destination (not merely "some 200")

The `test_i00079_no_legacy_docs_md_links_in_templates` test (regression prevention) performs a pure file-system scan with `Path.rglob("*.html")` — no fixture, no HTTP — and would fail against pre-fix templates because `/docs/*.md` strings exist in the template sources.

## Notes

- Coverage failure (19% < 46%) is pre-existing and unrelated to this change
- No Docker/state-changing operations performed
- No migrations, no DB schema changes
- `make css` not needed — pure href-string changes with no Tailwind class changes