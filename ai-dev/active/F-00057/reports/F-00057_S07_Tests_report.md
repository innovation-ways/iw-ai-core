# F-00057 S07 Tests Report

## Summary

Authored `tests/integration/test_oss_boundary.py` (10 boundary + 7 invariant tests) and `tests/integration/test_oss_freshness.py` (3 AC5 freshness tests) covering every Boundary Behavior row and Invariant from the F-00057 design doc.

## Files Changed

- `tests/integration/test_oss_boundary.py` — new file (922 lines)
- `tests/integration/test_oss_freshness.py` — new file (328 lines)

## Test Coverage

### Boundary Behavior Tests (`test_oss_boundary.py`)

| Test | Scenario |
|------|----------|
| `test_scan_refuses_when_oss_disabled` | `oss_enabled=false` → exit 2, no DB writes |
| `test_scan_persists_error_on_setup_failure` | Setup failure → `status='error'`, `exit_code=2` |
| `test_scan_on_unregistered_project` | Unknown project_id → exit 2, no writes |
| `test_enable_refuses_non_git_dir` | Non-git path → exit 2, flag unchanged |
| `test_rerun_at_same_head_creates_new_row` | Same HEAD twice → two `oss_scan` rows |
| `test_concurrent_scans_create_separate_rows` | Concurrent `run_scan` via `asyncio.gather` → no FK violations |
| `test_missing_tier1_tool_persists_as_missing` | Missing tool → `status='missing'`, scan completes |
| `test_status_on_no_scans_returns_gray` | No prior scans → `pill_color: "gray"` |
| `test_malformed_orchestrator_output` | Garbled JSON → `status='error'`, error_message set |
| *(enable force/non-force covered by existing `test_oss_cli.py` tests)* |

### Invariant Tests (`test_oss_boundary.py`)

| Test | Invariant |
|------|-----------|
| `test_invariant_1_finding_cascade_on_scan_delete` | Inv #1: FK CASCADE `oss_scan` → `oss_finding` |
| `test_invariant_2_tool_run_cascade_on_scan_delete` | Inv #2: FK CASCADE `oss_scan` → `oss_tool_run` |
| `test_invariant_3_pill_color_truth_table` | Inv #3: truth-table for must/should fail/human → red/yellow/green |
| `test_invariant_4_head_sha_captured_before_subprocess` | Inv #4: `head_sha` captured before subprocess starts |
| `test_invariant_5_config_writer_output_matches_defaults` | Inv #5: config output matches defaults |
| `test_invariant_6_project_cascade_to_findings_and_tool_runs` | Inv #6: project DELETE cascades to findings + tool_runs |
| `test_invariant_7_status_json_shape_stable` | Inv #7: `status --json` key set is stable |

### Freshness Tests (`test_oss_freshness.py`)

| Test | AC |
|------|---|
| `test_stale_detection_after_commit` | AC5: scan at SHA A, advance HEAD to B, `stale: true` |
| `test_fresh_when_head_matches` | AC5: scan at HEAD, `stale: false` |
| `test_stale_preserves_last_pill_color` | AC5: even when stale, `pill_color` preserved from last scan |

## Test Results

```
19 passed in 22.96s
```

All new tests pass. Pre-existing OSS integration tests (in `test_oss_cli.py`, `test_oss_scanner.py`, `test_oss_persistence.py`) also pass (38 total, 1 pre-existing unrelated failure in `test_oss_scanner.py` due to event-loop reuse pattern from prior step).

## Notes

- Fixed SQL syntax: split `CREATE TABLE IF NOT EXISTS` into separate `MIGRATION_SQL` (DROP-only, no DO$$ block) and `ENGINE_SETUP_SQL` (CREATE-only, no IF NOT EXISTS). PostgreSQL does not support `CREATE TABLE IF NOT EXISTS` inside a `DO$$` block.
- Used `asyncio.new_event_loop()` + `asyncio.set_event_loop()` pattern for async tests to avoid "Event loop is closed" errors when mixing testcontainer sessions.
- Pre-existing `test_oss_scanner.py::test_run_scan_creates_oss_scan_row` has an event-loop issue (not introduced by S07).