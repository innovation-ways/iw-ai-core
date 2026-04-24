# I-00037 S05 Tests Report

## What was done

Added a comprehensive test suite for the `compute_batch_step_progress` helper and the two router
functions (`_active_batches`, `_all_batches`) that wire it into the dashboard views.

## Files changed

- `tests/dashboard/conftest.py` — new entry point that re-exports `db_session` from
  `tests/integration/conftest.py` so dashboard tests can use the testcontainer-backed fixture.
- `tests/dashboard/test_batches_progress_parity.py` — new 16-test module with 4 test classes.

## Test structure

### `TestI00037ProgressParity` (1 test)
- `test_I00037_dashboard_home_and_batches_view_agree_on_progress` — reproduction + parity.
  Seeds 1 item with 10 steps (3 completed, 7 pending) and a single `executing` batch.
  Asserts both routers return `progress_pct == 30` and that `total_items == 1` (not 10).
  **Would fail against pre-S03 code** which returned `progress_pct == 0` (item-level).

### `TestComputeBatchStepProgress` (11 tests)
Direct unit tests of the helper for edge cases:

| Test | Scenario | Expected |
|------|----------|----------|
| `test_helper_empty_batch_ids_returns_empty_dict` | `[]` | `{}` |
| `test_helper_single_batch_3_of_10_done` | 1 item, 10 steps, 3 done | 30 |
| `test_helper_all_steps_done_is_100` | 5 steps, all done | 100 |
| `test_helper_zero_steps_is_0_not_crash` | 0 WorkflowStep rows | 0 |
| `test_helper_skipped_counts_as_done` | 2 completed + 2 skipped + 6 pending | 40 |
| `test_helper_failed_does_not_count` | 3 completed + 2 failed + 5 pending | 30 (NOT 50) |
| `test_helper_needs_fix_does_not_count` | 3 completed + 1 needs_fix + 6 pending | 30 (NOT 40) |
| `test_helper_in_progress_does_not_count` | 3 completed + 1 in_progress + 6 pending | 30 |
| `test_helper_multi_batch_bulk` | A:1/10, B:5/10, C:0 steps, D:10/10 | 10, 50, 0, 100 |
| `test_helper_missing_batch_id_defaults_to_0` | [existing, "DOESNOTEXIST"] | 100, 0 |
| `test_helper_scopes_by_project_id` | Two projects, same work_item_id | A→30, B→80 |

### `TestRouterProgressMatch` (2 tests)
- `test_active_batches_and_all_batches_match_on_partial` — same seeded state,
  both routers return identical `progress_pct` for the same batch.
- `test_active_batches_total_items_is_item_count_not_step_count` — asserts
  `total_items == 1` (batch item count) even though 10 workflow steps exist.

### `TestHttpProgressSmoke` (2 tests)
- `test_project_dashboard_html_contains_30_percent` — GET `/project/{id}/`,
  rendered HTML must contain "30%" somewhere.
- `test_batches_list_html_contains_30_percent` — GET `/project/{id}/batches`,
  rendered HTML must contain "30%" in the Progress column.

## Test results

```
tests/dashboard/test_batches_progress_parity.py: 16 passed, 1 warning
make test-unit:  1395 passed, 19 warnings
make test-integration: 974 passed, 10 skipped, 36 warnings
```

## Notes

- Enum corrections applied during test writing: `WorkItemPhase.execution` → `WorkItemPhase.active`,
  `WorkItemStatus.executing` → `WorkItemStatus.in_progress`, `WorkItemType.feature` → `WorkItemType.Feature`,
  `StepType.verify` → `StepType.implementation`, `BatchItemStatus.in_progress` → `BatchItemStatus.executing`.
- WorkItem constructor uses `type=` (not `item_type=`) and requires `config`, `depends_on`, `blocks`.
- `test_helper_multi_batch_bulk` required pre-seeding all 4 WorkItems before creating BatchItems
  (FK constraint on `batch_items.project_id, batch_items.work_item_id`).
- Parity assertion `dash.progress_pct == full.progress_pct` is the central lock:
  both routers MUST agree, regardless of what value they return.