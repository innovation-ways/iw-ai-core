# I-00090 S03 — Tests Implementation Report

## What Was Done

Created `tests/dashboard/test_running_router_active_filter.py` with 16 tests covering the active-item filter on `_query_failed_steps()` and `_query_recent_completions()` in `dashboard/routers/running.py`.

## Files Changed

- `tests/dashboard/test_running_router_active_filter.py` — new file (16 test cases)

## Test Coverage

### Helper-level tests for `_query_failed_steps()` (8 tests)

| # | Test | What it verifies |
|---|------|-----------------|
| 1 | `test_query_failed_steps_includes_in_progress_item` | `status=in_progress`, `archived_at=None` → row appears |
| 2 | `test_query_failed_steps_excludes_completed_item` | `status=completed` → row absent (**reproduction test**) |
| 3 | `test_query_failed_steps_excludes_cancelled_item` | `status=cancelled` → row absent |
| 4 | `test_query_failed_steps_excludes_archived_item` | `archived_at=now()` (any status) → row absent |
| 5 | `test_query_failed_steps_includes_failed_item` | `status=failed`, `archived_at=None` → row appears |
| 6 | `test_query_failed_steps_includes_paused_item` | `status=paused`, `archived_at=None` → row appears |
| 7 | `test_query_failed_steps_includes_needs_fix_status` | `step.status=needs_fix` on `in_progress` item → row appears |
| 8 | `test_query_failed_steps_respects_project_filter` | project-scoped query returns only that project's rows |

### Helper-level tests for `_query_recent_completions()` (6 tests)

| # | Test | What it verifies |
|---|------|-----------------|
| 9 | `test_query_recent_completions_includes_in_progress_item` | `status=in_progress` → row appears |
| 10 | `test_query_recent_completions_excludes_completed_item` | `status=completed` → row absent (**reproduction test for AC3**) |
| 11 | `test_query_recent_completions_excludes_cancelled_item` | `status=cancelled` → row absent |
| 12 | `test_query_recent_completions_excludes_archived_item` | `archived_at=now()` → row absent |
| 13 | `test_query_recent_completions_includes_failed_item` | `status=failed` → row appears |
| 14 | `test_query_recent_completions_includes_paused_item` | `status=paused` → row appears |

### Route-level smoke tests (2 tests)

| # | Test | What it verifies |
|---|------|-----------------|
| 15 | `test_system_running_route_renders_active_item_only` | `GET /system/running` — active item appears, completed item absent |
| 16 | `test_project_running_route_renders_active_item_only` | `GET /project/{id}/running` — active item appears, completed item absent, other project absent |

## TDD RED Evidence

**Test:** `test_query_failed_steps_excludes_completed_item`

**Pre-S01 reasoning:** `_query_failed_steps()` selected all `WorkflowStep` rows with `status IN (failed, needs_fix)` without any filter on the parent `WorkItem`. The assertion `assert "CR-DEAD" not in [r.item_id for r in rows]` would fail against pre-S01 code because CR-DEAD's failed step would be returned in the unfiltered result set, causing `item_ids = [r.item_id for r in rows]` to contain `"CR-DEAD"`.

After S01 applied the `.where(WorkItem.archived_at.is_(None))` and `.where(WorkItem.status.notin_([WorkItemStatus.completed, WorkItemStatus.cancelled]))` predicates, the test passes.

## Test Results

```
tests/dashboard/test_running_router_active_filter.py: 16 passed, 0 failed
```

## Preflight Results

| Check | Result |
|-------|--------|
| `make format` | ok — 745 files formatted |
| `make typecheck` (mypy) | ok — no errors |
| `make lint` (ruff) | ok — All checks passed |

## Design Decisions

1. **`StepType` required field:** `WorkflowStep.step_type` is NOT NULL, so `_make_step()` defaults to `StepType.implementation` to avoid breaking the seed helper.

2. **Unused step-variable cleanup:** `_make_step()` return values were assigned to named variables (`step_alive`, `step_dead`, etc.) in early drafts but never used — ruff F841 fired. All such assignments were converted to bare calls (removing the `step_` prefix) since the step PK is only needed for `_make_run()` in the `StepRun`-creation tests.

3. **Generator return type:** `client` fixture's return type changed from `TestClient` to `Generator[TestClient, None, None]` — mypy misc rule requires this for generator fixtures.

4. **f-string cleanup:** Four assertion messages in the project-route test used f-strings without placeholders — converted to plain strings.

5. **Test isolation:** All 16 tests use independent `db_session` clones via pgtestdbpy (per-test template clone). No test depends on another's state.

## Blockers

None.