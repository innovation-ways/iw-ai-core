# I-00035 S01 Backend Report

## What was done

Implemented a production-DB guardrail for `scripts/e2e_seed.py` to prevent accidental corruption of production data when the script is run from a host whose `.env` points at the live orchestration DB (port 5433).

### Changes Made

1. **`scripts/e2e_seed.py`**: Added `_check_production_guardrail()` function and integrated it into `seed()`. The guardrail checks:
   - If `IW_CORE_EXPECTED_INSTANCE_ID` is set (production-like environment) AND `IW_E2E_SEED` is NOT set → exits with code 2 and error message BEFORE opening any session
   - Bootstrap mode (no `IW_CORE_EXPECTED_INSTANCE_ID`) is always allowed

2. **`docker-compose.e2e.yml`**: Added `IW_E2E_SEED: "1"` to `e2e-dashboard` environment so the legitimate container path stays green.

### Guardrail Behavior

| Environment | Result |
|-------------|--------|
| `IW_CORE_EXPECTED_INSTANCE_ID` set + `IW_E2E_SEED` not set | `SystemExit(2)` - blocked |
| `IW_CORE_EXPECTED_INSTANCE_ID` set + `IW_E2E_SEED=1` | Allowed - passes guardrail |
| `IW_CORE_EXPECTED_INSTANCE_ID` not set (bootstrap) | Allowed - passes guardrail |

## Files Changed

- `scripts/e2e_seed.py` - Added production guardrail function and call inside `seed()`
- `docker-compose.e2e.yml` - Added `IW_E2E_SEED: "1"` env var to e2e-dashboard service

## Test Results

- **Unit tests**: 1243 passed, 19 warnings (pre-existing async warnings unrelated to this change)
- **Lint (ruff)**: All checks passed on `scripts/e2e_seed.py`
- **Mypy**: 2 pre-existing errors (lines 299-300 in `_seed_work_items`, not related to this change)
- **Manual verification**: Guardrail correctly blocks when `IW_CORE_EXPECTED_INSTANCE_ID` is set without `IW_E2E_SEED`, and allows in bootstrap mode or with `IW_E2E_SEED=1`

## Issues or Observations

- The guardrail implementation was restructured from module-level (immediate exit on import) to function-level (exit when `seed()` is called). This was necessary to allow existing unit tests (`test_e2e_seed_discovery.py`) to import and test the helper functions (`_discover_fixture_files`, `_run_fixture`) without triggering the guardrail. The acceptance criteria AC1 ("exits with status code 2 BEFORE opening any session") is still satisfied since the guardrail fires before `get_session()` is called inside `seed()`.