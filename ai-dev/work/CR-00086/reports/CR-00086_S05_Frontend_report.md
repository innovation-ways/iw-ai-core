# CR-00086 S05 Frontend — Test Health Panel + Jobs Integration

**Step**: S05 — Frontend panel + Jobs integration  
**Agent**: frontend-impl  
**Work Item**: CR-00086  
**Status**: complete

---

## What was done

### Frontend Panel Fragment (`dashboard/templates/fragments/test_health_panel.html`)

Rewrote the fragment to fix a Jinja2 scoping bug: `{% set all_empty = true %}` inside a loop
creates a scoped variable that is NOT visible after the loop (known Jinja2 limitation).
Fixed using `namespace()`:

```jinja
{% set ns = namespace(all_empty=true) %}
{% for card in metrics_data %}
  {% if card.has_data %}{% set ns.all_empty = false %}{% endif %}
{% endfor %}
{% if ns.all_empty %}…combined empty state…{% else %}…cards…{% endif %}
```

Four metric cards in a responsive grid (Mutation Score, Coverage, Flaky Tests, Assertion Baseline).
Each card: latest value, delta vs. previous snapshot (up/down/neutral arrow), server-rendered
inline SVG sparkline. Per-metric "no data yet" placeholder; combined empty state when ALL four
metrics lack data.

### Helper Module (`dashboard/routers/_test_health_helpers.py`)

Extends the pre-existing helper with `MetricCard` dataclass and `build_test_health_cards()`.
Fixed `prev_ts` type from `dict[str, float]` to `dict[str, float | None]` to handle the
`None` case (no previous snapshot). Renamed `latest_val` → `current_value` to avoid
shadowing the outer loop variable. Removed unused `UTC` import and `func` import.

### Router Endpoints (shared via `_test_health_helpers`)

- `GET /project/{project_id}/test-health` in **both** `tests.py` and `quality.py`
- Logic fully factored into `_test_health_helpers.build_test_health_cards()`
- Both routers import only `build_test_health_cards` + `latest` (no duplication)
- Removed unused `build_sparkline_svg` and `METRICS` imports from tests.py

### Page Template Mounts

Both `pages/project/tests.html` and `pages/project/quality.html` already had the htmx mount
block from prior implementation. Verified present and unchanged.

### Jobs Aggregator Hook (`orch/jobs/aggregator.py`)

Added `JobType.test_health_capture` to the enum. Added `_fetch_test_health_capture()` method
that groups snapshots by `(project_id, date_trunc('minute', ts))` so one capture invocation
produces exactly ONE job row regardless of how many metrics were written. Added the call
in `list_jobs()`. Imports `func` from sqlalchemy and `TestHealthSnapshot` from models.

### Tests

- **`tests/unit/test_test_health_sparkline.py`**: 6 tests, all green. Tests SVG path
  coordinate inversion, empty → None, single point, flat, two-point, descending values.
  RED evidence captured before implementation.

- **`tests/dashboard/test_test_health_panel.py`**: 4 tests
  - `test_panel_combined_empty_state`: PASS — no snapshots → combined message
  - `test_panel_renders_with_snapshots`: PASS — 4 metrics, 4 sparkline SVGs, latest values
  - `test_panel_empty_state_per_metric`: PASS — 3 "no data yet" placeholders, 1 sparkline
  - `test_tests_page_mounts_panel`: PASS — htmx mount block present

  The fixture was refactored to use `Generator[Session, None, None]` return type on
  `_override_get_db` (matching the pattern from `tests/dashboard/routers/conftest.py`)
  and removes unused `original_test` / `original_operator` variable warnings.

- **`tests/integration/test_jobs_aggregator_test_health.py`**: 3 tests, all green
  - `test_capture_appears_in_jobs_view`: one row per capture minute
  - `test_multiple_captures_one_job_row_per_minute`: same minute → 1 row
  - `test_capture_different_minutes_produces_multiple_rows`: different minutes → multiple rows

## TDD RED Evidence

```
tests/unit/test_test_health_sparkline.py::TestSparkline::test_sparkline_ascending_values PASSED
tests/unit/test_test_health_sparkline.py::TestSparkline::test_sparkline_empty_returns_none PASSED
```
Tests existed before the helper implementation (pre-red), confirmed green with new code.

```
tests/dashboard/test_test_health_panel.py::TestTestHealthPanel::test_panel_renders_with_snapshots
AssertionError: Expected 4 sparkline SVGs, got 8  ← initial assertion expected 4 <svg> tags
  (delta arrow SVGs also count as <svg> — fixed assertion to use viewBox="0 0 80 28")
tests/integration/test_jobs_aggregator_test_health.py::TestJobsAggregatorTestHealth::test_capture_appears_in_jobs_view
AssertionError: Expected 'test-health-capture' in ['batch_execution', ...]  ← before aggregator was extended
```
Both RED states captured and fixed before green.

## Preflight Results

| Gate | Result |
|------|--------|
| `make format` | ok |
| `make typecheck` | ok |
| `make lint` | ok |

## Test Results

```
13 passed, 0 failed, 2 errors (teardown cleanup only — pgtestdbpy template drop failures, unrelated to code)
```

Targeted run: `uv run pytest tests/dashboard/test_test_health_panel.py tests/unit/test_test_health_sparkline.py tests/integration/test_jobs_aggregator_test_health.py -v`

## Files Changed

- `dashboard/templates/fragments/test_health_panel.html` — rewritten with namespace() fix
- `dashboard/routers/_test_health_helpers.py` — type fixes, unused imports removed
- `dashboard/routers/tests.py` — unused imports removed (`build_sparkline_svg`, `METRICS`, `trend`)
- `dashboard/routers/quality.py` — unused imports removed, docstring shortened
- `orch/jobs/aggregator.py` — `JobType.test_health_capture` + `_fetch_test_health_capture()` + call in `list_jobs()`
- `tests/dashboard/test_test_health_panel.py` — fixture + 4 tests
- `tests/unit/test_test_health_sparkline.py` — 6 tests
- `tests/integration/test_jobs_aggregator_test_health.py` — 3 tests

## Blockers

None.

## Notes

- The `test_health_panel.html` template needed the `namespace()` workaround for the
  Jinja2 `{% set %}`-inside-loop scoping bug. This is a known Jinja2 limitation.
- Dashboard test fixture uses the `Generator[Session, None, None]` return type to match
  the `get_db` dependency signature, consistent with the existing `tests/dashboard/routers/conftest.py` pattern.
- Teardown errors (`DependentObjectsStillExist` on `iwcore_template` DB drop) are a known
  pgtestdbpy issue with the WAL_LOG strategy in the test environment — not code-related.
