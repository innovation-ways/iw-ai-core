# I-00073 S04 CodeReview Report

## What was reviewed

Regression test suite in `tests/integration/cli/test_step_commands_drift.py` (9 scenarios + reproduction test) for I-00073 — `iw step-done/step-fail` crash with `UndefinedColumn` when worktree ORM adds columns to `step_runs`/`work_items`.

## Files changed

| File | Type | Purpose |
|------|------|---------|
| `tests/integration/cli/test_step_commands_drift.py` | NEW | 9 regression scenarios + reproduction test |
| `docs/IW_AI_Core_Agent_Constraints.md` | MODIFIED | R2b subsection added (CLI resilience to schema drift) |

## Pre-flight gates

| Check | Result |
|-------|--------|
| `make lint` | PASS — 0 violations |
| `make format` | PASS — 647 files already formatted |

## RED Check (manual verification)

Confirmed by running the suite against **unfixed code** (S01 fix not applied to this worktree):

```
FAILED tests/integration/cli/test_step_commands_drift.py::test_step_done_tolerates_missing_step_runs_column
  → AssertionError: step-done exited 1
  → Error: Database error: (psycopg.errors.UndefinedColumn) column step_runs.diff_text does not exist
  → [SQL: SELECT step_runs.id, step_runs.step_id, ..., step_runs.diff_text, step_runs.diff_summary, ...]
```

All 9 tests fail identically with `UndefinedColumn`. This is the **correct RED state** — the suite successfully pins the bug against unfixed code. Once S01's `load_only()` patches are applied, these tests will pass.

## Review Checklist

### 1. Coverage of Patched Callsites ✅

| Test | Command | Patched Callsite | Drift Column |
|------|---------|-----------------|-------------|
| `test_step_done_tolerates_missing_step_runs_column` | `iw step-done` | step_commands.py:374-382 | `step_runs.diff_text` |
| `test_step_fail_tolerates_missing_step_runs_column` | `iw step-fail` | step_commands.py:531-538 | `step_runs.diff_text` |
| `test_step_restart_tolerates_missing_work_items_column` | `iw step-restart` | step_commands.py:659-663 | `work_items.diff_text` |
| `test_step_restart_from_tolerates_missing_workflow_steps_column` | `iw step-restart-from` | step_commands.py:622, 730 | `workflow_steps.gate` |
| `test_step_skip_tolerates_missing_step_runs_column` | `iw step-skip` | step_commands.py:825-829 | `step_runs.diff_text` |
| `test_step_kill_tolerates_missing_step_runs_column` | `iw step-kill` | step_commands.py:890-897 | `step_runs.diff_text` |
| `test_step_start_tolerates_missing_work_items_column` | `iw step-start` | step_commands.py:247-251 | `work_items.diff_text` |
| `test_item_status_tolerates_missing_work_items_column` | `iw item-status` | item_commands.py:718 (session.get) | `work_items.diff_text` |
| `test_item_status_tolerates_missing_workflow_steps_column` | `iw item-status` | item_commands.py:724 (select) | `workflow_steps.gate` |

Every command from S01's root-cause table is covered. `item-status` has **two separate scenarios** — one for each query shape (Shape A: `session.get(WorkItem, ...)` at item_commands.py:718; Shape B: `select(WorkflowStep)` at item_commands.py:724).

### 2. Semantic Correctness of Assertions ✅

Every test asserts both (a) exit code and (b) specific DB state:

- `test_step_done_*`: `step.status == "completed"` AND `_latest_step_run_status() == "completed"`
- `test_step_fail_*`: `step.status == "failed"` AND error_message contains reason
- `test_step_restart_*`: `step.status == "pending"`
- `test_step_skip_*`: `step.status == "skipped"`
- `test_step_kill_*`: `step.status == "failed"` AND `run.status == RunStatus.killed`
- `test_step_start_*`: `step.status == "in_progress"` AND `work_item.status == "in_progress"`
- `test_item_status_*_work_items`: specific JSON `project_id`, `id`, `steps[0].step_id`, `steps[0].status` values
- `test_item_status_*_workflow_steps`: same JSON value verification

### 3. Drift Simulation Is Real ✅

Confirmed:
- Dropped columns (`diff_text`, `diff_summary`, `merge_commit_sha`, `gate`) are **declared on the in-process ORM** (`models.py` lines 522, 527, 535, 618)
- `ALTER TABLE ... DROP COLUMN IF EXISTS` is executed against the testcontainer DB (not port 5433)
- Dropped columns are restored after test via `_restore_column()` in a `try/finally` pattern

### 4. Subprocess Invocation ✅

All tests invoke `uv run iw ...` via `_run_iw()` subprocess runner — never Click `CliRunner` or direct function calls. This proves end-to-end drift tolerance.

### 5. Testcontainer Conventions ✅

- URL replacement: `postgresql+psycopg2://` → `postgresql+psycopg://` ✅
- FTS DDL: `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` run after `create_all()` ✅
- No DB mocking ✅
- No `importlib.reload(orch.config)` ✅
- No port 5433 connections ✅

### 6. Test Isolation ✅

- Session-scoped `pg_container` with engine cache reused across all 9 tests
- `_bootstrap_orch_db` is idempotent (guards via `_BOOTSTRAPPED_ENGINES` set)
- Column restoration via `_restore_column` after each test ensures no leakage

### 7. Manual RED-Check Plausibility ✅

S03 report notes: *"With unfixed code: 9 tests FAIL with `UndefinedColumn`. Error message confirms: `column step_runs.diff_text does not exist` on `SELECT step_runs.id, step_runs.step_id, ... step_runs.diff_text, step_runs.diff_summary ...`*"

Verified first-hand — tests fail with `UndefinedColumn` against unfixed code. The narrative is accurate and specific.

## Test Results

| Suite | Result |
|-------|--------|
| `make test-unit` | 2707 passed ✅ |
| `make lint` | All checks passed ✅ |
| `make format` | 647 files already formatted ✅ |
| Drift tests (9) against unfixed code | 9 FAILED with `UndefinedColumn` ✅ (correct RED state) |

## Notes

- **S01 fix NOT applied to this worktree**: All 9 drift tests fail as expected. This confirms the tests successfully pin the bug. Once the `load_only()` patches from S01 are applied (via the `iw-execute` workflow), these tests will pass.
- **R2b subsection in constraints doc**: S01 added the `docs/IW_AI_Core_Agent_Constraints.md` R2b policy note, which correctly documents the rule so future contributors understand why column-projected selects are required.
- **No migration file created**: Confirmed — the fix is purely in the CLI layer (no migrations needed or created).
