# F-00085 — S13 Tests Report

## What was done

- Implemented/expanded unit coverage for:
  - `orch.auto_merge_aggregator`
  - `resolve_project_config` flow (in `orch.auto_merge_aggregator`)
  - `orch.daemon.auto_merge_health`
  - model pricing/token rollup logic
- Added integration coverage for auto-merge observability/control-surface routes and DB persistence.
- Added dashboard TestClient coverage for auto-merge routes (success + validation/error paths + invariants/idempotency).
- Added shared fixture helpers in `tests/fixtures/auto_merge_observability/fixtures.py`.

## Files changed

- `tests/unit/test_auto_merge_aggregator.py`
- `tests/unit/test_auto_merge_config_resolution.py`
- `tests/unit/test_auto_merge_health.py`
- `tests/unit/test_auto_merge_pricing.py`
- `tests/integration/test_auto_merge_observability.py`
- `tests/integration/test_auto_merge_control_surface.py`
- `tests/dashboard/test_auto_merge_routes.py`
- `tests/fixtures/auto_merge_observability/fixtures.py`

## Test results

- Preflight static checks:
  - `make lint` ✅
  - `make typecheck` ✅
- Targeted test run (without coverage gate):
  - `uv run pytest --no-cov tests/unit/test_auto_merge_*.py tests/integration/test_auto_merge_*.py tests/dashboard/test_auto_merge_routes.py -v`
  - Result: **210 passed, 0 failed**
- Coverage run (scoped cov args + `--cov-fail-under=0` to avoid repository-wide fail-under interference):
  - `uv run pytest tests/unit/test_auto_merge_*.py tests/integration/test_auto_merge_*.py tests/dashboard/test_auto_merge_routes.py --cov=orch.auto_merge_aggregator --cov=orch.daemon.auto_merge_health --cov=dashboard.routers.auto_merge_ui --cov-fail-under=0 -v`
  - Result: **210 passed, 0 failed**
  - Coverage:
    - `orch.auto_merge_aggregator`: **95.85%**
    - `orch.daemon.auto_merge_health`: **100.00%**
    - `dashboard.routers.auto_merge_ui`: **85.71%**

## TDD RED evidence (structural)

- Confirmed failure by mutating config-resolution behavior (bypassing DB override path): tests expecting per-project DB override behavior fail (e.g., runtime source/value assertions in `test_resolve_per_project_db_phase_and_runtime_both_set`).

## Notes / observations

- Existing repository pytest defaults include global coverage instrumentation; targeted no-cov run was required to satisfy the “all green targeted tests” gate independently from project-wide fail-under.
- No live DB connections were used; integration tests ran via testcontainer fixtures.
