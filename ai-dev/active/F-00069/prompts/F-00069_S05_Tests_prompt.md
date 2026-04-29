# F-00069_S05_Tests_prompt

**Work Item**: F-00069 -- Test Execution, Coverage Gate, Reports, and Coverage Dashboard View
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

(Standard policy. No Docker calls in tests; testcontainer fixtures are exempt and acceptable.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. Tests must not invoke alembic against the live DB.)

## Input Files

- `ai-dev/active/F-00069/F-00069_Feature_Design.md`
- S01–S04 reports
- `dashboard/services/coverage_service.py`
- `dashboard/routers/coverage.py`
- `dashboard/templates/pages/system/coverage.html`
- `dashboard/templates/fragments/coverage_files.html`
- `tests/conftest.py` (fixture patterns)
- `tests/CLAUDE.md` (live-DB-guard rules)

## Output Files

- New: `tests/unit/dashboard/test_coverage_service.py`
- New: `tests/dashboard/test_coverage_page.py`
- New: `tests/fixtures/coverage_sample.json` (sample coverage.json for tests)
- `ai-dev/active/F-00069/reports/F-00069_S05_Tests_report.md`

## Context

You are writing the test coverage for the new coverage view. The
service is pure functions; the router has two endpoints. Both can be
exercised without a live DB.

## Requirements

### 1. Sample fixture

Create `tests/fixtures/coverage_sample.json` mimicking `coverage.py`'s
JSON output. At minimum:

```json
{
  "meta": {"version": "7.6.0", "timestamp": "2026-04-29T12:00:00Z"},
  "files": {
    "orch/foo.py": {
      "summary": {
        "covered_lines": 80, "num_statements": 100,
        "percent_covered": 80.0,
        "missing_lines": 20, "excluded_lines": 0,
        "num_branches": 20, "num_partial_branches": 2, "covered_branches": 16
      }
    },
    "orch/bar.py": { "summary": { "covered_lines": 50, "num_statements": 50, "percent_covered": 100.0, "missing_lines": 0, "excluded_lines": 0, "num_branches": 10, "num_partial_branches": 0, "covered_branches": 10 } },
    "dashboard/baz.py": { "summary": { "covered_lines": 30, "num_statements": 60, "percent_covered": 50.0, "missing_lines": 30, "excluded_lines": 0, "num_branches": 12, "num_partial_branches": 4, "covered_branches": 6 } },
    "executor/qux.py": { "summary": { "covered_lines": 5, "num_statements": 10, "percent_covered": 50.0, "missing_lines": 5, "excluded_lines": 0, "num_branches": 0, "num_partial_branches": 0, "covered_branches": 0 } }
  },
  "totals": { "covered_lines": 165, "num_statements": 220, "percent_covered": 75.0, "missing_lines": 55, "excluded_lines": 0, "num_branches": 42, "num_partial_branches": 6, "covered_branches": 32 }
}
```

(Exact percentages chosen so different threshold values exercise
green/amber/red boundaries deterministically.)

### 2. Unit tests — `tests/unit/dashboard/test_coverage_service.py`

Cover:

