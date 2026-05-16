# F-00085 — S08 API Report

## What was done

- Added new dashboard router `dashboard/routers/auto_merge_ui.py` implementing the 7 required project-scoped auto-merge endpoints.
- Wired router in `dashboard/app.py`.
- Added focused dashboard tests in `tests/dashboard/test_auto_merge_routes.py` covering all 7 endpoint contracts (page, status, events, event detail, verdict write, config write, rollup).
- Implemented operator sentinel behavior: defaults to `"dashboard"`, overridden by `X-Operator` header.
- Implemented verdict/config validations and DB upserts with conflict handling.
- Implemented config update audit event emission (`auto_merge_config_updated`) with old/new metadata payload.
- Implemented diff viewer data build for `merge_auto_resolved` event details using `git show main:<file>` with `cwd`, timeout, and safe fallback behavior.
- Added template placeholder fallback rendering when S10 templates are not present yet, while still referencing required template paths.

## Files changed

- `dashboard/routers/auto_merge_ui.py`
- `dashboard/app.py`
- `tests/dashboard/test_auto_merge_routes.py`

## TDD RED → GREEN evidence

- RED run:
  - `uv run pytest tests/dashboard/test_auto_merge_routes.py::test_get_auto_merge_page_red_before_wiring -v`
  - Failure line: `assert 404 == 200`
- GREEN run:
  - `PYTEST_ADDOPTS='--no-cov' uv run pytest tests/dashboard/test_auto_merge_routes.py -v`
  - Result: `9 passed`

## Preflight / quality gates

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅
- Targeted tests command in prompt (`uv run pytest tests/dashboard/test_auto_merge_routes.py -v`) runs functionally green (9 passed) but fails repo-wide coverage threshold in this isolated invocation. Re-ran with `PYTEST_ADDOPTS='--no-cov'` for the targeted route contract verification requested in this step.

## Issues / observations

- The targeted single-file pytest command triggers global coverage fail-under enforcement (50%) in this repository context even when endpoint tests themselves pass. This is unrelated to endpoint correctness.
- Rollup route defensively handles aggregator breakdown query exceptions and falls back to an empty refuse-list breakdown so UI remains available.
