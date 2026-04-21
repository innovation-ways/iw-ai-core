# F-00057_S08_CodeReview_prompt

**Work Item**: F-00057
**Step Being Reviewed**: S07 (tests-impl — boundary + freshness + invariant tests)
**Review Step**: S08

---

## Input Files

- `ai-dev/active/F-00057/F-00057_Feature_Design.md` — Boundary Behavior + Invariants sections
- `ai-dev/active/F-00057/reports/F-00057_S07_Tests_report.md`
- Files listed in S07 report

## Output Files

- `ai-dev/active/F-00057/reports/F-00057_S08_CodeReview_report.md`

## Context

Review the test additions from S07. The goal is to verify that every Boundary Behavior row and every Invariant from the design doc has a dedicated test, that tests are isolated (no live DB), and that they follow project conventions.

## Review Checklist

### 1. Coverage

Cross-check the design doc against tests:

- **Every Boundary Behavior row has a dedicated test** in `test_oss_boundary.py` (9 rows → 9 tests).
- **Every Invariant has a dedicated assertion** (7 invariants → at least 7 tests, can share files).
- **Freshness (AC5)** covered in `test_oss_freshness.py` with at least 3 scenarios.

### 2. Test isolation (CLAUDE.md hard rules)

- NO connections to the live DB on port 5433.
- Testcontainers used for every integration test.
- `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")` applied where needed.
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` run after `create_all()` (per CLAUDE.md hard rule).
- No `importlib.reload(orch.config)` — any env overrides use `monkeypatch.delenv` or fixture-scoped env.
- Each test is order-independent (no shared mutable state between tests).

### 3. Quality

- Test names describe what they verify (not `test_1`, `test_oss`).
- Assertions are semantic (assert on the invariant, not on shape-only).
- Fixtures reused from `tests/conftest.py` where applicable; new fixtures justified.
- Monkeypatches are scoped tightly (function-level, not module-level).
- No sleeps or timing-sensitive assertions.

### 4. Red-before-green evidence

Per TDD, every boundary/invariant test should have been **shown to fail** against pre-S03/S05 code before passing against merged code. The S07 report's notes field should mention this; flag if missing.

### 5. Performance

- Integration test file total runtime under 60s (testcontainer startup dominates).
- Tests that only need mocks do NOT spin up a container.

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — all tests pass.
2. `make test-unit` — pass.
3. `make lint` — pass.
4. Spot-check that at least one test fails if you comment out the related invariant's implementation (review-time spot check).

## Review Result Contract

Standard JSON. `verdict: pass` only if zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
