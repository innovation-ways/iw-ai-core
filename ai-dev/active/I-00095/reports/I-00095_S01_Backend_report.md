# I-00095 — S01 Backend Report

## What was done

- Extended `list_recent_events` in `orch/auto_merge_aggregator.py` with new optional parameters:
  - `sort: str = "created_at"`
  - `direction: str = "desc"`
- Added a whitelist of sortable columns:
  - `created_at`, `event_type`, `entity_id`, `verdict`
- Added validation:
  - Invalid `sort` raises `ValueError` with allowed values
  - Invalid `direction` raises `ValueError` (`asc`/`desc` only)
- Applied dynamic ordering via SQLAlchemy column expressions.
- Implemented `NULLS LAST` when sorting by `verdict`, so rows without verdicts go to the bottom in both sort directions.
- Preserved default behavior for existing callers (created_at descending) by keeping defaults unchanged.

## TDD (RED → GREEN)

- Added RED test:
  - `test_list_recent_events_sorts_by_event_type_asc`
- RED run confirmed failure before implementation:
  - `TypeError: list_recent_events() got an unexpected keyword argument 'sort'`
- Implemented minimal backend changes.
- GREEN run passed for targeted test.

## Files changed

- `orch/auto_merge_aggregator.py`
- `tests/unit/test_auto_merge_aggregator.py`
- `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py` *(lint-only pre-existing issue fix to satisfy gate)*

## Test results

- `uv run pytest tests/unit/test_auto_merge_aggregator.py::test_list_recent_events_sorts_by_event_type_asc -v`
  - Test: **passed**
- `uv run pytest tests/unit/test_auto_merge_aggregator.py -v`
  - Tests: **23 passed, 0 failed**

Note: this repository's pytest invocation enforces global coverage and reports a coverage threshold failure when running this targeted subset only, even though all targeted tests pass.

## Quality gates

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅

## Issues / observations

- `verdict` sort uses `NULLS LAST` intentionally due outer join nullable values.
