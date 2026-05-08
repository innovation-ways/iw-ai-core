# I-00073 S03 Tests Report

## What was done

Implemented the regression test suite for **I-00073 — iw step-done/step-fail crash with UndefinedColumn when worktree ORM adds columns to step_runs/work_items**.

## Files changed

- `tests/integration/cli/test_step_commands_drift.py` — NEW regression test suite (9 scenarios + 1 reproduction test)

## Test scenarios implemented

| Test name | Command | Drift simulated | Side-effect verified |
|-----------|---------|----------------|---------------------|
| `test_step_done_tolerates_missing_step_runs_column` | `iw step-done` | `step_runs.diff_text` dropped | step.status==completed, latest StepRun.status==completed |
| `test_step_fail_tolerates_missing_step_runs_column` | `iw step-fail` | `step_runs.diff_text` dropped | step.status==failed, error_message contains reason |
| `test_step_restart_tolerates_missing_work_items_column` | `iw step-restart` | `work_items.diff_text` dropped | step.status==pending |
| `test_step_restart_from_tolerates_missing_workflow_steps_column` | `iw step-restart-from` | `workflow_steps.gate` dropped | S01 and S02 both reset to pending |
| `test_step_skip_tolerates_missing_step_runs_column` | `iw step-skip` | `step_runs.diff_text` dropped | step.status==skipped |
| `test_step_kill_tolerates_missing_step_runs_column` | `iw step-kill` | `step_runs.diff_text` dropped | step.status==failed, active run.status==killed |
| `test_step_start_tolerates_missing_work_items_column` | `iw step-start` | `work_items.diff_text` dropped | step.status==in_progress, work_item.status==in_progress |
| `test_item_status_tolerates_missing_work_items_column` | `iw item-status` | `work_items.diff_text` dropped | JSON output has correct project_id, id, steps[] with specific values |
| `test_item_status_tolerates_missing_workflow_steps_column` | `iw item-status` | `workflow_steps.gate` dropped | JSON output has correct step_id and status values |

## Bug reproduction (RED check)

**Confirmed**: Tests FAIL against the unfixed code with `psycopg.errors.UndefinedColumn column step_runs.diff_text does not exist`.

The `_drop_column` helper was discovered to have a critical bug: it called `_restore_column()` immediately after dropping, before the subprocess ran. This caused the drift simulation to be undone before the CLI command was executed — making all tests pass against both fixed and unfixed code (false positive). Fixed by removing the automatic restore; columns are restored at test teardown via a `try/finally` pattern.

After fixing `_drop_column`, the RED check was verified:
- With unfixed code: 9 tests FAIL with `UndefinedColumn`
- Error message confirms: `column step_runs.diff_text does not exist` on `SELECT step_runs.id, step_runs.step_id, ... step_runs.diff_text, step_runs.diff_summary ...`

## Test design notes

- **Subprocess invocation**: All tests invoke `uv run iw ...` as a subprocess (not Click CliRunner or direct function calls) to prove end-to-end drift tolerance.
- **Semantic correctness**: Every test verifies SPECIFIC VALUES (not just exit code 0 or key presence):
  - `_step_status()` / `_latest_step_run_status()` query helpers use `load_only()` to avoid the same drift issue in test code
  - `item-status` tests verify exact `project_id`, `id`, `step_id`, and `status` values
- **Isolation**: Session-scoped pg_container + engine cache ensures all 9 tests share one container; `_bootstrap_orch_db` is idempotent and skips re-bootstrap on subsequent calls.
- **Drift simulation**: `_drop_column(engine, table, column)` runs `ALTER TABLE ... DROP COLUMN IF EXISTS` without immediate restore; column is restored after test completes via session cleanup.

## Preflight results

| Check | Result |
|-------|--------|
| `make format` | ok — 647 files already formatted |
| `make typecheck` | ok — no issues found in 233 source files |
| `make lint` | ok — All checks passed |

## Test results

- **Unit tests**: 2705 passed (existing suite unchanged)
- **Integration tests (drift suite)**: 9 failed (expected — unfixed code)
  - The 9 failures are the bug being pinned, not test regressions
  - With the S01 fix applied (load_only columns in step_commands.py and item_commands.py), these tests would pass

## Important observation

This worktree's `orch/cli/step_commands.py` and `orch/cli/item_commands.py` are in the UNFIXED state (identical to `main`/HEAD — the S01 fix was never applied to this worktree). The `git checkout HEAD~1 -- ...` command found no differences, confirming the S01 changes are NOT in this worktree.

The test suite correctly identifies the bug against the current code. Once S01's fix (adding `_STEP_RUN_CLI_COLUMNS`, `_WORK_ITEM_CLI_COLUMNS`, `_WORKFLOW_STEP_CLI_COLUMNS` tuples and `load_only()` calls) is applied, the 9 drift tests will pass.

## Blockers

- **S01 fix not applied**: The tests pin the bug (RED check passes), but cannot verify GREEN because the S01 backend fix hasn't been applied to this worktree. The actual fix is in the `iw-execute` workflow via the Backend agent.

## Notes

- The original test file (from a prior session) had a `_restore_column()` call inside `_drop_column()` that immediately restored the dropped column before the subprocess ran. This caused the drift simulation to be lost. Fixed by removing the automatic restore from `_drop_column()`.
- `test_item_status` has TWO scenarios (work_items drift vs workflow_steps drift) to separately pin the two query shapes in item_commands.py: the `session.get(WorkItem, ...)` path and the `select(WorkflowStep)` path.
- All tests use `load_only()` in their own DB query helpers to avoid the same drift issue in test verification code.