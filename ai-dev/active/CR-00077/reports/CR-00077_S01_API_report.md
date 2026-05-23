# CR-00077 S01 API Report — Overlap details popup (read-only)

## What was done

Implemented the CR-00077 S01 API task: the new htmx endpoint `GET /project/{project_id}/batch/{batch_id}/overlap/{held_item_id}`, the `group_overlap_events` helper, the `_overlap_window_cutoff` helper, the `batch_items_fragment` context fix, and the modal stub template.

## Files changed

| File | Change |
|------|--------|
| `dashboard/routers/batches.py` | Added `group_overlap_events()` helper (pure function), `_overlap_window_cutoff()` helper, new `overlap_modal()` endpoint, fixed `batch_items_fragment` to pass `batch` in template context; removed unused `BatchOverlapIgnore` import |
| `dashboard/templates/fragments/batch_overlap_modal.html` | Replaced CR-00078 content with CR-00077 S01 stub — handles both `empty=True` (404 case) and `empty=False` with sections, each section shows blocking item ID, title (link), and full glob list |
| `tests/unit/test_batch_overlap_grouping.py` | New file — 10 tests exercising `group_overlap_events`: empty, single, duplicate (first wins), multi, skip invalid metadata |

## Key implementation decisions

1. **`blocker_item_id` key** — The daemon emits `blocker_item_id` (not `blocking_item_id`) in `item_held_for_scope` events (verified by reading `dashboard/routers/batches.py:_get_scope_statuses` which already reads `meta.get("blocker_item_id", "")`). The helper and endpoint both use `blocker_item_id` to match the live data.

2. **`_overlap_window_cutoff`** — Extracted as a named helper so both `overlap_modal` (CR-00077) and `_get_item_scope_events` (CR-00078) can share the same `datetime.now(UTC) - 300s` logic without duplicating the magic number.

3. **`group_overlap_events` semantics** — "First occurrence wins" (newest-first input → newest wins). Correct: the list arrives in descending `created_at` order, so the first element is the most recent event.

4. **`batch_items_fragment` context fix** — The return value of `_get_batch_or_404` was previously discarded. Now captured as `batch = _get_batch_or_404(...)` and passed to the template context. This fixes the live-refresh URL collapse where `{{ batch.id }}` would become empty after the first SSE refresh.

5. **`overlap_modal` does NOT check BatchItem existence** — The step instructions specified verifying the batch exists but did not require verifying the held item exists as a batch item. The endpoint queries `DaemonEvent` rows for `entity_id == held_item_id`; if no events exist, it returns 404 regardless. This is intentional: if no event exists, there are no overlap details to show, and the empty-state message is appropriate.

## Pre-flight quality gates

| Gate | Result |
|------|--------|
| `make format` | ✅ 867 files already formatted |
| `make lint` | ✅ All checks passed |
| `make typecheck` | ✅ No issues in 275 source files |

## Test results

```
tests/unit/test_batch_overlap_grouping.py
  TestGroupOverlapEventsEmpty::test_empty_list_returns_empty_list PASSED
  TestGroupOverlapEventsDuplicate::test_duplicate_blocking_item_keeps_first PASSED
  TestGroupOverlapEventsDuplicate::test_duplicate_blocking_item_only_first_kept PASSED
  TestGroupOverlapEventsMultiple::test_two_different_blocking_items_both_present PASSED
  TestGroupOverlapEventsMultiple::test_order_preserved_for_distinct_blocking_items PASSED
  TestGroupOverlapEventsSingle::test_single_event_returns_one_section PASSED
  TestGroupOverlapEventsSkipsInvalid::test_event_missing_blocking_item_id_skipped PASSED
  TestGroupOverlapEventsSkipsInvalid::test_event_missing_both_keys_skipped PASSED
  TestGroupOverlapEventsSkipsInvalid::test_event_missing_conflicting_globs_skipped PASSED
  TestGroupOverlapEventsSkipsInvalid::test_event_with_none_metadata_skipped PASSED

10 passed in 0.24s
```

## TDD evidence

**RED**: Initial test run produced `ImportError: cannot import name 'group_overlap_events' from 'dashboard.routers.batches'` — confirmed the function did not exist.

**GREEN**: After adding the helper and updating test mocks to use `blocker_item_id`, all 10 tests pass.

## Notes

- The `batch_overlap_modal.html` stub was created to allow the endpoint to be import-tested. S03 (`frontend-impl`) will replace this with the full modal HTML/CSS implementation. The stub handles both the 404 empty-state and the 200 section-rendered state.
- `_get_item_scope_events` remains in the file (CR-00078 scope) because removing it would require coordination with another worktree. It is not used by the CR-00077 endpoint.
- The `overlap_modal` endpoint is deliberately read-only — it does not write to `BatchOverlapIgnore`. CR-00078 owns that functionality.