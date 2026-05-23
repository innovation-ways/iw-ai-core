# CR-00078 S04 Backend Report

## What Was Done

Implemented the CR-00078 per-batch overlap ignore daemon hook:

1. **Pure helper** — Added `filter_blocked_by_ignores()` to `orch/daemon/scope_overlap.py` (no new module; keeping DB-free purity in the overlap module):
   - Takes `blocked_by: list[tuple[str, list[str]]]` and `ignored_pairs: set[tuple[str, str]]`
   - Drops each `(blocking_id, glob)` whose pair is in `ignored_pairs`
   - Drops tuples whose globs list becomes empty
   - Pure function, no DB access

2. **Daemon hook** — In `batch_manager._process_batch()`, after the `scope_overlap.find_blocking_items()` call and before the existing `if blocked_by:` branch:
   - Queries `BatchOverlapIgnore` scoped by `project_id`, `batch_id`, `held_item_id`
   - Calls `filter_blocked_by_ignores()` to narrow `blocked_by`
   - Emits `batch_overlap_allowed_by_ignore` event when all pairs were ignored
   - **Always reassigns** `blocked_by = filtered_blocked_by` on every path (critical invariant)
   - Falls through to launch path when ignore clears all conflicts

3. **TDD RED anchor** — `tests/unit/test_daemon_overlap_filter.py` has `test_empty_ignores_returns_input` (imported from `scope_overlap`, not a new module), which passes now that the helper is implemented.

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/scope_overlap.py` | Added `filter_blocked_by_ignores()` pure helper at end of module |
| `orch/daemon/batch_manager.py` | Added `from sqlalchemy import select`, `BatchOverlapIgnore` import, `filter_blocked_by_ignores` import, CR-00078 hook block between `find_blocking_items` and existing `if blocked_by:` |
| `tests/unit/test_daemon_overlap_filter.py` | New file with RED anchor test |

## Test Results

```
tests/unit/test_daemon_overlap_filter.py::TestFilterBlockedByIgnoresEmpty::test_empty_ignores_returns_input — 1 passed
```

## Preflight

| Gate | Result |
|------|--------|
| `make format` | ok |
| `make typecheck` | ok |
| `make lint` | ok |

## Notes

- Chose to add the helper to `scope_overlap.py` rather than a new module because it is tightly coupled to the overlap gate's data structures (`list[tuple[str, list[str]]]`) and must be importable without pulling in SQLAlchemy machinery.
- Helper location: `orch.daemon.scope_overlap.filter_blocked_by_ignores` — imported as such in both `batch_manager.py` and the test.
- The `batch_overlap_allowed_by_ignore` event is emitted only when ignores actually cleared the hold (`not filtered_blocked_by and ignored_pairs`). The existing `item_held_for_scope` path remains unchanged for real (non-ignored) conflicts.
- The reassignment `blocked_by = filtered_blocked_by` is placed after the event emission, ensuring that both the event and the reassignment fire on the "all ignored" path — the item falls through to the launch decision below.