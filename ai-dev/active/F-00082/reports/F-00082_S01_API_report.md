# F-00082_S01_API_report — Dashboard Cancel Buttons: API Layer

## Step: S01
**Agent**: API (`api-impl`)
**Work Item**: F-00082 — Dashboard Cancel Buttons (Batch + Work Item)
**Date**: 2026-05-14

---

## What Was Done

### 1. Created `orch.cancel` — shared cancellation service layer

**File**: `orch/cancel.py` (new, 516 lines)

Implements the canonical `cancel_work_item()` and `cancel_batch()` functions used by both the dashboard API and CLI. Includes:

- **Status sets**: `CANCELLABLE_WORK_ITEM_STATUSES`, `CANCELLABLE_BATCH_STATUSES`, `_ACTIVE_BATCH_STATUSES` — mirrors the service-layer design.
- **`CancelWorkItemResult`** dataclass: `new_status`, `reason`, `teardown_errors`.
- **`CancelBatchResult`** dataclass: `new_batch_status`, `cancelled_batch_items`, `reset_to_draft`, `killed_pids`, `teardown_errors`.
- **`cancel_work_item()`**: Validates item status + active-batch guard, kills running step processes via `SIGTERM`, resets steps to `pending` if `to_draft=True`, tears down worktree via `git worktree remove` and compose stack via `docker compose down`, emits `DaemonEvent`.
- **`cancel_batch()`**: Validates batch status, iterates non-terminal `BatchItem`s, kills PIDs, teardown compose + worktree, updates all member `WorkItem` statuses, emits `DaemonEvent`.
- **`_teardown_item_worktree()` / `_teardown_compose_stack()`**: Best-effort helpers — errors are appended to `teardown_errors` but never raise.

### 2. Rewrote `POST /project/{project_id}/api/item/{item_id}/cancel`

**File**: `dashboard/routers/actions.py`

- Now accepts `reason: str = Form("cancelled by operator")` and `to_draft: bool = Form(False)`.
- Delegates to `orch.cancel.cancel_work_item()`.
- Maps `LookupError` → 404, `ValueError("active batch" in msg)` → 409, other `ValueError` → 422.
- Builds toast message naming the new status + reason; appends one warning line per `teardown_error`.

### 3. Rewrote `POST /project/{project_id}/api/batch/{batch_id}/cancel`

**File**: `dashboard/routers/actions.py`

- Accepts `reason: str = Form("cancelled by operator")` and `reset_items: bool = Form(False)`.
- Delegates to `orch.cancel.cancel_batch()` (imported as `_cancel_batch` to avoid shadowing the endpoint).
- Maps `LookupError` → 404, `ValueError` → 422 (no 409 carve-out for batch).
- Builds toast message listing `cancelled_batch_items`, `reset_to_draft`, `killed_pids`; appends warning per `teardown_error`.

### 4. Extended confirm-dialog GET handlers for cancel action

**File**: `dashboard/routers/actions.py`

- `confirm_item_dialog()` (line 761): When `action == "cancel"`, uses template `fragments/confirm_action_form.html` with `default_reason`, `reset_field_name="to_draft"`, `reset_field_label="Also reset item to draft (re-runnable)"`.
- `confirm_batch_dialog()` (line 1503): When `action == "cancel"`, uses template `fragments/confirm_action_form.html` with `default_reason`, `reset_field_name="reset_items"`, `reset_field_label="Also reset member items to draft (re-runnable)"`.
- For all other actions, the existing `fragments/confirm_action.html` is used (no regression for approve/pause/resume/restart).

**Note**: The fragment file `confirm_action_form.html` is referenced by name only — it is created by S03 (Frontend).

### 5. Updated `_ACTION_LABELS` for cancel entries

**File**: `dashboard/routers/actions.py`

- **Item cancel**: title `"Cancel Item?"`, description mentions process kill, step skip, worktree teardown, and optional draft reset, confirm label `"Cancel Item"`, danger `True`.
- **Batch cancel**: title `"Cancel Batch?"`, description mentions killing all non-terminal items and worktree teardown, confirm label `"Cancel Batch"`, danger `True`.

