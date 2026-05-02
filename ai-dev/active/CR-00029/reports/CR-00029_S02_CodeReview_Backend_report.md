# CR-00029 S02 Code Review Report (Backend)

## What Was Reviewed

S01 (backend-impl) implemented:
1. `StepDetail.restartable: bool = False` field (default False so non-synthetic rows are unaffected)
2. `_synthetic_setup_step(bi, step_statuses)` computes restartable = True when BatchItem.status ∈ {setup_failed, failed} AND all steps still pending
3. Private helper `_reset_item_to_approved(db, project_id, item_id, *, event_type, event_message)` extracted from `full_restart_item`
4. `full_restart_item` refactored to delegate to the helper
5. New `POST /project/{project_id}/api/item/{item_id}/restart-setup` endpoint with dual precondition gates
6. `"restart-setup"` entry added to `_ITEM_ACTION_LABELS` so `confirm_item_dialog` dispatcher handles it automatically

## Files Changed

| File | Change Summary |
|------|----------------|
| `dashboard/routers/actions.py` | `_reset_item_to_approved` helper extracted (lines 1049–1141); `full_restart_item` refactored (lines 1144–1173); `restart_setup` endpoint added (lines 1176–1235); `_ITEM_ACTION_LABELS` extended with `restart-setup` (lines 123–129) |
| `dashboard/routers/items.py` | `restartable: bool = False` added to `StepDetail` (line 63); `_synthetic_setup_step` signature updated + restartable logic (lines 564–617); caller updated (line 432) |
| `tests/dashboard/test_restart_setup_backend.py` | 11 new tests (7 unit for restartable flag logic, 4 integration for endpoint preconditions and success paths) |

## Pre-Review Gate Results

| Check | Result |
|-------|--------|
| `make lint` (all files) | FAIL — 5 W292 trailing-newline violations in unrelated `ai-dev/active/I-*/e2e_fixtures/*.py` files |
| `make format` (all files) | FAIL — 3 files would be reformatted (same unrelated fixtures) |
| `make lint` (changed files only: `dashboard/routers/actions.py`, `dashboard/routers/items.py`) | PASS — all checks passed |
| `make format` (changed files only) | PASS — both files already formatted |
| `uv run mypy dashboard/routers/actions.py dashboard/routers/items.py` | PASS — no issues found |

The global lint/format failures are pre-existing (unrelated `ai-dev/active/I-00058` and `I-00059` fixtures), not regressions from S01 changes.

## Checklist Verification

### 1. `StepDetail.restartable` & `_synthetic_setup_step`

- **Field**: `restartable: bool = False` at line 63 of `items.py` — correct default (False), non-synthetic rows unaffected.
- **Inline comment**: "CR-00029: true iff setup_failed/failed with all steps still pending" — present and accurate.
- **Computation** (lines 598–603):
  ```python
  restartable = (
      bi is not None
      and step_statuses is not None
      and bi.status in (BatchItemStatus.setup_failed, BatchItemStatus.failed)
      and step_statuses == ["pending"] * len(step_statuses)
  )
  ```
  Matches AC1/AC2: requires both setup-recoverable status AND all steps pending. Empty `step_statuses` (no steps defined yet) correctly yields `restartable=True` (0 steps are pending).
- **Caller** at line 431–432: `step_statuses = [s.status.value for s in workflow_steps]` then `_synthetic_setup_step(bi, step_statuses)` — all callers updated.

### 2. Helper extraction (`_reset_item_to_approved`)

- **Signature**: `_reset_item_to_approved(db, project_id, item_id, *, event_type, event_message)` — private (leading underscore), parametrized event fields.
- **No behavior change in `full_restart_item`**: 
  - The original `full_restart_item` body performed: status-precondition check → DB query for steps → iterate steps (delete runs + unlink logs) → reset step fields → load WorkItem → reset status → load BatchItem → reset batch → reopen batch if `completed_with_errors` → emit event → commit → delete worktree.
  - The new helper performs the **identical sequence** in the **same order**, just parametrized on event_type/event_message.
  - `full_restart_item` (lines 1144–1173): precondition → helper call → response. No logic was lost or reordered.
- **No dead `_FULL_RESTART_ALLOWED` checks** duplicated inside the helper — the helper is called after the caller performs its own precondition.

### 3. `restart_setup` endpoint

