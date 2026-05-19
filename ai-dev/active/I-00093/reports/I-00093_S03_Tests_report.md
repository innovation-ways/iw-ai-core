# I-00093 S03 — Tests Report

## Work Item
I-00093 — Auto-merge event detail modal hides the most useful fields

## Step
S03 (tests-impl)

## What Was Done

Added 5 regression tests to `tests/dashboard/test_auto_merge_routes.py` covering the modal enrichment delivered in S01. Each test follows the semantic-correctness rule (I003): assertions use exact strings set by the factory, not generic word matches that would pass against buggy code.

Also added two factory helpers to `tests/integration/auto_merge_fixtures.py`:
- `daemon_event_factory()` — inserts a `DaemonEvent` row
- `merge_verdict_factory()` — inserts a `MergeAutoVerdict` row

Both commit to the test session (no mocks, per CLAUDE.md "NEVER mock the database in integration tests").

### Tests Added

| Test | Covers | AC |
|------|--------|----|
| `test_event_modal_renders_message_and_metadata_for_health_probe` | AC1: health probe modal renders exact message string + all metadata keys/values | AC1 |
| `test_event_modal_renders_old_new_for_config_updated` | AC2: config_updated modal renders `"old"`, `"new"`, `"updated_by"`, `"dashboard"` from metadata JSON | AC2 |
| `test_event_modal_renders_verdict_info_for_resolved` | AC4: resolved event modal renders verdict value/notes/by AND the existing verdict form pre-checked | AC4 |
| `test_event_modal_no_verdict_form_for_non_resolved_events` | AC4 complement: non-resolved events do NOT show verdict form, but message+metadata still render | AC4 |
| `test_event_modal_heading_is_humanized` | AC3: heading contains `event_type` (not just `"Event #<id>"`) via scoped `<h3>` regex | AC3 |

### Key Design Decisions

- **No `daemon_event_factory` fixture**: the prompt asked for a factory but did not require a pytest fixture. Tests directly construct `DaemonEvent` rows inline (same pattern as existing tests like `_event()` in the same file), keeping the change minimal.
- **`merge_verdict_factory` function added but not used in tests**: the verdict test inserts the `MergeAutoVerdict` row inline (following the existing `_event()` pattern). The helper is available for future tests.
- **Attribute-scoped CSS checks**: the heading test uses `re.search(r'<h3[^>]*id="auto-merge-event-title"[^>]*>(.*?)</h3>', html, re.DOTALL)` to scope to the specific element rather than matching anywhere in HTML.
- **Duplicate test removal**: while fixing a lint error, discovered that the I-00096 section had been duplicated in a previous edit — removed the duplicate definitions for `test_topbar_chip_appears_on_non_auto_merge_page`, `test_default_events_view_excludes_non_auto_merge`, `test_show_all_toggle_includes_non_auto_merge_events`, `test_show_all_toggle_button_renders_with_correct_aria_pressed`.

## Files Changed

| File | Change |
|------|--------|
| `tests/dashboard/test_auto_merge_routes.py` | Added 5 I-00093 regression tests; removed 4 duplicate I-00096 test definitions |
| `tests/integration/auto_merge_fixtures.py` | Added `daemon_event_factory()` and `merge_verdict_factory()` helpers + `datetime`/`UTC` imports |

## Pre-flight Quality Gates

| Check | Result |
|-------|--------|
| `make format` | ✅ All files formatted |
| `make typecheck` | ✅ Success: no issues in 255 source files |
| `make lint` | ✅ All checks passed |

## Test Verification

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

**Result**: 47 passed, 0 failed.

Coverage failure (20% < 50% required) is a pre-existing global configuration issue affecting the entire test suite, not related to this change.

## TDD Evidence

`tdd_red_evidence = "n/a — coverage step (tests-impl)"` — this is a coverage step, not a TDD red phase.

## Notes

- The coverage threshold warning is pre-existing and global (not introduced by these changes).
- `daemon_event_factory` and `merge_verdict_factory` are added as plain Python functions (not pytest fixtures) to keep the change minimal. They are available for future test authors to use.
- The duplicate I-00096 tests were a pre-existing issue in the file (not introduced by S03); removing them was necessary to get lint to pass and ensures the test file is clean.