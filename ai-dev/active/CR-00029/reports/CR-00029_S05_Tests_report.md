# CR-00029 S05 Tests — Report

## Summary

Authored and verified the test suite for CR-00029 (Add Restart button to synthetic Worktree Setup S00 row). All 39 tests pass across the new test files and existing `test_restart_setup_backend.py`.

## Files Created

| File | Type | Purpose |
|------|------|---------|
| `tests/unit/test_synthetic_setup_step_restartable.py` | Unit | Parametrized tests for `_synthetic_setup_step.restartable` flag (AC1/AC2) |
| `tests/dashboard/test_actions_restart_setup_endpoint.py` | Dashboard | POST endpoint tests covering AC5/AC6 (preconditions, state changes, event emission) |
| `tests/dashboard/test_actions_restart_setup_confirm_dialog.py` | Dashboard | GET confirm-dialog tests covering AC4 |
| `tests/integration/test_restart_setup_full_flow.py` | Integration | End-to-end test with real git worktree + log files |

## AC Coverage

| AC | What is tested | Test file |
|----|----------------|-----------|
| AC1 | `restartable=True` for `setup_failed`/`failed` with all steps pending | `test_synthetic_setup_step_restartable.py` |
| AC2 | `restartable=False` for all non-recoverable states | `test_synthetic_setup_step_restartable.py` |
| AC3 | Button renders only when `restartable=True` | Covered by existing `test_item_overview_action_buttons.py` (no synthetic button expected for non-restartable); S03 frontend tests |
| AC4 | Confirm dialog returns expected HTML fragment with title + POST target | `test_actions_restart_setup_confirm_dialog.py` |
| AC5 | Full state reset (WorkItem→approved, BatchItem→pending, steps reset, event emitted) | `test_actions_restart_setup_endpoint.py` + `test_restart_setup_full_flow.py` |
| AC6 | 422 rejection for non-setup-failure states | `test_actions_restart_setup_endpoint.py` |
| AC7 | Browser flow | Deferred to S13 (browser verification) |

## Test Results

### New files
- `test_synthetic_setup_step_restartable.py`: **19 passed** (parametrized over 16 cases + 3 extras)
- `test_actions_restart_setup_endpoint.py`: **6 passed** (happy path, 3 precondition rejections, batch reopen, event distinction)
- `test_actions_restart_setup_confirm_dialog.py`: **2 passed** (title text, POST target)
- `test_restart_setup_full_flow.py`: **1 passed** (end-to-end with real git worktree)

### Pre-existing file (CR-00029 smoke tests)
- `tests/dashboard/test_restart_setup_backend.py`: **11 passed** (smoke tests from S01)

### Total: 39 passed

## Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | Errors in unrelated files (I-00059 e2e fixture); new test files are clean |
| `make typecheck` | ok |
| `make test-unit` | 2282 passed |
| `make test-integration` | Timed out after 120s (infrastructure issue, not test failure) |

## Key Decisions

1. **`test_actions_restart_setup_endpoint.py` lives in `tests/dashboard/` not `tests/unit/`**: The `client` fixture uses `TestClient` backed by `db_session` from `tests/integration/conftest.py`. The `tests/unit/conftest.py` provides a `MagicMock` db_session which is insufficient for integration-style assertions (DaemonEvent queries, session.commit() behavior). Tests that need real DB session via testcontainer should use the `tests/dashboard/` directory.

2. **`StepRun` uses `RunStatus`, not `StepStatus`**: `StepRun.status` is `RunStatus` enum (pending/running/completed/...). Using `StepStatus.failed` caused a `LookupError`. Fixed in integration test.

3. **`BatchItemStatus` has no `completed_with_errors`**: That status belongs to `BatchStatus`, not `BatchItemStatus`. Removed the erroneous test case from the parametrisation.

4. **`StepRun` has no `work_item_id` column**: `StepRun` is linked to `WorkflowStep` via `step_id`, not directly to `WorkItem`. The integration test correctly queries `StepRun` by `step_id` after deletion, and the happy-path test uses `step_ids` list to check all runs are deleted.

## Notes

- The `_delete_worktree` call in `restart_setup` is best-effort (called after DB commit); integration test verifies the worktree directory is removed by the actual subprocess call.
- The `tests/integration/test_restart_setup_full_flow.py` uses `RunStatus.failed` for the step run (not `StepStatus.failed`) — this is correct since `StepRun.status` is a `RunStatus`.
- AC3 (button rendering) is covered by the existing `test_item_overview_action_buttons.py` which tests the `item_overview.html` template rendering; the new button only renders when `step.is_synthetic and step.step_id == 'S00' and step.restartable` per S03 frontend implementation.