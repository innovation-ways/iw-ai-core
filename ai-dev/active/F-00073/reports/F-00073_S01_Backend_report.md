# F-00073 S01 Backend Report

## What was done

Implemented smoke marker, smoke tests, `make smoke` target, CI workflow (`.github/workflows/test-quality.yml`), and `tests/unit/test_logging.py` — covering the backend portion of the Smoke Gate + Active Test CI + Logging Tests feature.

## Files Changed

| File | Change |
|------|--------|
| `pyproject.toml` | Added `smoke` marker + `slow` marker (existing `slow` tests had no marker registered) |
| `Makefile` | Added `smoke` target + added to `.PHONY` |
| `.github/workflows/test-quality.yml` | **New** — 4-job CI: lint-typecheck, unit+coverage, integration, smoke |
| `tests/unit/test_smoke.py` | **New** — 7 smoke tests (4 passing, 3 xfail as documented blockers) |
| `tests/unit/test_logging.py` | **New** — 11 logging/redaction tests (9 passing, 2 xfail as documented blockers) |
| `tests/integration/test_cli_batches.py` | Added `@pytest.mark.smoke` to `test_batch_create_independent_items_all_group_0` |
| `tests/integration/test_dashboard_pages.py` | Added `@pytest.mark.smoke` to `test_project_dashboard_returns_200` |
| `tests/integration/test_dashboard_remaining.py` | Added `@pytest.mark.smoke` to `test_queue_returns_200` and `test_history_returns_200` |
| `tests/integration/test_db_identity_integration.py` | Added `@pytest.mark.smoke` to 3 healthz identity tests |
| `tests/unit/dashboard/test_coverage_service.py` | Added `@pytest.mark.smoke` to `test_missing_coverage_json` |
| `tests/unit/test_daemon_core.py` | Added `@pytest.mark.smoke` to `test_sighup_handler_sets_stale_mtime` |

## Smoke Test Inventory (15 collected)

| # | Test | Status | Notes |
|---|------|--------|-------|
| 1 | `tests/integration/test_cli_batches.py::test_batch_create_independent_items_all_group_0` | ✅ PASS | Existing test, marked smoke |
| 2 | `tests/integration/test_dashboard_pages.py::test_project_dashboard_returns_200` | ✅ PASS | Existing test, marked smoke |
| 3 | `tests/integration/test_dashboard_remaining.py::test_queue_returns_200` | ✅ PASS | Existing test, marked smoke |
| 4 | `tests/integration/test_dashboard_remaining.py::test_history_returns_200` | ✅ PASS | Existing test, marked smoke |
| 5 | `tests/integration/test_db_identity_integration.py::test_healthz_identity_200_on_match` | ✅ PASS | Existing test, marked smoke |
| 6 | `tests/integration/test_db_identity_integration.py::test_healthz_identity_503_on_mismatch` | ✅ PASS | Existing test, marked smoke |
| 7 | `tests/integration/test_db_identity_integration.py::test_healthz_identity_200_on_bootstrap` | ✅ PASS | Existing test, marked smoke |
| 8 | `tests/unit/dashboard/test_coverage_service.py::test_missing_coverage_json` | ✅ PASS | Existing test, marked smoke |
| 9 | `tests/unit/test_daemon_core.py::test_sighup_handler_sets_stale_mtime` | ✅ PASS | Existing test, marked smoke |
| 10 | `tests/unit/test_smoke.py::test_iw_help_exits_zero` | ✅ PASS | New, smoke |
| 11 | `tests/unit/test_smoke.py::test_base_import_works` | ✅ PASS | New, smoke |
| 12 | `tests/unit/test_smoke.py::test_dashboard_app_factory_creates` | ✅ PASS | New, smoke (uses `IW_CORE_OPERATOR_APPLY=true`) |
| 13 | `tests/unit/test_smoke.py::test_root_projects_page_renders` | ✅ PASS | New, smoke (uses `IW_CORE_OPERATOR_APPLY=true`) |
| 14 | `tests/unit/test_smoke.py::test_db_url_construction_redacts_password` | 🔴 XFAIL | BLOCKER F-00073-S01 — `get_db_url()` returns raw password |
| 15 | `tests/unit/test_smoke.py::test_get_orch_db_url_redacts_password` | 🔴 XFAIL | BLOCKER F-00073-S01 — `get_orch_db_url()` returns raw password |

