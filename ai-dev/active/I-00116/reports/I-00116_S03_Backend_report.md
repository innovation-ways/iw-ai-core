# I-00116 S03 Backend Report

## What Was Done

Implemented the **cumulative per-work-item review-relaunch cap** (S03 of I-00116), adding a hard limit on how many times a `code_review` or `code_review_final` step can be re-launched for a single work item.

**Root cause addressed** (sub-bug 3 from the design): `fix_cycle.py` capped fix cycles per-step (5) but not cumulatively per work-item. Because every fix-cycle completion resets ALL downstream review steps, a single item's review steps could churn 40+ relaunches while no individual step approached its own cap.

## Files Changed

- `orch/daemon/fix_cycle.py`
- `orch/daemon/batch_manager.py`

## Changes Detail

### `orch/daemon/fix_cycle.py`

1. **New env var** `MAX_REVIEW_RELAUNCHES_PER_ITEM = int(os.getenv("IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM", "15"))` — read at module load with explicit default 15. One-line comment cites I-00116 and the daemon design doc.

2. **`_count_review_relaunches(db, project_id, work_item_id)`** — counts cumulative `StepRun` rows for `code_review`/`code_review_final` steps of this work item. Uses `db.execute(select(func.count(StepRun.id)).join(WorkflowStep, ...).where(...))` matching the project's SQLAlchemy 2.0 `select(...).where(...)` style. Counting from the DB (not in-memory) ensures the counter survives daemon restarts.

3. **`_transition_item_to_failed_for_loop(db, project_id, work_item_id, relaunch_count)`** — idempotent transition:
   - Returns early if item is already `failed`
   - Sets `WorkItem.status = WorkItemStatus.failed`
   - Queries the last 20 review `StepRun` rows for diagnostics
   - Emits `DaemonEvent` of type `review_relaunch_cap_exceeded` with `event_metadata` (NOT `metadata`) carrying `work_item_id`, `cap`, `actual_count`, and `review_step_runs` list
   - Logs `ERROR orch.daemon.fix_cycle: I-00116 review relaunch cap exceeded for %s: %d/%d` with `%`-style placeholders

### `orch/daemon/batch_manager.py`

In `_launch_step()`, right after `worktree_path` is resolved and before runtime resolution:

```python
if step.step_type in (StepType.code_review, StepType.code_review_final):
    from orch.daemon import fix_cycle as fc
    relaunch_count = fc._count_review_relaunches(db, self.project_id, step.work_item_id)
    if relaunch_count >= fc.MAX_REVIEW_RELAUNCHES_PER_ITEM:
        fc._transition_item_to_failed_for_loop(db, self.project_id, step.work_item_id, relaunch_count)
        return
```

This fires on every review-step launch — including the initial launch, first retry, etc. The counter is already ≥1 at this point, so the cap (15) is generous enough to allow legitimate fix cycles while catching pathological loops well before the theoretical max (~40).

## Env Var Added

```
IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM (default: 15)
```

Read at module load in `fix_cycle.py`. **NOT added to `orch/config.py`** — that file is outside `scope.allowed_paths` for this step.

## TDD RED Evidence

Pre-fix `fix_cycle.py` / `batch_manager.py` has **no per-item relaunch counter**; the S07 cap-overflow test (`tests/integration/test_fix_cycle_review_relaunch_cap.py`) will fail because:

1. No `review_relaunch_cap_exceeded` `DaemonEvent` is ever emitted — the event type is only emitted by the new `_transition_item_to_failed_for_loop()` which is never called without the cap check.
2. The work item stays in `in_progress` indefinitely — `WorkItem.status` is never set to `failed` by the relaunch path since there is no code to do so.

After S07 implements the test: it launches ≥15 review steps for a single work item and asserts that the 16th launch is blocked, the work item is `failed`, and the expected `DaemonEvent` is recorded.

## Post-Edit Gates

```json
{
  "make format-check": "pass",
  "make lint": "pass"
}
```

Both `make format-check` (ruff format) and `make lint` (ruff check) pass with no violations introduced by these changes.

## Notes

- The cap check fires before every `code_review` / `code_review_final` launch — initial and relaunch alike. The DB counter includes all runs, so the check naturally excludes the very first launch (count = 1, cap = 15). Pathological loops trigger when a fix-cycle completion causes the same review step(s) to be re-launched repeatedly; each such re-launch increments the counter until the cap is hit.
- `MAX_REVIEW_RELAUNCHES_PER_ITEM` is intentionally NOT added to `orch/config.py` — that file is outside this step's `scope.allowed_paths`, and S04 (CodeReview_Backend) would flag it as a CRITICAL scope violation.
- The cap default of 15 was chosen per the design doc: with 5 review steps × 5 per-step cycles, the theoretical max is ~25. A cap of 15 is tight enough to break loops within minutes while leaving room for legitimate multi-step fix convergence.
