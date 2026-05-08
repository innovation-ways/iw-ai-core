# I-00073 S02 Code Review Report — Backend (S01)

## What was reviewed

S01 implemented column-projected SELECTs for all agent-facing CLI reads of `StepRun`, `WorkItem`, and `WorkflowStep` to prevent `UndefinedColumn` crashes when a worktree ORM has un-applied migration columns that the live orchestration DB does not yet have.

## Files reviewed

| File | Change |
|------|--------|
| `orch/cli/step_commands.py` | Added `_STEP_RUN_CLI_COLUMNS`, `_WORK_ITEM_CLI_COLUMNS`, `_WORKFLOW_STEP_CLI_COLUMNS` pinned tuples; `load_only()` on all 10 agent-facing callsites; module docstring with R2b resilience explanation |
| `orch/cli/item_commands.py` | Added `_WORK_ITEM_CLI_COLUMNS`, `_WORKFLOW_STEP_CLI_COLUMNS` pinned tuples; `load_only()` on all 7 agent-facing callsites; module docstring with R2b resilience explanation |
| `docs/IW_AI_Core_Agent_Constraints.md` | Added "CLI resilience to in-flight schema drift" subsection (R2b) documenting the rule, both query shapes, and pointer to I-00073 |
| `tests/integration/cli/test_step_commands_drift.py` | New regression suite — 9 tests covering every patched CLI command against a column-drifted testcontainer DB |

## Architecture compliance (AC3)

- ✅ Fix lives entirely in `orch/cli/step_commands.py`, `orch/cli/item_commands.py`, and `docs/IW_AI_Core_Agent_Constraints.md`
- ✅ No file under `orch/daemon/` modified
- ✅ No migration files added or modified
- ✅ No `try/except UndefinedColumn` fallback present

## Callsite coverage

All callsites from the Root Cause Analysis table are confirmed patched:

### Shape B (`session.get(WorkItem, ...)`) — `item_commands.py`
All 6 RCA-listed shape-B callsites (lines 249, 416, 542, 605, 718, 854) have been rewritten as:
```python
session.execute(
    select(WorkItem)
    .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
    .where(WorkItem.project_id == project_id, WorkItem.id == item_id)
).scalar_one_or_none()
```
Grep confirms zero `session.get(WorkItem, ...)` remain in `orch/cli/item_commands.py`. The `session.get(WorkItem, ...)` in `batch_commands.py` and `doc_commands.py` are operator-facing and outside RCA scope per AC3.

### Shape A (`select(Model).where(...)`) — `step_commands.py`
All 10 RCA-listed callsites confirmed with `load_only()`:
- Line 141 `_get_workflow_step` helper (cascades to all step-lifecycle commands) ✅
- Lines 371–378 `step-done` StepRun lookup ✅
- Lines 531–538 `step-fail` StepRun lookup ✅
- Lines 247–251 `step-start` WorkItem lookup ✅
- Lines 659–663 `step-restart` WorkItem lookup ✅
- Lines 757–761 `step-restart-from` WorkItem lookup ✅
- Lines 825–829 `step-skip` StepRun lookup ✅
- Lines 890–897 `step-kill` StepRun lookup ✅
- Line 622 `step-restart-from` WorkflowStep advanced-step scan ✅
- Line 730 `step-restart-from` WorkflowStep all-steps scan ✅

### Shape A — `item_commands.py`
- Line 724 (`item-status` WorkflowStep select) ✅

## Pinned column set quality

- ✅ Defined as module-level tuples (`_STEP_RUN_CLI_COLUMNS`, `_WORK_ITEM_CLI_COLUMNS`, `_WORKFLOW_STEP_CLI_COLUMNS`)
- ✅ Named with descriptive purpose (`_CLI_COLUMNS` suffix)
- ✅ Uses `Mapped` attribute references (not string column names) — fails at import time if renamed
- ✅ NOTE comments document intentionally excluded columns (e.g. `diff_text`, `diff_summary`, `gate`, `merge_commit_sha`) and explain why they are safe to omit (CLI writes via direct assignment after load, which is a no-op against a drifted DB)
- ✅ `step-restart`'s pre-existing `select(StepRun.run_number)` (line 763) was left unchanged — it was already column-projected and not in scope for the fix

## Documentation

- ✅ `orch/cli/step_commands.py` module docstring explains the R2/R2b resilience contract
- ✅ `orch/cli/item_commands.py` module docstring explains the rule
- ✅ `docs/IW_AI_Core_Agent_Constraints.md` has new "CLI resilience to in-flight schema drift" subsection referencing I-00073

## Pre-flight quality gates

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ 647 files already formatted |

## Test results

### Unit tests (`make test-unit`)
```
= 2707 passed, 4 skipped, 5 xfailed, 1 xpassed, 47 warnings in 63.44s =
```
2 pre-existing failing tests (`test_safe_migrate.py::test_apply_refuses_in_agent_context`, `test_rollback_refuses_in_agent_context`) are unrelated to I-00073 — verified by stashing changes and confirming they fail identically without this work.

### Regression tests (`test_step_commands_drift.py`, --no-cov)
```
tests/integration/cli/test_step_commands_drift.py::test_step_done_tolerates_missing_step_runs_column PASSED
tests/integration/cli/test_step_commands_drift.py::test_step_fail_tolerates_missing_step_runs_column PASSED
tests/integration/cli/test_step_commands_drift.py::test_step_restart_tolerates_missing_work_items_column PASSED
tests/integration/cli/test_step_commands_drift.py::test_step_restart_from_tolerates_missing_workflow_steps_column PASSED
tests/integration/cli/test_step_commands_drift.py::test_step_skip_tolerates_missing_step_runs_column PASSED
tests/integration/cli/test_step_commands_drift.py::test_step_kill_tolerates_missing_step_runs_column PASSED
tests/integration/cli/test_step_commands_drift.py::test_step_start_tolerates_missing_work_items_column PASSED
tests/integration/cli/test_step_commands_drift.py::test_item_status_tolerates_missing_work_items_column PASSED
tests/integration/cli/test_step_commands_drift.py::test_item_status_tolerates_missing_workflow_steps_column PASSED
========================= 9 passed, 1 warning in 8.07s =========================
```
All 9 scenarios pass — one per patched CLI command (step-done, step-fail, step-restart, step-restart-from, step-skip, step-kill, step-start) plus two for item-status (drifting work_items only, drifting workflow_steps only). Both Shape A and Shape B query shapes are exercised.

**Note on coverage failure in partial runs**: Running a single test file with `--no-cov` reports low aggregate coverage (9% or below), which falls below the 46% fail-under threshold. This is expected — the full suite (`make test-integration`) is needed to accumulate coverage across all modules. The drift tests themselves pass; the coverage failure is a pre-existing configuration artifact of running isolated test files against the full coverage baseline.

## Findings

Zero CRITICAL, HIGH, MEDIUM_FIXABLE, or convention violations found.
