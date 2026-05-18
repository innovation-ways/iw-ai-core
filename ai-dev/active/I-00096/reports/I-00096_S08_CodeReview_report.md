# I-00096 S08 CodeReview Report

## What Was Reviewed

Step S07 (tests-impl) — regression tests for I-00096: chip dedup + auto-merge-only default filter.

## Files Changed (S07)

| File | Change |
|------|--------|
| `tests/unit/test_auto_merge_aggregator.py` | +80 lines: 3 new tests for aggregator prefix filter |
| `tests/dashboard/test_auto_merge_routes.py` | +149 lines: 5 new tests for chip dedup + show-all toggle |

## Pre-flight Quality Gates

- `make lint` — **PASS** (all checks passed)
- `make format` — **PASS** (760 files already formatted)

## Test Verification

```
uv run pytest tests/unit/test_auto_merge_aggregator.py tests/dashboard/test_auto_merge_routes.py -v --no-cov
============================= 64 passed in 17.76s ==============================
```

All 64 tests pass (22 unit + 42 dashboard).

## Review Checklist

| Check | Status | Notes |
|-------|--------|-------|
| Test placement (I-00067) | ✅ | Unit tests in `tests/unit/`, dashboard tests in `tests/dashboard/` |
| Semantic correctness (I003) | ✅ | `test_auto_merge_page_renders_exactly_one_chip` uses `.count('id="auto-merge-status-chip"') == 1`; default-filter tests assert on message strings (`"probe-y"` / `"step-x"`) |
| Coverage — all 6 named tests | ✅ | All 6 tests from the design present |
| Topbar-on-other-page guard (over-fix) | ✅ | `test_topbar_chip_appears_on_non_auto_merge_page` hits `/queue` and asserts compact chip class present |
| CSS class attribute-scoped | ✅ | `auto-merge-chip--compact` checked with `re.search(r'class\s*=\s*"[^"]*\bauto-merge-chip--compact\b[^"]*"', response.text)` |
| Targeted-run discipline | ✅ | Both files named explicitly in test command |
| Bug fixed during test writing | ✅ | `test_default_events_view_excludes_non_auto_merge` had missing `db_session.add()` for `auto_merge_health_probe` — fixed |

## Test Coverage Mapping

| Design Test | Implementation |
|-------------|----------------|
| `test_list_recent_events_default_excludes_non_auto_merge` | ✅ `test_list_recent_events_default_excludes_non_auto_merge` (unit) |
| `test_list_recent_events_include_non_auto_merge_shows_everything` | ✅ `test_list_recent_events_include_non_auto_merge_shows_everything` (unit) |
| `test_list_recent_events_explicit_event_type_filter_overrides_prefix_default` | ✅ `test_list_recent_events_event_type_filter_takes_precedence` (unit) |
| `test_auto_merge_page_renders_exactly_one_chip` | ✅ `test_auto_merge_page_renders_exactly_one_chip` (dashboard) |
| `test_topbar_chip_appears_on_non_auto_merge_page` | ✅ `test_topbar_chip_appears_on_non_auto_merge_page` (dashboard) |
| `test_default_events_view_excludes_non_auto_merge` | ✅ `test_default_events_view_excludes_non_auto_merge` (dashboard) |
| `test_show_all_toggle_includes_non_auto_merge_events` | ✅ `test_show_all_toggle_includes_non_auto_merge_events` (dashboard) |
| `test_show_all_toggle_button_renders_with_correct_aria_pressed` | ✅ `test_show_all_toggle_button_renders_with_correct_aria_pressed` (dashboard) |

## Findings

None. All mandatory checks pass.

## TDD RED Evidence

N/A — S07 is a coverage step (tests-impl). The unit tests were already written and verified by S03 (backend-impl) in TDD red/green cycle.

## Verdict

**PASS** — all checks green.