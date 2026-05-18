# I-00099 S01 Backend Report

## What was done

Removed the sibling-directory fallback from `orch/daemon/scope_overlap.py` (I-00099, 2026-05-18):

1. **Deleted `_same_parent()`** (former lines 128–132) — the helper function that compared parent directories.
2. **Removed the sibling-case fallback inside `find_blocking_items()`** (former lines 160–168) — the `if not intersecting: for cp in candidate_paths: for ifp in in_flight_paths: if _same_parent(cp, ifp): ...` block. The function now returns `globs_intersect` results directly.
3. **`globs_intersect()` and `_strip_test_globs()` were not modified** — byte-identical to the pre-fix version.
4. **Updated the module docstring** to document the removal, the remaining safety nets, and the two concrete false-positive cases that motivated it.

## Files changed

- `orch/daemon/scope_overlap.py` — 173 lines (down from 190), 17 lines removed

## Caller contract confirmation

`batch_manager.py:_launch_pending_items` (line 397–416) calls `find_blocking_items()` and extracts `conflicting_globs` for the `item_held_for_scope` event message: `f"Held: {item.work_item_id} overlaps with {blocking_id} on {', '.join(conflicting_globs[:3])}"`. With the sibling fallback gone, `conflicting_globs` now always originate from `globs_intersect` — real intersecting paths, not a misleading candidate-side sibling path. **The contract is intact**; the message is now accurate by construction.

## Preflight quality gates

| Gate | Result |
|------|--------|
| `make format` | ok (750 files already formatted) |
| `make typecheck` | ok (no issues in 255 source files) |
| `make lint` | ok (all checks passed) |

## Test results

```
uv run pytest tests/unit/daemon/test_scope_overlap.py -v
46 passed, 2 failed
```

- **All glob-intersect, test-path stripping, and I-00071 regression tests: PASS**
- **`test_non_test_sibling_still_blocks`: FAIL** — expected; this test validates the sibling rule that was just removed. S03 (tests-impl) will delete it.
- **`test_blocks_multiple_in_flight`: FAIL** — this test expected `src/app/config.py` to block `src/app/main.py` via sibling-directory logic. With the sibling rule removed, no such block exists (no `dir/**` glob was declared). S03 will update this test to remove the incorrect assertion.

## Notes

- `test_blocks_multiple_in_flight` was relying on the sibling fallback to fire a block between `src/app/main.py` (candidate) and `src/app/config.py` (in-flight). This is the same false-positive pattern described in the issue — two different files in the same directory blocking each other without any explicit glob intersection. S03 fixes both failing tests.
- The coverage failure (`total of 3 is less than fail-under=50`) is a pre-existing environment issue — the test run covers only `tests/unit/daemon/test_scope_overlap.py` (module coverage 94%), not the full project. `make check` runs the full suite with proper coverage aggregation.