### 6. Added `orch/cancel.py` to pyproject.toml lint allowlist

**File**: `pyproject.toml` — added `"orch/cancel.py": ["S603", "S607"]` (git/docker subprocess calls are intentional for worktree teardown).

### 7. Wrote TDD anchor tests

**Files**: `tests/dashboard/test_actions_cancel_item.py`, `tests/dashboard/test_actions_cancel_batch.py` (10 tests total, all passing):

| Test | What It Verifies |
|------|-----------------|
| `test_cancel_item_calls_service_layer_with_form_params` | POST with `reason`/`to_draft` calls `orch.cancel.cancel_work_item` with correct args |
| `test_cancel_item_maps_lookup_error_to_404` | `LookupError` → HTTP 404 |
| `test_cancel_item_maps_active_batch_value_error_to_409` | `ValueError` with "active batch" → HTTP 409 |
| `test_cancel_item_success_builds_toast_with_status` | 204 + `HX-Trigger` with `showToast` + `reload` |
| `test_cancel_item_teardown_errors_append_warning_to_toast` | teardown errors appear in toast |
| `test_cancel_batch_calls_service_layer_with_form_params` | POST with `reason`/`reset_items` calls `orch.cancel.cancel_batch` with correct args |
| `test_cancel_batch_maps_lookup_error_to_404` | `LookupError` → HTTP 404 |
| `test_cancel_batch_maps_value_error_to_422` | `ValueError` → HTTP 422 (no 409 for batch) |
| `test_cancel_batch_success_builds_toast_with_summary` | 204 + toast with cancelled items list |
| `test_cancel_batch_teardown_errors_append_warning_to_toast` | teardown errors appear in toast |

---

## Files Changed

| File | Change |
|------|--------|
| `orch/cancel.py` | **NEW** — service layer with `cancel_work_item` and `cancel_batch` |
| `dashboard/routers/actions.py` | Rewrote both cancel endpoints; extended GET handlers; updated `_ACTION_LABELS` |
| `tests/dashboard/test_actions_cancel_item.py` | **NEW** — 5 anchor tests |
| `tests/dashboard/test_actions_cancel_batch.py` | **NEW** — 5 anchor tests |
| `pyproject.toml` | Added `orch/cancel.py` to S607 allowlist |

---

## Test Results

```
10 passed in 6.79s
```

### TDD RED Evidence

Initial tests written before `orch.cancel` existed — the RED was `AttributeError: <module 'dashboard.routers.actions'> does not have the attribute 'cancel_work_item'` (when patching `dashboard.routers.actions.cancel_work_item`).

After creating `orch.cancel` and patching it correctly (`patch("orch.cancel.cancel_work_item")`), tests went green.

Final RED-to-GREEN was for the positional-vs-kwargs call assertion — `call_args.kwargs` was empty because FastAPI injects `db`, `project_id`, `item_id` as positional args and `reason`/`to_draft` as kwargs. Fixed by using `call_args.args[1]` and `call_args.args[2]` for positional params.

---

## Preflight

| Check | Result |
|-------|--------|
| `make format` | ok (679 files already formatted) |
| `make typecheck` | ok (0 mypy errors on `orch/cancel.py` + `dashboard/routers/actions.py`) |
| `make lint` | ok (0 errors on changed files) |

---

## Notes

- The `confirm_action_form.html` fragment is created by S03 (Frontend). S01 references it by name — the contract is the GET handler passing `default_reason`, `reset_field_name`, and `reset_field_label` context variables.
- `orch.cancel._teardown_compose_stack()` has an unused `batch_item_id` parameter (kept for API symmetry with `orch.daemon.worktree_compose.down()`). Renamed to `_batch_item_id` to silence ARG001.
- The `new_item_status` local variable was removed from `cancel_batch()` — it was assigned but never used since the actual status determination is done inline in the loop.

---

## Blockers

None.