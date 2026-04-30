# F-00069_S06_CodeReview_Tests_prompt

**Work Item**: F-00069 -- Test Execution, Coverage Gate, Reports, and Coverage Dashboard View
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `uv run iw item-status F-00069 --json`
- `ai-dev/active/F-00069/F-00069_Feature_Design.md`
- `ai-dev/active/F-00069/reports/F-00069_S05_Tests_report.md`
- All test files added by S05

## Output Files

- `ai-dev/active/F-00069/reports/F-00069_S06_CodeReview_report.md`

## Review Checklist

### 1. Coverage of design's Boundary Behavior table

For each row in the design's "Boundary Behavior" table, confirm a corresponding test exists. Missing scenarios are CRITICAL findings.

- [ ] coverage.json missing → empty state test
- [ ] coverage.json malformed → error path test
- [ ] coverage.json partial (overall but no files) → graceful render test
- [ ] threshold absent in pyproject → fallback to 0 test
- [ ] coverage exactly at threshold → green badge test
- [ ] coverage below threshold → red badge test
- [ ] xdist `-n 1` mode (smoke check exists in test_make_targets.py)
- [ ] allure CLI absent (Makefile inspection — covered by smoke test)
- [ ] e2e stack down (out of scope for unit tests; verified in S13)

### 2. Test isolation

- [ ] No test touches live DB (port 5433).
- [ ] No test reads/writes `tests/output/coverage/` real path — uses `tmp_path` and monkeypatch.
- [ ] No test depends on order with another test.
- [ ] All tests honor `tests/CLAUDE.md` strict rules.

### 3. Test quality

- [ ] Each test name describes what it verifies.
- [ ] Assertions are specific (not just `assert response.status_code != 500`).
- [ ] Fixtures are reused where appropriate.
- [ ] No `time.sleep`, no flaky timing, no real network calls.
- [ ] BeautifulSoup or specific text assertions used for HTML structure.

### 4. Coverage of invariants

The design lists invariants 1–8. Confirm tests assert at least:
- Invariant 3 (service does not raise on missing/malformed) — explicit tests.
- Invariant 4 (no DB / no jobs / no pytest invocation) — visible by code inspection of the service file.
- Invariant 6 (xdist uses loadfile) — Makefile string smoke test.
- Invariant 7 (no new external deps beyond pytest-xdist + maybe pyyaml) — pyproject dep diff inspection.

### 5. Test execution

- [ ] `uv run pytest tests/unit/dashboard/test_coverage_service.py -v` passes locally.
- [ ] `uv run pytest tests/dashboard/test_coverage_page.py -v` passes locally.
- [ ] `uv run pytest tests/unit/test_make_targets.py -v` passes locally.
- [ ] No regressions in the rest of the unit suite.

## Severity Levels

(Standard table.)

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00069",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
