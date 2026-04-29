# I-00050 S01 Backend Report

## Summary

Fixed `_get_browser_findings` in `orch/daemon/fix_cycle.py` to detect and surface newer daemon-detected failures that post-date the original agent-reported failure stored in `step.report_file` / `step.report_content`.

## Bug Description

The original `_get_browser_findings` always returned the failure report from the first `iw step-fail` call (run 1's agent-reported failure). When subsequent runs failed due to daemon-detected errors (container crashes, env setup failures), those newer failures were invisible to fix-cycle agents because they only wrote to `StepRun.error_message` on the `StepRun` record, not to the step-level `report_file` / `report_content` fields.

## Changes Made

### `orch/daemon/fix_cycle.py` (lines 589–650)

Modified `_get_browser_findings` to:

1. After reading content from `step.report_file` or `step.report_content`, query for the most recent failed `StepRun`
2. Check if that run has `report_file = None` (daemon-detected failure, not agent-reported) AND a non-empty `error_message`
3. If both conditions are true, prepend a `## ⚠️ Most Recent Failure (run N)` section to the returned content
4. The original report is preserved below under `## Original Browser Report (for V table context)`

The function's "last resort" path (step.report_file and step.report_content both None) already returns the latest error and needed no change.

### `tests/unit/test_fix_cycle.py`

Added 10 new tests for `_get_browser_findings`:
- `test_get_browser_findings_prefers_step_report_file` — existing behavior preserved
- `test_get_browser_findings_falls_back_to_step_report_content` — existing behavior preserved
- `test_get_browser_findings_newer_daemon_failure_prepended_from_report_file` — new behavior (RED/GREEN verified)
- `test_get_browser_findings_newer_daemon_failure_prepended_from_report_content` — new behavior (RED/GREEN verified)
- `test_get_browser_findings_no_prepend_when_latest_has_report_file` — original behavior preserved (latest run has its own report_file)
- `test_get_browser_findings_last_resort_error_message` — existing behavior preserved
- `test_get_browser_findings_no_report_available` — existing behavior preserved
- `test_get_browser_findings_truncation_at_8000_chars` — existing behavior preserved

## Test Results

All 26 tests in `tests/unit/test_fix_cycle.py` pass:
- 26 passed, 0 failed

## Quality Gates

- **format**: `ruff format` applied — 2 files reformatted
- **typecheck**: `mypy orch/daemon/fix_cycle.py` — Success: no issues
- **lint**: `ruff check` on changed files — All checks passed

Note: Pre-existing lint warnings in `dashboard/routers/code_qa.py` and typecheck errors in `orch/daemon/container_info.py` are unrelated to this change.

## Scope

Strictly scoped to `_get_browser_findings`. No changes to `_get_review_findings`, `_latest_failure_reason`, `attempt_fix_cycle`, or any other function.