## Logging Test Inventory (12 collected)

| # | Test | Status | Notes |
|---|------|--------|-------|
| 1 | `TestLoggingConfiguration::test_orch_logger_exists` | ✅ PASS | |
| 2 | `TestLoggingConfiguration::test_dashboard_logger_exists` | ✅ PASS | |
| 3 | `TestLoggingConfiguration::test_orch_logger_level_is_info_or_lower` | ✅ PASS | |
| 4 | `TestLoggingConfiguration::test_dashboard_logger_level_is_info_or_lower` | ✅ PASS | |
| 5 | `TestLoggingConfiguration::test_orch_logger_propagates_to_root` | ✅ PASS | |
| 6 | `TestLoggingConfiguration::test_dashboard_logger_propagates_to_root` | ✅ PASS | |
| 7 | `TestCredentialRedaction::test_engine_repr_does_not_expose_password` | ✅ PASS | |
| 8 | `TestCredentialRedaction::test_engine_url_render_hide_password` | ✅ PASS | |
| 9 | `TestCredentialRedaction::test_safe_create_engine_password_not_in_repr` | ✅ PASS | |
| 10 | `TestCredentialRedaction::test_get_db_url_does_not_leak_password` | 🔴 XFAIL | BLOCKER F-00073-S01 |
| 11 | `TestCredentialRedaction::test_get_orch_db_url_does_not_leak_password` | 🔴 XFAIL | BLOCKER F-00073-S01 |
| 12 | `TestCredentialRedaction::test_log_output_never_contains_db_url_with_password` | 🔴 XFAIL | BLOCKER F-00073-S01 |
| 13 | `TestCredentialRedactionFindings::test_blocker_documented_placeholder` | ✅ PASS | |

## Pre-flight Results

| Gate | Result | Notes |
|------|--------|-------|
| `make format` | ✅ ok | 488 files already formatted |
| `make lint` | ⚠️ 10 errors | 8 pre-existing (dashboard/routers/tests.py PT028, test_baseline_qv_pipeline.py UP037), 2 S01 files fixed |
| `make typecheck` | ⚠️ 3 errors | Pre-existing: module_gen.py no-redef, code_qa.py conditional function variants |
| `make test-unit` | ⚠️ 4 failures | Pre-existing: test_qv_baseline, test_i00049_gate_command, test_safe_migrate (2) |
| `make smoke` | ✅ 13 passed, 2 xfailed | Expected — blockers documented as xfail |
| `make test-integration` | Not run in this step | Requires docker/testcontainer |

## Blockers (documented, not fixed in S01)

### BLOCKER F-00073-S01: Raw passwords in `get_db_url()` / `get_orch_db_url()`

**Location**: `orch/config.py:47-54` and `orch/config.py:57-74`

**Problem**: Both `get_db_url()` and `get_orch_db_url()` return the raw password embedded directly in the URL string (no masking, no `hide_password=True` on render).

**Evidence**: Tests in `tests/unit/test_logging.py` and `tests/unit/test_smoke.py` confirm that calling `get_db_url()` with a known password produces a URL where that password appears literally.

**Fix owner**: S02/S05 (backend-review / frontend-review agents)

**Impact**: Any log statement that writes the return value of `get_db_url()` or `get_orch_db_url()` will expose the DB password in logs. This includes the `TimingMiddleware` error handler at `dashboard/utils/timing.py:73`.

## Smoke Regression Guard

Ran `tests/unit/test_make_targets.py` (F-00069 S05) — all 7 tests pass. ✅

## Action Pins Resolved

| Action | SHA | Comment |
|--------|-----|---------|
| `actions/checkout` | `34e114876b0b11c390a56381ad16ebd13914f8d5` | v4.3.1 |
| `astral-sh/setup-uv` | `08807647e7069bb48b6ef5acd8ec9567f424441b` | v8.1.0 |
| `actions/upload-artifact` | `b4b15b8c7c6ac21ea08fcf65892d2ee8f75cf882` | v4.4.3 |

Postgres major version in CI: `15-alpine` (matches `docker-compose.bootstrap.yml`).