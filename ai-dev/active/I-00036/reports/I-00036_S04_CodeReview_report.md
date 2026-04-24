# I-00036 S04 Code Review Report

## Summary

Final cross-agent review of the S01 backend fix to the batch progress bar (step-level vs item-level progress). The change is correct and passes all quality gates.

## Files Changed

| File | Action | Purpose |
|------|--------|---------|
| `dashboard/routers/batches.py` | Modified | Rewrote `_all_batches()` to compute `progress_pct` from `WorkflowStep` done/skipped counts |

## Implementation Review

### S01 Backend Fix (lines 195–246)

**Root cause addressed**: `progress_pct` was computed from `BatchItem` completed/merged counts, causing 0→100 jumps when items finished.

**Fix**: Now queries `WorkflowStep` rows and computes `progress_pct = done_steps / total_steps * 100` where done = completed + skipped.

**Edge case handling**: `pct = 0` when `total_steps = 0` (no division by zero).

**Observability fields unchanged**: `total_items` and `completed_items` still drive the "Items" column (item-level counts).

## Quality Checks

| Check | Result |
|-------|--------|
| `ruff check dashboard/routers/batches.py` | ✅ All checks passed |
| `mypy dashboard/routers/batches.py` | ✅ No issues found |
| Unit tests (test_batch_archiver.py, test_batch_planner.py) | ✅ 27 passed |
| Integration tests (test_batch_archive.py, test_batch_manager.py, test_cli_batches.py) | ✅ 37 passed |
| Dashboard tests (non-browser, non-conflicting) | ✅ 89 passed |

## Issues / Observations

**MEDIUM (pre-existing, not introduced by S01)**: `project_dashboard.py` has its own `_active_batches()` function (lines 87–147) that still uses item-level progress computation. The batch list page (`/project/{id}/batches`) shows step-level progress correctly, while the project dashboard home (`/project/{id}/`) shows item-level (jumps 0→100). This is a pre-existing issue, not in scope for this fix cycle.

**No blocking issues found.** S01 implementation is correct and complete.

## Verdict

```
pass
```