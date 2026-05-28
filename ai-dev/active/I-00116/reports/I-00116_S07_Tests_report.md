# I-00116 S07 — Tests Report

**Work Item**: I-00116
**Step**: S07
**Agent**: Tests
**Status**: Completed (manual fix cycle)

## Summary

Three test files were created by the original S07 agent run. The targeted pytest command exposed one failing test, which was diagnosed and fixed in this step before marking S07 done.

## Test Files Created

### (a) `tests/unit/daemon/test_step_monitor_i00116_review_recovery.py`

Four unit tests for `_try_recover_completed_review_step` in `step_monitor.py`:

| Test | Purpose |
|------|---------|
| `test_i00116_review_step_with_report_on_disk_is_recovered_not_crashed` | RED repro: report on disk → recovery path fires, `_handle_crashed` NOT called |
| `test_i00116_review_step_without_report_still_marked_crashed` | Negative path: no report → `_handle_crashed` still fires |
| `test_i00116_non_review_step_type_is_unchanged` | Non-review steps follow original crash path regardless of report |
| `test_i00116_recovered_run_emits_daemon_event_with_verdict` | DaemonEvent emitted with correct `verdict` and `step_id` in metadata |

### (b) `tests/integration/test_fix_cycle_review_relaunch_cap.py`

Two integration tests using a real testcontainer-backed `db_session`:

| Test | Purpose |
|------|---------|
| `test_i00116_under_cap_review_relaunches_are_unaffected` | Under-cap path: work item proceeds normally |
| `test_i00116_at_cap_review_relaunch_transitions_item_failed_and_emits_event` | At-cap path: item transitions to `failed` with exactly one `review_relaunch_cap_exceeded` DaemonEvent |

### (c) `tests/unit/test_review_prompt_scope.py`

Four unit tests verifying master prompt file content:

| Test | Purpose |
|------|---------|
| `test_review_prompt_references_allowed_paths` | `agents/code-review-impl.md` references `allowed_paths` |
| `test_iw_workflow_skill_documents_diff_scoping_convention` | `skills/iw-workflow/SKILL.md` documents the scoping convention |
| `test_review_prompt_does_not_recommend_unbounded_git_diff_head` | Neither master prompt contains unbounded `git diff HEAD` guidance |
| `test_code_review_final_prompt_also_references_allowed_paths` | `commands/code-review-impl.md` also references `allowed_paths` |

## Bug Found and Fixed During S07 Validation

### Root Cause

`_try_recover_completed_review_step` in `orch/daemon/step_monitor.py` (line 286) used `run.step_id` (an **integer FK** to `workflow_steps.id`) in the glob pattern, but report files are named with the **string step identifier** (e.g. `S02`). The glob never matched any report, so the recovery path was never triggered and `_handle_crashed` was always called instead.

### Production Fix (`orch/daemon/step_monitor.py`)

Before the glob, look up `WorkflowStep` by the integer FK to obtain the string step identifier:

```python
ws = db.get(WorkflowStep, run.step_id)
if ws is None:
    return False
step_str = ws.step_id  # e.g. "S02"
```

The glob pattern and DaemonEvent metadata now use `step_str` instead of `run.step_id`.

### Test Fix (`test_step_monitor_i00116_review_recovery.py` test 4)

Test 4 uses `mock_db` to intercept `db.get()`. After the production fix, `ws.step_id` is accessed on the mock object. Added `mock_step.step_id = "S02"` to the mock setup so it returns the correct string.

## Test Results

```
uv run pytest tests/unit/daemon/test_step_monitor_i00116_review_recovery.py \
              tests/integration/test_fix_cycle_review_relaunch_cap.py \
              tests/unit/test_review_prompt_scope.py -v
```

```
PASSED tests/unit/daemon/test_step_monitor_i00116_review_recovery.py::test_i00116_non_review_step_type_is_unchanged
PASSED tests/unit/daemon/test_step_monitor_i00116_review_recovery.py::test_i00116_recovered_run_emits_daemon_event_with_verdict
PASSED tests/unit/daemon/test_step_monitor_i00116_review_recovery.py::test_i00116_review_step_with_report_on_disk_is_recovered_not_crashed
PASSED tests/unit/daemon/test_step_monitor_i00116_review_recovery.py::test_i00116_review_step_without_report_still_marked_crashed
PASSED tests/integration/test_fix_cycle_review_relaunch_cap.py::test_i00116_under_cap_review_relaunches_are_unaffected
PASSED tests/integration/test_fix_cycle_review_relaunch_cap.py::test_i00116_at_cap_review_relaunch_transitions_item_failed_and_emits_event
PASSED tests/unit/test_review_prompt_scope.py::test_review_prompt_references_allowed_paths
PASSED tests/unit/test_review_prompt_scope.py::test_iw_workflow_skill_documents_diff_scoping_convention
PASSED tests/unit/test_review_prompt_scope.py::test_review_prompt_does_not_recommend_unbounded_git_diff_head
PASSED tests/unit/test_review_prompt_scope.py::test_code_review_final_prompt_also_references_allowed_paths

10 passed in 10.01s
```

## Files Modified

| File | Change |
|------|--------|
| `tests/unit/daemon/test_step_monitor_i00116_review_recovery.py` | Created (4 tests) + fixed test 4 mock setup |
| `tests/integration/test_fix_cycle_review_relaunch_cap.py` | Created (2 tests) |
| `tests/unit/test_review_prompt_scope.py` | Created (4 tests) |
| `orch/daemon/step_monitor.py` | Fixed glob to use string step identifier via `db.get(WorkflowStep, run.step_id).step_id` |