- **Precondition 1** (lines 1189–1202): `BatchItem.status in {setup_failed, failed}` — 422 with clear message "Cannot restart setup: no BatchItem in setup_failed/failed status for {item_id}".
- **Precondition 2** (lines 1204–1221): no `WorkflowStep.status != pending` — 422 with "Cannot restart setup: at least one step has progressed past pending for {item_id}. Use the full restart action instead."
- **Success path**: calls `_reset_item_to_approved(..., event_type="setup_restarted", ...)` — right event name.
- **Response**: `_action_response(...)` with toast and `reload=True` — consistent with existing endpoints.

### 4. `_ITEM_ACTION_LABELS` registration

- `restart-setup` entry (lines 123–129): title "Restart setup?", description matching design spec, confirm label "Restart Setup", `danger=True`.
- **No custom GET handler added** — the existing `confirm_item_dialog` dispatcher (line 699) at `/project/{project_id}/api/confirm-item/{action}/{item_id}` handles it via the dict lookup.
- The title template in `confirm_item_dialog` (line 723): `f"{title.rstrip('?')} {item_id}?"` → "Restart setup CR00029-no-batch?" — matches the design's "Restart setup {item_id}?" wording.
- The `confirm_url` (line 717): `/project/{project_id}/api/item/{item_id}/restart-setup` — correct POST target.

### 5. Caller compatibility

- `_synthetic_setup_step` signature changed from `(bi: BatchItem | None)` to `(bi: BatchItem | None, step_statuses: list[str] | None = None)`. The new optional parameter defaults to `None` → `restartable=False` for any callers that don't pass it. The single caller at line 432 was updated to pass `step_statuses`.

### 6. Project Conventions

- Router prefix: `APIRouter(prefix="/project/{project_id}/api")` — correct.
- `_emit` helper used for daemon events in both `full_restart_item` and `restart_setup`.
- SQLAlchemy 2.0 style: `db.scalars(select(...))`, `db.scalar(select(...))`.

### 7. Code Quality

- No magic strings — `BatchItemStatus.setup_failed`, `BatchItemStatus.failed`, `StepStatus.pending`, `StepStatus.in_progress`, `BatchStatus.completed_with_errors`.
- SQLAlchemy 2.0 style throughout.
- Error messages don't leak sensitive data (item IDs are operator-scoped, not secrets).
- Both preconditions have clear, actionable error messages.

## Test Results

```
uv run pytest tests/dashboard/test_restart_setup_backend.py -v --no-cov
  11 passed in 17.97s
uv run pytest tests/unit/ -v --no-cov
  2264 passed, 2 skipped, 5 xfailed, 1 xpassed, 48 warnings in 37.04s
```

All tests pass. The coverage failure is a threshold enforcement artifact (total project coverage 18.62% < 46% threshold) — not related to S01 changes.

## Findings

| Severity | File | Line(s) | Description |
|----------|------|---------|-------------|
| None | — | — | No CRITICAL or HIGH issues found |
| MEDIUM (suggestion) | `dashboard/routers/actions.py` | 1176–1235 | The `restart_setup` endpoint has an identical structure to `full_restart_item`: both call `_get_item` implicitly (via the helper which loads the WorkItem), but `restart_setup` never calls `_get_item` directly — it only queries `BatchItem` directly. This is fine for the happy path but differs from `full_restart_item` which calls `_get_item` for its status precondition. No bug, just a note that the `WorkItem` row is loaded inside `_reset_item_to_approved` for both. |
| LOW | `dashboard/routers/items.py` | 598–603 | The comparison `step_statuses == ["pending"] * len(step_statuses)` creates a temporary list. Could be written as `all(s == "pending" for s in step_statuses)` to avoid allocation, though the current form is clear and correct. Not worth flagging as a fix. |

## Verdict

**PASS** — All checklist items verified. The implementation is correct, tests pass, lint/format/typecheck clean on changed files, and no behavior change in `full_restart_item`. The pre-existing lint/format violations in unrelated fixture files are not caused by S01.

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00029",
  "step_reviewed": "S01",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "findings": [
    {
      "severity": "LOW",
      "file": "dashboard/routers/items.py",
      "lines": "598-603",
      "description": "step_statuses == [\"pending\"] * len(step_statuses) creates a temporary list allocation. Could use all() generator instead, but current form is correct and clear. Not a mandatory fix.",
      "suggested_fix": "all(s == \"pending\" for s in step_statuses)"
    }
  ],
  "tests_passed": true,
  "test_summary": "11 restart_setup tests passed; 2264 unit tests passed (no regressions)",
  "notes": "Pre-existing lint/format violations in ai-dev/active/I-00058/I-00059 e2e fixtures are unrelated to S01 changes. Changed files (actions.py, items.py) pass all quality gates cleanly."
}
```