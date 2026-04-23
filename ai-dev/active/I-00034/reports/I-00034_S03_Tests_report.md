# S03 Tests Report — I-00034

## What was done

Written 6 integration tests in `tests/integration/dashboard/test_items_duration.py` covering the full I-00034 duration aggregation bug:

- **Reproduction test** (`test_I00034_step_duration_spans_first_run_to_last_completion`): Seeds a step with 2 `StepRun`s (failed + completed) and 1 `FixCycle`, sets `WorkflowStep.started_at/completed_at` to the last-iteration values (simulating the daemon's post-fix-cycle state). Asserts `duration_secs == 630` (10m30s), `started_at == 12:00:00`, `completed_at == 12:10:30`. RED confirmed: pre-fix code returns 30s. GREEN confirmed: post-fix code returns 630s.
- **Total duration companion** (`test_I00034_total_duration_spans_full_item`): Same fixture, asserts `metrics.total_duration_secs == 630`.
- **Happy-path regression guard** (`test_I00034_happy_path_single_run_duration_unchanged`): Single run, 45s duration — unchanged.
- **In-progress regression** (`test_I00034_in_progress_step_returns_none_duration_and_aggregated_start`): Documents S01's in-progress bug — SQL `MAX()` ignores NULL completed_at, so a step with one completed run and one running run gets duration=0 instead of None. Assertion includes explanatory message.
- **Never-launched regression** (`test_I00034_never_launched_step_duration_is_none`): Pending step with zero runs/cycles — duration is None.
- **N+1 guard** (`test_I00034_get_steps_query_count_is_bounded`): Verified `_get_steps` issues 17 queries for N=10 steps (7 + N, not 7 + 2N). Uses `db_session.get_bind()` event listener.

## Files Changed

- `tests/integration/dashboard/test_items_duration.py` — new file (6 tests)

## Test Results

| Test | Status |
|------|--------|
| `test_I00034_step_duration_spans_first_run_to_last_completion` | PASS (post-fix) / FAIL pre-fix (30s ≠ 630s) |
| `test_I00034_total_duration_spans_full_item` | PASS |
| `test_I00034_happy_path_single_run_duration_unchanged` | PASS |
| `test_I00034_in_progress_step_returns_none_duration_and_aggregated_start` | FAIL (documents S01 bug) |
| `test_I00034_never_launched_step_duration_is_none` | PASS |
| `test_I00034_get_steps_query_count_is_bounded` | PASS (17 queries ≤ 17 max) |

Pre-existing unit test failures (12 failures in `test_daemon_core.py`, `test_merge_queue_cli.py`, etc.) are pre-existing identity/mock fixture issues unrelated to this change.

## RED/GREEN Verification

- Pre-fix (stashed S01): `assert 30.0 == pytest.approx(630)` — **FAILED** as expected
- Post-fix (S01 restored): all 5 passing tests **PASS**

## Query Count

Observed 17 queries for N=10 steps: 1 (projects) + 1 (work_items) + 1 (batch_items) + 1 (workflow_steps) + 1 (fix_cycle_counts) + 2 (aggregation) + 10 (step_runs per step) = 17 total.

Max allowed: 17 — test passes.

## Issues / Observations

1. **S01 in-progress bug**: `_aggregate_step_spans` uses SQL `MAX(completed_at)` which ignores NULLs. A step with one completed run and one running run (completed_at=NULL) returns MAX=T0, not None. The duration becomes 0.0 instead of None, so the template would not render "—". The test documents this gap. Fixing it requires detecting NULL in the aggregation and returning None for the completed_at tuple element.

2. **No unit test for aggregation helper written**: S01 extracted the helper as a private function inside `items.py` (not a standalone module). The integration tests cover the logic directly. No separate unit test file was created.

## Notes

- `ruff check` passes with `# noqa: N802` annotations on test method names — the naming convention test_I00034_... is intentional per the issue spec.
- `_make_work_item` helper was added to reduce repetition across tests.
