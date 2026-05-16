# F-00085 — S06 Backend Report

## What was done

- Added `orch/auto_merge_aggregator.py` with:
  - project config resolution (`resolve_project_config`) with precedence: per-project DB > TOML > hardcoded default.
  - disabled-runtime fallback handling and guarded `auto_merge_config_invalid` emission.
  - status/event/verdict/refuse-list/health/token-cost rollup query helpers and dataclasses.
  - strict model pricing table and unknown-model handling (`has_unknown_models=True`, zero cost).
- Added `orch/daemon/auto_merge_health.py` with `maybe_run_probe()`:
  - idempotent interval gate
  - phase-0 no-op
  - bounded subprocess timeout
  - `auto_merge_health_probe` event persistence.
- Updated `orch/daemon/auto_merge.py`:
  - `attempt_resolution()` now uses resolved config for phase-0 gate.
  - `_resolve_runtime_option()` now prefers resolved runtime option id.
- Updated `orch/daemon/merge_queue.py`:
  - loaded TOML config is resolved through `resolve_project_config()` before `attempt_resolution()`.
- Updated `orch/daemon/main.py`:
  - added per-enabled-project post-processing health probe call (after batch/merge processing, exception-isolated).
- Added RED→GREEN unit tests:
  - `tests/unit/test_auto_merge_aggregator.py`
  - `tests/unit/test_auto_merge_config_resolution.py`
  - `tests/unit/test_auto_merge_health.py`
  - `tests/unit/test_auto_merge_pricing.py`

## Files changed

- `orch/auto_merge_aggregator.py` (new)
- `orch/daemon/auto_merge_health.py` (new)
- `orch/daemon/auto_merge.py` (updated)
- `orch/daemon/merge_queue.py` (updated)
- `orch/daemon/main.py` (updated)
- `tests/unit/test_auto_merge_aggregator.py` (new)
- `tests/unit/test_auto_merge_config_resolution.py` (new)
- `tests/unit/test_auto_merge_health.py` (new)
- `tests/unit/test_auto_merge_pricing.py` (new)

## Test results

- RED evidence run (before implementation):
  - `uv run pytest tests/unit/test_auto_merge_aggregator.py tests/unit/test_auto_merge_config_resolution.py tests/unit/test_auto_merge_health.py tests/unit/test_auto_merge_pricing.py -v`
  - failed with expected missing-module failures.
- Final targeted tests:
  - `uv run pytest tests/unit/test_auto_merge_*.py tests/unit/test_merge_queue.py -v --no-cov`
  - **95 passed, 0 failed**.
- Preflight gates:
  - `make format` ✅
  - `make typecheck` ✅
  - `make lint` ✅

## Issues / observations

- Running very narrow pytest selections with coverage enabled in this repo can trip global `fail-under` due to broad source scope; final targeted verification used `--no-cov` to keep the step-level unit check focused and deterministic.
