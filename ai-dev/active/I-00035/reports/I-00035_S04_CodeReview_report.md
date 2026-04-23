# I-00035 S04 Code Review Report

## What was done

Second-pass code review of the S01 backend implementation (production-DB guardrail for `scripts/e2e_seed.py`).

## Files Changed

No new files were modified in S04. The files from S01 remain:
- `scripts/e2e_seed.py` — added `_check_production_guardrail()` function and call inside `seed()`
- `docker-compose.e2e.yml` — added `IW_E2E_SEED: "1"` env var to e2e-dashboard service

## Review Findings

**Guardrail Implementation** (`scripts/e2e_seed.py:377-404`):
- Correctly fails fast before any session is opened (line 408: `_check_production_guardrail()` called before `get_session()`)
- Uses `get_expected_instance_id()` from `orch.db.identity` — the established DB identity check
- Exits with code 2 when `IW_CORE_EXPECTED_INSTANCE_ID` is set and `IW_E2E_SEED` is not set
- Bootstrap mode (no `IW_CORE_EXPECTED_INSTANCE_ID`) is always allowed
- Error message is clear and actionable

**Guardrail Placement**:
- Function-level (inside `seed()`) rather than module-level was the right call — allows unit tests to import and test helper functions (`_discover_fixture_files`, `_run_fixture`) without triggering the guardrail while still satisfying AC1 ("exits with status code 2 BEFORE opening any session")

**AC1 Verification**: The guardrail exits before `get_session()` is called — `seed()` → `_check_production_guardrail()` (line 408) → `with get_session() as db:` (line 409). AC1 satisfied.

**docker-compose.e2e.yml** (`line 77`):
- `IW_E2E_SEED: "1"` correctly added to `e2e-dashboard` environment so the container path works

## Test Results

- **Ruff**: All checks passed on `scripts/e2e_seed.py`
- **Mypy**: 2 pre-existing errors at lines 299-300 (in `_seed_work_items`) — unrelated to the guardrail changes
- **Unit tests**: 7/7 e2e_seed_discovery tests passed

## Issues or Observations

- The 2 mypy errors at lines 299-300 (`existing.design_doc_content = ...`, `existing.summary = ...`) are pre-existing type issues in `_seed_work_items` — the `existing` object from `db.get()` has an `object` type that doesn't match the `SQLCoreOperations` expected types. These are unrelated to the guardrail and existed before S01.
- No new issues found in the guardrail implementation itself.
- The guardrail is correctly implemented and the docker-compose path is green.