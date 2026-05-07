# F-00080_S08_CodeReview_prompt

**Work Item**: F-00080 — First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness)
**Step Being Reviewed**: S07 (tests-impl)
**Review Step**: S08

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status F-00080 --json`
- Design doc + S07 report + every test file in S07's `files_changed`

## Output Files

- `ai-dev/work/F-00080/reports/F-00080_S08_CodeReview_report.md`

## Pre-Review Lint & Format Gate

```bash
make lint
make format
```

NEW violations → CRITICAL.

## Review Checklist

### 1. Coverage (CRITICAL)
- 22 slugs covered in `test_help_router.py` parametrised 200 test.
- 10 list views covered in `test_empty_states.py`.
- Orphan-slug check covers ALL page templates under `templates/pages/**` and `templates/*.html`, not just those known to be in scope.
- Reverse orphan check (every fragment file is used by at least one page) is present.
- Path-traversal cases: `../etc/passwd`, URL-encoded `..%2F`, uppercase, leading digit, spaces, 33-char slug, empty slug — all → 404.
- `test_help_license.py` exists and covers AC7: Driver.js LICENSE file present + MIT-canonical text, IIFE bundle has MIT header, THIRD_PARTY_LICENSES lists Driver.js + MIT, no AGPL-licensed onboarding library vendored.

### 2. Determinism & isolation (HIGH)
- No flaky timing dependencies (no `time.sleep` longer than necessary; no `requests` calls).
- No tests rely on real DB state from production (use TestClient + monkeypatch).
- No tests mock the database in integration tests (CLAUDE.md hard rule).

### 3. Test conventions (MEDIUM)
- Match patterns in `tests/CLAUDE.md` and existing dashboard tests.
- Use existing fixtures (`tests/dashboard/conftest.py`) instead of building new ones.
- Test names start with `test_` and clearly describe behaviour.

### 4. Method test (MEDIUM)
- POST/PUT/DELETE on `/_help/queue` returns 405 — included in suite.

### 5. Static-asset reachability (MEDIUM)
- Smoke test asserts `/static/help/help.js`, `/static/help/tours.js`, `/static/vendor/driver/driver.js.iife.js` are all served (200 or HEAD).

## Test Verification

Run the FULL suite:

```bash
make test-unit
make test-integration
```

Both must pass with zero failures.

## Severity Levels

Standard scale.

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "F-00080",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
