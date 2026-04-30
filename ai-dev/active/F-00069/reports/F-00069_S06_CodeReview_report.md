# F-00069_S06_CodeReview_report

## What was done

Code review of S05 (tests-impl) for F-00069: coverage service unit tests, dashboard page tests, and Makefile smoke tests.

## Files reviewed

- `tests/unit/dashboard/test_coverage_service.py` — 11 tests
- `tests/dashboard/test_coverage_page.py` — 5 tests
- `tests/unit/test_make_targets.py` — 7 tests
- `tests/fixtures/coverage_sample.json` — sample fixture
- `dashboard/services/coverage_service.py` — service under test

## Test results

```
23 passed, 0 failed
```

Coverage enforcement failure is expected behavior (threshold=46% vs actual ~19% for full suite) — not a test failure.

## Checklist assessment

### 1. Boundary Behavior table coverage

| Scenario | Test(s) | Status |
|----------|---------|--------|
| coverage.json missing | `test_missing_coverage_json` | ✓ |
| coverage.json malformed | `test_malformed_coverage_json` | ✓ |
| coverage.json partial (totals, no files) | `test_partial_coverage_json_totals_present_files_absent` | ✓ |
| Threshold absent in pyproject | `test_threshold_zero_when_missing` | ✓ |
| Coverage below threshold (red badge) | `test_badge_red` | ✓ |
| Coverage above threshold (green/amber) | `test_badge_green`, `test_badge_amber` | ✓ |
| xdist loadfile mode | `test_makefile_has_test_parallel` (smoke) + pyproject.toml comment | ✓ |
| Allure CLI absent | `test_makefile_has_allure_report` (smoke) | ✓ |
| e2e stack down | Out of scope for unit tests (S13) | ✓ |
| **Coverage exactly at threshold** | Not directly tested | **MINOR** |

**MINOR**: No test exercises the exact boundary where `overall_line_pct == threshold`. The overall badge turns green (since `_badge` uses `>=`) and `gap_pct == 0`. Indirectly covered by `test_badge_green` (dashboard at 90.0 >= 70) but not at the equality point.

### 2. Test isolation

- `coverage_service.py` is pure functions — no DB, no testcontainers.
- Service tests use `tmp_path` fixtures for all file operations.
- Dashboard tests use `unittest.mock.patch` to monkeypatch `load_coverage` at the router level, bypassing any filesystem access.
- `tests/dashboard/conftest.py` re-exports `db_session` from `tests/integration/conftest.py` (testcontainer-backed) — dashboard tests are integration tests by design.
- No test touches live DB (port 5433).
- No `time.sleep`, no real network calls.

### 3. Test quality

- Test names describe behavior: `test_malformed_coverage_json`, `test_badge_amber`, `test_coverage_files_fragment_404_unknown_package`.
- Assertions are specific: `view.available is False`, `view.error is not None`, `packages["executor"].badge == "red"`.
- Fixtures reused across tests: `sample_coverage_json`, `pyproject_with_threshold`, `temp_coverage_dir`.
- HTML structure verified via `assert "text" in html` — appropriate for template rendering checks.

### 4. Invariants

- **Invariant 3** (no raise on missing/malformed): `test_missing_coverage_json`, `test_malformed_coverage_json` verify `available=False` is returned without exceptions.
- **Invariant 4** (no DB / no jobs / no pytest): `coverage_service.py` has no `orch.db` imports — confirmed by code inspection.
- **Invariant 6** (xdist loadfile): Makefile line 46 has `-n auto --dist=loadfile`; smoke test `test_makefile_has_test_parallel` confirms presence.
- **Invariant 7** (no new deps): `pytest-xdist>=3.5.0` confirmed in pyproject.toml; no other new deps introduced.

### 5. Test execution

All three test files pass individually:
```
tests/unit/dashboard/test_coverage_service.py     11 passed
tests/dashboard/test_coverage_page.py             5 passed
tests/unit/test_make_targets.py                   7 passed
```

## Findings

| Severity | Count | Description |
|----------|-------|-------------|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 1 | Exact-threshold boundary (overall == threshold) not directly tested |
| LOW | 0 | — |

**MEDIUM-1**: No test exercises the exact boundary where `overall_line_pct == threshold`. The `_badge()` function uses `line_pct >= threshold` for green, so at equality the badge is green. `gap_pct` would be `0` at equality. While the logic is sound and covered indirectly by `test_badge_green` (90.0 >= 70), a dedicated test at the equality boundary would make the intent clearer.

## Mandatory fix count

**0** — no blocking issues found.

## Notes

- `tests/dashboard/conftest.py` properly re-exports integration fixtures, so dashboard tests run with testcontainer-backed DB.
- Makefile smoke tests check string presence only (acceptable for surface-level lock).
- Pre-existing typecheck/lint issues in `orch/daemon/container_info.py` and `orch/diagram/render.py` are outside S05 scope.
