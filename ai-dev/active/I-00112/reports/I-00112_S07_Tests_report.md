# I-00112 S07 — Tests Report

## What was done
- Added success-contract regression tests at subprocess boundary:
  - `tests/unit/test_keep_alive_poller_success_contract.py` (tests 1–4).
  - `tests/integration/test_keep_alive_poller_success_contract.py` (tests 5–6), because `tests/unit/conftest.py` provides a mocked `db_session`.
- Updated service unit tests for `FireResult` shape and strict success contract:
  - `tests/unit/test_keep_alive_service.py`.
- Added/updated poller unit tests to mock `FireResult` (not tuple):
  - `tests/unit/test_keep_alive_poller.py`.
- Added dashboard render regression tests for new Elapsed/Output columns and NULL fallback:
  - `tests/dashboard/test_keep_alive_runs_table.py`.

## Files changed
- `tests/unit/test_keep_alive_poller_success_contract.py`
- `tests/integration/test_keep_alive_poller_success_contract.py`
- `tests/unit/test_keep_alive_service.py`
- `tests/unit/test_keep_alive_poller.py`
- `tests/dashboard/test_keep_alive_runs_table.py`

## Preflight
- `make format`: fixed (applied `ruff format` to new/changed tests, then check passed)
- `make typecheck`: ok
- `make lint`: ok

## Test results
Executed:

```bash
uv run pytest \
  tests/unit/test_keep_alive_poller_success_contract.py \
  tests/integration/test_keep_alive_poller_success_contract.py \
  tests/unit/test_keep_alive_service.py \
  tests/unit/test_keep_alive_poller.py \
  tests/dashboard/test_keep_alive_runs_table.py \
  -v
```

Result: **24 passed, 0 failed**.

## TDD red evidence
`n/a — dedicated coverage step; behavioural RED owned by S03 (existing tests broken by FireResult signature change). Per-test pre-S03 failure reasoning recorded below.`

## Notes (per-test pre-S03 reasoning)
- `test_i00112_silent_no_op_is_not_success_empty_stdout`: pre-S03 rc==0 path would have been treated success; this would fail and catches the incident class directly.
- `test_i00112_silent_no_op_is_not_success_fast_elapsed`: pre-S03 ignored elapsed floor; would incorrectly classify success.
- `test_i00112_real_round_trip_is_success`: guards valid success path after stricter contract.
- `test_i00112_nonzero_returncode_is_failure`: preserves nonzero failure invariant.
- `test_i00112_poller_persists_captured_fields`: pre-S03 had no persisted stdout/stderr/elapsed/returncode; this assertion set would fail.
- `test_i00112_poller_logs_failed_when_contract_violated`: canonical reproduction; pre-S03 would log success for rc=0 no-op.