- `test_load_coverage_returns_view_when_file_present` — `view.available is True`, overall pct matches fixture, packages contains exactly `orch`, `dashboard`, `executor`.
- `test_load_coverage_handles_missing_file` — pass nonexistent path → `available is False, error is None, packages == [], threshold` still read from pyproject.
- `test_load_coverage_handles_malformed_json` — write `"not json"` to a temp path → `available is False, error is not None`, no exception.
- `test_threshold_read_from_pyproject` — pass a fixture pyproject.toml string with `fail_under = 70` → `view.threshold == 70`.
- `test_threshold_falls_back_to_zero_when_absent` — fixture pyproject without `fail_under` → `view.threshold == 0`.
- `test_color_badge_at_boundary` — package at exactly threshold → `badge == "green"`.
- `test_color_badge_below_threshold_within_10` — threshold 80, pkg at 75 → `badge == "amber"`.
- `test_color_badge_well_below_threshold` — threshold 80, pkg at 60 → `badge == "red"`.
- `test_color_badge_above_threshold` — threshold 50, pkg at 100 → `badge == "green"`.
- `test_per_package_rollup_aggregates_files` — verify `orch` row sums orch/foo.py + orch/bar.py correctly.
- `test_files_by_package_keys_are_first_path_segment` — `view.files_by_package` has `orch`, `dashboard`, `executor` keys.
- `test_gap_pct_signed` — overall 75, threshold 80 → `gap_pct == -5.0`. Overall 90, threshold 80 → `gap_pct == 10.0`.
- `test_mtime_iso_format` — fixture file has known mtime → `view.mtime_iso` is a parseable ISO 8601 string with timezone.

Use `pytest`'s `tmp_path` fixture; do NOT touch real `tests/output/`.

### 3. Dashboard tests — `tests/dashboard/test_coverage_page.py`

Use the existing dashboard `client` fixture (FastAPI `TestClient`):

- `test_coverage_page_renders_with_data` — monkeypatch `load_coverage` to return a populated view → 200, response HTML contains "Test Coverage", "Overall Lines", at least one package badge class.
- `test_coverage_page_renders_empty_state` — monkeypatch `load_coverage` to return `available=False` → 200, response contains "No coverage data yet" and the make-target hint.
- `test_coverage_files_fragment_renders` — monkeypatch `load_coverage` to return populated view; GET `/system/coverage/files/orch` → 200, fragment contains `orch/foo.py`.
- `test_coverage_files_fragment_404_unknown_package` — populated view; GET `/system/coverage/files/nope` → 404.
- `test_coverage_page_in_system_nav` — GET `/` (or any page); response HTML contains `/system/coverage` and `Test Coverage`.

### 4. xdist + threshold smoke

Add a single test under `tests/unit/test_make_targets.py` that:

- Confirms `make test-parallel`, `make e2e-health`, `make e2e-logs`, `make e2e-stats`, `make allure-report` are present in the Makefile (read the Makefile as text; assert the strings exist).
- Confirms `[tool.coverage.report] fail_under` is present and >= 0 in `pyproject.toml`.

This locks the public surface so future Makefile cleanups don't accidentally remove these.

### 5. Live-DB guard

All tests MUST honor `tests/CLAUDE.md` rules. The new coverage tests are filesystem-only and do not touch the DB.

## Project Conventions

- Mirror the file layout of `tests/unit/dashboard/` (other dashboard service tests live there).
- Use `pytest`'s `tmp_path`, `monkeypatch`, and the existing `client` fixture from `tests/dashboard/conftest.py`.
- Asserts on rendered HTML may use `bs4` (BeautifulSoup) which is in dev deps, or simple `in`/`not in`. Prefer `bs4` for non-trivial structure assertions.

## TDD Requirement

Write each test RED first (run, confirm it fails) before claiming the deliverable is GREEN. The implementation already exists from S01/S02 — the RED phase here is about asserting your test design is correct, not about driving implementation.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "overall_line_pct" in vars(view)` (shape only — doesn't prove the right value is computed)
- GOOD: `assert view.overall_line_pct == pytest.approx(75.0)` (semantic — proves the exact computation)
- GOOD: `assert view.packages[0].badge == "amber"` (proves specific boundary logic, not just badge exists)
- GOOD: `assert "No coverage data" in response.text` (proves specific message, not just status 200)

## Pre-flight Quality Gates

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit` — must pass with new tests
5. `uv run pytest tests/dashboard/test_coverage_page.py -v` — passes

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "F-00069",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/dashboard/test_coverage_service.py",
    "tests/dashboard/test_coverage_page.py",
    "tests/fixtures/coverage_sample.json",
    "tests/unit/test_make_targets.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
