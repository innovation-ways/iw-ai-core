# F-00069 S01 Backend Report

## What was done

### 1. Test infrastructure (pyproject.toml)
- Added `pytest-xdist>=3.5.0` to `[dependency-groups] dev`
- Updated `[tool.pytest.ini_options]` with coverage flags: `--cov=orch --cov=dashboard --cov=executor` and all report formats (term-missing, HTML, XML, JSON) to `tests/output/coverage/`
- Added `[tool.coverage.run]` block with `source`, `omit`, and `branch=true`
- Added `[tool.coverage.report]` with `fail_under = 46` (derived from baseline measurement below)
- Added per-file-ignores for `scripts/e2e_health_check.py` (T201, S310)

### 2. Makefile additions
- Added `test-parallel` target: `uv run pytest tests/unit tests/integration -v -n auto --dist=loadfile`
- Added `allure-report` target with install-check guard and `allure generate --clean`
- Wrapped existing `allure-serve` with install-check guard (replacing `npx allure`)
- Added `e2e-health`, `e2e-logs`, `e2e-stats` targets with `COMPOSE_E2E` variable
- Updated `.PHONY` list

### 3. `.gitignore`
- Added `tests/output/` entry (previously missing)

### 4. Baseline coverage measurement
- Ran `make test-unit` — measured **51.25%** overall line coverage
- Floor: `floor(51.25) - 5 = 46`
- `fail_under = 46` persisted to `pyproject.toml`

### 5. Coverage service (`dashboard/services/coverage_service.py`)
- Pure functions: `PackageRow`, `FileRow`, `CoverageView` dataclasses
- `load_coverage()` reads `coverage.json` + `pyproject.toml` fail_under via `tomllib`
- Handles: file missing, JSON malformed (logs warning), parse error
- Per-package rollup from file paths (first path segment)
- Color badge: green (≥threshold), amber (threshold-10 to threshold), red (<threshold-10)

### 6. FastAPI router (`dashboard/routers/coverage.py`)
- `GET /system/coverage` — renders `pages/system/coverage.html`
- `GET /system/coverage/files/{package}` — renders `fragments/coverage_files.html` (404 if unknown package)
- Uses `request.app.state.templates` pattern (matching existing routers)
- Registered `coverage` router in `dashboard/app.py` (alphabetically sorted import + include_router call)

### 7. E2E health check script (`scripts/e2e_health_check.py`)
- Parses `docker-compose.e2e.yml` with `pyyaml`
- Extracts host ports from `ports:` mappings
- curls `http://localhost:<port>/health` with 5s timeout
- Prints `PASS/Fail per service`, exits 1 if any fail

### 8. TDD test for coverage_service (`tests/unit/dashboard/test_coverage_service.py`)
- 10 test cases covering: missing file, malformed JSON, valid JSON, package rollup, badge green/amber/red, files_by_package, threshold from pyproject, threshold-zero fallback
- All 10 tests pass

### 9. Design doc update
- "Baseline Coverage Snapshot" section appended with measured date (2026-04-29), baseline (51.25%), floor (46%), and notes on `executor/` coverage

## Files changed

| File | Change |
|------|--------|
| `pyproject.toml` | Added pytest-xdist, pytest-cov config, coverage config, fail_under=46, script ignores |
| `Makefile` | Added test-parallel, allure-report, wrapped allure-serve, e2e-health/logs/stats targets |
| `.gitignore` | Added `tests/output/` |
| `dashboard/services/coverage_service.py` | New — pure coverage view-model service |
| `dashboard/routers/coverage.py` | New — FastAPI router for /system/coverage |
| `dashboard/app.py` | Added coverage router import and include_router |
| `scripts/e2e_health_check.py` | New — E2E health check script |
| `tests/unit/dashboard/test_coverage_service.py` | New — 10 TDD tests for coverage_service |
| `ai-dev/active/F-00069/F-00069_Feature_Design.md` | Updated Baseline Coverage Snapshot section |

## Test results

- `tests/unit/dashboard/test_coverage_service.py`: **10 passed**
- Pre-existing unit test failures (9 failures in `test_mapgen_mermaid.py`, `test_rag_*`, `test_safe_migrate.py`) are unrelated to F-00069 changes and were present before S01
- Coverage threshold `fail_under=46` enforced — baseline at 51.25% passes

## Preflight

| Gate | Result |
|------|--------|
| format | ok (ruff format auto-fixed 2 files) |
| typecheck | ok (mypy on new files: no issues) |
| lint | S01 files pass; 2 pre-existing ARG001 errors in `code_qa.py` unrelated to S01 |

## Notes

- Templates (`pages/system/coverage.html`, `fragments/coverage_files.html`) intentionally not created — owned by S02 (frontend). `/system/coverage` will 500 until S02 lands.
- 9 pre-existing unit test failures are unrelated to F-00069 changes.
- `make lint` shows 2 errors in `dashboard/routers/code_qa.py` (ARG001 unused args) — pre-existing, not introduced by S01.
- The `--cov-fail-under=46` threshold is enforced by pytest-cov automatically; no manual flag needed in Makefile.
