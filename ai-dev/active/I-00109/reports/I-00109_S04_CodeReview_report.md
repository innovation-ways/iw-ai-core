# I-00109 S04 Code Review Report

**Agent**: code-review (S04)
**Work Item**: I-00109 — `GET /project/{project_id}/docs/{doc_id}/pdf` raises unhandled `PermissionError` → HTTP 500 when on-disk PDF cache dir is not writable
**Step Reviewed**: S03 (tests-impl)
**Date**: 2026-05-24

---

## Verdict: ✅ PASS

Zero CRITICAL, zero HIGH, zero MEDIUM_FIXABLE findings. All review gates pass.

---

## Pre-Review Lint & Format Gate

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 889 files already formatted |

No new violations introduced by S03.

---

## Review Checklist

### 1. Semantic Correctness, Not Shape — ✅ FULL COVERAGE

The new test `test_docs_pdf_returns_200_when_cache_dir_not_writable` in `tests/dashboard/test_docs_pdf_cache_failure.py` asserts every AC1 contract point semantically:

| AC1 Assertion | Test Line | Strength |
|---|---|---|
| `resp.status_code == 200` | line 126 | ✅ Exact `== 200`, not `< 500` or `!= 500` |
| `Content-Type == application/pdf` | lines 127–130 | ✅ Exact string match, not `"pdf" in content-type` |
| `resp.content.startswith(b"%PDF")` | lines 131–134 | ✅ PDF magic bytes prefix check |
| `Content-Disposition: attachment` | lines 135–138 | ✅ `"attachment" in` check |
| WARNING log with exact substring | lines 141–149 | ✅ Filtered by level `WARNING` + substring `"Failed to write pdf_path cache for doc"` |
| `doc.pdf_path is None` after failure | lines 153–156 | ✅ `db_session.refresh(doc)` + exact `is None` check |

The `pdf_path` check is especially strong: without it, the test would pass even if `svc.update_doc` ran with a garbage path. The `refresh` pattern correctly proves the guard intercepted `svc.update_doc` before it landed on the DB.

Reference: `skills/iw-ai-core-testing/SKILL.md` §0 — the mutation-test question is satisfied: every assertion would fail if the production guard were removed.

### 2. Test Would Fail Against Pre-Fix Code — ✅ VERIFIED

Pre-fix, `dashboard/routers/docs.py::docs_pdf` had no `try/except` around the cache write at lines 320–324. `cache_dir.mkdir(...)` raises `PermissionError` → FastAPI surfaces it as HTTP 500 → `resp.status_code` is 500, not 200 → the first assertion fails. The test pins the regression.

**No source-revert verification performed** (the step's report did not use `git stash` or `git checkout HEAD~1`). Logical reasoning confirms the test fails on pre-fix code by construction.

### 3. File Location Discipline — ✅ CORRECT

- New file: `tests/dashboard/test_docs_pdf_cache_failure.py` ✅ (correct directory; `client` fixture works)
- Modified: `tests/dashboard/test_route_contract_sweep.py` ✅ (correct directory)

The `client` fixture in the new test file is defined inline (matching `test_route_contract_sweep.py::sweep_client` pattern) and correctly binds all module-level `SessionLocal` / `engine` references to the testcontainer engine. No `fixture 'client' not found` collection error possible.

### 4. `EXPECTED_5XX` Removal Is in the Same Step — ✅ CONFIRMED

S03's `files_changed` contains both:
- `tests/dashboard/test_docs_pdf_cache_failure.py` (new — the regression test)
- `tests/dashboard/test_route_contract_sweep.py` (modified — `EXPECTED_5XX` now `{}`)

The declaration `EXPECTED_5XX: dict[str, str] = {}` is preserved. The explanatory comment block is intact. No surrounding context was removed.

### 5. No Manual Source Revert — ✅ CLEAN

S03's report contains no mention of `git stash`, `git checkout HEAD~1 -- ...`, or any runtime source-revert. The step is clean.

### 6. No Full-Suite Run Inside the Step — ✅ TARGETED

S03 ran only:
```
uv run pytest tests/dashboard/test_docs_pdf_cache_failure.py tests/dashboard/test_route_contract_sweep.py -v --no-cov
```
Not `make test-integration`, not `make test-unit`. Targeted run only.

### 7. Scope Discipline — ✅ CLEAN

S03's `files_changed` contains exactly the two allowlisted test files. No `dashboard/routers/docs.py` (S01's territory) or any other file was touched.

### 8. Project Conventions — ✅ FULL COMPLIANCE

- `from __future__ import annotations` ✅ (line 11)
- Imports follow ruff isort order ✅
- Docstring mentions I-00109 by ID ✅ (multiple references)
- `monkeypatch.setattr` / `monkeypatch.delenv` used (not bare `mock.patch`) ✅
- `caplog.at_level("WARNING", logger="dashboard.routers.docs")` scoped to the route's logger ✅ (line 122)

---

## Test Verification Results

### Targeted Run
```
uv run pytest tests/dashboard/test_docs_pdf_cache_failure.py tests/dashboard/test_route_contract_sweep.py -v --no-cov
```
**Result**: 126 passed in 55.08s ✅

Key outcomes:
- `test_docs_pdf_returns_200_when_cache_dir_not_writable` — **PASSED** ✅
- `test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf]` — **PASSED** ✅ (normal pass after `EXPECTED_5XX` removal; no `xfail` marker, no `XPASS(strict)`)
- All 124 other sweep cases — **PASSED** ✅

### Unit Suite
```
make test-unit
```
**Result**: 3490 passed, 5 skipped, 5 xfailed, 2 xpassed, 46 warnings in 92.07s ✅

No regressions introduced.

---

## Final Review Result

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00109",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "test_docs_pdf_returns_200_when_cache_dir_not_writable: PASSED; test_route_returns_no_5xx[GET /project/{project_id}/docs/{doc_id}/pdf]: PASSED (normal pass after EXPECTED_5XX removal); 124 other sweep cases: PASSED; make test-unit: 3490 passed, 0 failed",
  "notes": "All 6 AC1 assertions are semantically strong (not shape-only). EXPECTED_5XX removal is in the same step as the regression test. File location discipline enforced. No source-revert operations. Targeted test run only. Full scope: exactly the two allowlisted test files."
}
```