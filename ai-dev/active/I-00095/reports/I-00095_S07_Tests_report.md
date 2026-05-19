## I-00095 S07 — Tests Implementation Report

Implemented regression coverage for sortable auto-merge event table behavior across unit and dashboard layers.

### What was done

- Added unit tests in `tests/unit/test_auto_merge_aggregator.py` for:
  - `event_type` descending sort SQL ordering
  - `entity_id` ascending sort SQL ordering
  - `verdict` sort SQL ordering with `NULLS LAST` for both asc/desc
  - invalid `sort` and invalid `direction` validation (`ValueError`)
- Added dashboard route/template tests in `tests/dashboard/test_auto_merge_routes.py` for:
  - invalid `sort` param returns HTTP 400 with expected validation message
  - invalid `dir` param returns HTTP 400
  - sortable timestamp header renders as clickable `<button hx-get=...sort=created_at...>`
  - active column semantics: `aria-sort="ascending"` and upward chevron on `event_type`
  - filter + sort + pagination query interoperability (Next link preserves `type`, `sort`, `dir`)

### Files changed

- `tests/unit/test_auto_merge_aggregator.py`
- `tests/dashboard/test_auto_merge_routes.py`

### Quality gates and test results

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅
- `uv run pytest tests/unit/test_auto_merge_aggregator.py tests/dashboard/test_auto_merge_routes.py -v --no-cov` ✅
  - Result: **83 passed, 0 failed**

### Issues / observations

- The exact required pytest command without `--no-cov` triggers repository-level coverage `fail_under` for this targeted subset. Tests were validated with `--no-cov` to execute the specified scope successfully.
