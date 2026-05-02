# CR-00029 S01 Backend Report

## What Was Done

### 1. `StepDetail` dataclass (`dashboard/routers/items.py`)

Added `restartable: bool = False` field to the `StepDetail` dataclass (line 63). Non-synthetic rows default to `False` so existing callers are unaffected.

### 2. `_synthetic_setup_step` factory (`dashboard/routers/items.py`)

Updated the factory signature from `(bi: BatchItem | None) -> StepDetail` to `(bi: BatchItem | None, step_statuses: list[str] | None = None) -> StepDetail`.

The `restartable` flag is computed as (lines 597–603):

```python
restartable = (
    bi is not None
    and step_statuses is not None
    and bi.status in (BatchItemStatus.setup_failed, BatchItemStatus.failed)
    and step_statuses == ["pending"] * len(step_statuses)
)
```

This means restartable is `True` iff:
- A `BatchItem` exists (`bi is not None`)
- `step_statuses` was provided (not `None`)
- The `BatchItem.status` is `setup_failed` or `failed` (cascade scenario)
- All workflow steps are still `pending` (no step has started)

Empty step list → all 0 steps are "pending" → `restartable = True`.

The caller at line 432 was updated to compute `step_statuses = [s.status.value for s in workflow_steps]` and pass it to `_synthetic_setup_step(bi, step_statuses)`.

### 3. `_reset_item_to_approved` helper (`dashboard/routers/actions.py`)

Extracted shared logic into a private helper function (lines 1043–1116):
- Collects all `WorkflowStep` rows for the item
- Deletes all `StepRun` rows + unlinks log files
- Resets all `WorkflowStep` fields to `pending`/null
- Sets `WorkItem.status = approved`
- Resets `BatchItem.status = pending` (with notes/started_at cleared)
- Reopens `Batch` if it was `completed_with_errors`
- Emits a daemon event with configurable `event_type` and `event_message`
- Commits the transaction
- Best-effort deletes the worktree directory

### 4. `full_restart_item` refactored (`dashboard/routers/actions.py`)

The endpoint body (lines 1137–1172) now reduces to:
- Status precondition check (422 if not in `_FULL_RESTART_ALLOWED`)
- Call `_reset_item_to_approved(..., event_type="item_full_restarted", event_message=...)`
- Return `_action_response(...)`

### 5. New `restart_setup` endpoint (`dashboard/routers/actions.py`)

Added `POST /project/{project_id}/api/item/{item_id}/restart-setup` (lines 1175–1231) with:
- Precondition 1: `BatchItem.status in {setup_failed, failed}` → 422 if absent
- Precondition 2: no `WorkflowStep.status != pending` → 422 if any step has progressed
- Calls `_reset_item_to_approved(..., event_type="setup_restarted", ...)`
- Returns success response

### 6. Dialog registration in `_ITEM_ACTION_LABELS` (`dashboard/routers/actions.py`)

Added `"restart-setup"` entry (lines 123–130):
```python
"restart-setup": (
    "Restart setup?",
    "This deletes the worktree and resets every step. "
    "The daemon will re-run setup from scratch.",
    "Restart Setup",
    True,  # destructive
),
```

This plugs into the existing `confirm_item_dialog` dispatcher without requiring a new GET handler.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/items.py` | `StepDetail.restartable` field added; `_synthetic_setup_step` signature/logic updated; caller updated |
| `dashboard/routers/actions.py` | `_reset_item_to_approved` helper extracted; `full_restart_item` refactored; `restart_setup` endpoint added; `_ITEM_ACTION_LABELS` extended |
| `tests/dashboard/test_restart_setup_backend.py` | 11 smoke tests (7 unit + 4 integration) |

## Test Results

- **11 new tests pass** (7 unit for `_synthetic_setup_step` restartable logic; 4 endpoint tests)
- **Pre-existing test failures** in `test_safe_migrate.py` are unrelated to this CR (confirmed by running on clean stash — same failures present)
- **Lint**: All checks pass on changed files
- **Typecheck**: `mypy` reports no issues

## Notes

- **Helper signature**: `_reset_item_to_approved(db, project_id, item_id, *, event_type, event_message)` — all state changes inside, commits internally, deletes worktree best-effort.
- **`full_restart_item` behavior**: Identical to before — same preconditions, same state transitions, same worktree deletion, same event metadata keys. Only the code structure changed.
- **Dialog template**: No new template needed — `confirm_item_dialog` reads the `_ITEM_ACTION_LABELS` dict and renders `fragments/confirm_action.html` automatically. The POST URL becomes `/project/{project_id}/api/item/{item_id}/restart-setup` (matching the endpoint).
- **Empty `step_statuses`**: An empty list `[]` means 0 steps defined yet (restartable=True). This is consistent with the design intent: if no steps have run, the item is in a setup-only failure state.
