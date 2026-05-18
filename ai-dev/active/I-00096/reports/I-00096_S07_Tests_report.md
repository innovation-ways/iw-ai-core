# I-00096 S07 Tests Report

## What Was Done

Wrote regression tests for chip deduplication (AC1/AC2) and the auto-merge-only default filter with Show-All toggle (AC3/AC4/AC5).

## Test Coverage

### Unit tests (`tests/unit/test_auto_merge_aggregator.py`)

All three tests were already added by S03 (backend-impl) and are preserved here as the canonical location:

| Test | What it verifies |
|------|-----------------|
| `test_list_recent_events_default_excludes_non_auto_merge` | Default call returns only `auto_merge_*` / `merge_auto_*` events; `step_launched` is excluded |
| `test_list_recent_events_include_non_auto_merge_shows_everything` | `include_non_auto_merge=True` bypasses prefix filter |
| `test_list_recent_events_event_type_filter_takes_precedence` | Explicit `event_type_filter` overrides the prefix default |

### Dashboard tests (`tests/dashboard/test_auto_merge_routes.py`)

Five new tests added for I-00096:

| Test | What it verifies |
|------|-----------------|
| `test_auto_merge_page_renders_exactly_one_chip` | AC1: `/auto-merge` page has exactly one `id="auto-merge-status-chip"` |
| `test_topbar_chip_appears_on_non_auto_merge_page` | AC2: `/queue` still renders the compact topbar chip when phase >= 1 |
| `test_default_events_view_excludes_non_auto_merge` | AC3: default `/auto-merge/events` shows only auto-merge events |
| `test_show_all_toggle_includes_non_auto_merge_events` | AC4: `?all=1` includes both auto-merge and non-auto-merge events |
| `test_show_all_toggle_button_renders_with_correct_aria_pressed` | AC5: toggle button present with correct `aria-pressed` state for both default and `?all=1` |

## Bug Fixed During Test Writing

`test_default_events_view_excludes_non_auto_merge` had a missing `db_session.add()` for the `auto_merge_health_probe` event — it was constructed but never flushed to the database. The test passed only because `db_session.add()` was called for `step_launched` but the auto-merge event was not persisted. Fixed by wrapping the auto-merge event in `db_session.add()` before flushing.

## Pre-flight Quality Gates

```
make format  — ok (0 files need reformatting after uv run ruff format)
make typecheck — ok (no issues in 255 source files)
make lint   — ok (all checks passed)
```

## Test Results

```
uv run pytest tests/unit/test_auto_merge_aggregator.py tests/dashboard/test_auto_merge_routes.py -v --no-cov
64 passed, 0 failed
```

All 22 unit tests + 42 dashboard tests in the two files pass.

## TDD RED Evidence

`tdd_red_evidence = "n/a — coverage step (tests-impl)"`

This is a coverage step (tests-impl); implementation was done in S03/S05. The unit tests for the aggregator were written and verified red/green by S03.

## Notes

- Unit tests use `MagicMock` to simulate SQL-level filtering. Dashboard tests use real DB via testcontainers, confirming the full stack works end-to-end.
- `test_show_all_toggle_button_renders_with_correct_aria_pressed` uses `re.search` with attribute-scoped class matching per I-00067 conventions.
- The 5 new I-00096 tests join existing regression coverage (I-00091, I-00092, I-00097) already in the same file.
- Blockers: None.