# I-00045 S01 Frontend Report

## What Was Done

Fixed the OSS status widget (displayed on the project dashboard page) which was showing raw JSON dict inside the status pill instead of a human-readable summary.

### Root Cause

The `scan_summary()` function in `dashboard/services/oss_service.py` returned `scan.summary_json` (a dict like `{"must_pass": 5, "must_fail": 0}`) directly as the `summary` field. The `oss_status_frame.html` template then rendered this dict object inline in the pill, producing raw JSON text like `{"must_pass": 5, "must_fail": 0}` instead of a clean status message.

### Fix

Added a `_format_summary()` helper function in `dashboard/services/oss_service.py` that formats the summary dict into a compact human-readable string (e.g., `"2 MUST failures, 3 SHOULD warnings"`) and modified `scan_summary()` to call it before returning.

## Files Changed

- `dashboard/services/oss_service.py` — Added `_format_summary()` helper; `scan_summary()` now returns a formatted string instead of the raw dict

## Test Results

All OSS-related tests pass:
- `test_oss_dashboard_service.py` — 22 passed
- `test_oss_dashboard_boundary.py` + `test_oss_dashboard_routes.py` — 52 passed
- `test_oss_dashboard_templates_extras.py` — 31 passed
- ruff + mypy — clean

## Issues/Observations

None. The fix is minimal and backward-compatible — the `summary` field was always intended to be a string label for the pill, not a raw dict.